"""Background worker process for ingestion jobs.

Runs as a separate process from the API (see docker-compose.yml's
`worker` service). Polls the Redis queue, promotes due delayed retries,
and drives each job through the ingestion state machine, calling the
existing IngestionService and ContentAnalysisService pipeline methods
at each stage.
"""

from __future__ import annotations

import asyncio
import signal
import time
import uuid

from app.core.config import get_settings
from app.core.exceptions import (
    ContentAnalysisEmptyError,
    DocumentNotFound,
    InvalidStateTransition,
)
from app.core.logging import configure_logging, get_logger
from app.core.redis import create_redis_client
from app.db.database import create_database_engine
from app.db.repositories.chunks import ChunkRepository
from app.db.repositories.dependencies import DependencyRepository
from app.db.repositories.documents import DocumentRepository
from app.db.repositories.ingestion_jobs import IngestionJobRepository
from app.db.repositories.pages import PageRepository
from app.db.repositories.structure import StructureRepository
from app.db.repositories.topics import TopicRepository
from app.db.session import create_session_factory
from app.models.ingestion_job import IngestionState
from app.services.ai.factory import create_llm_provider
from app.services.content_analysis.service import ContentAnalysisService
from app.services.dependency.linking_service import (
    PrerequisiteLinkingService,
)
from app.services.dependency.service import DependencyGraphService
from app.services.ingestion.job_queue import (
    DEFAULT_BACKOFF_BASE_SECONDS,
    ack,
    compute_backoff_seconds,
    dequeue,
    promote_due_delayed_jobs,
    schedule_retry,
)
from app.services.ingestion.reconciliation import reconcile_stale_jobs
from app.services.ingestion.service import IngestionService

logger = get_logger(__name__)

_shutdown_requested = False

RECONCILE_INTERVAL_SECONDS = 60


def _request_shutdown(signum: int, frame: object) -> None:
    global _shutdown_requested
    logger.info("Worker shutdown requested signal=%s", signum)
    _shutdown_requested = True


async def _process_job(
    job_id_str: str, session_factory, redis_client, llm_provider
) -> None:
    """Process a single job: drive it through the state machine, retry on failure."""
    job_id = uuid.UUID(job_id_str)

    async with session_factory() as session:
        job_repository = IngestionJobRepository(session)
        job = await job_repository.get_by_id(job_id)

        if job is None:
            logger.warning("Job not found, dropping job_id=%s", job_id_str)
            return

        if job.status in {
            IngestionState.COMPLETED,
            IngestionState.CANCELLED,
            IngestionState.FAILED,
        }:
            logger.info(
                "Dropping terminal job job_id=%s status=%s",
                job_id,
                job.status.value,
            )
            return

        document_repository = DocumentRepository(session)
        page_repository = PageRepository(session)
        structure_repository = StructureRepository(session)
        chunk_repository = ChunkRepository(session)
        topic_repository = TopicRepository(session)
        dependency_repository = DependencyRepository(session)

        ingestion_service = IngestionService(
            document_repository,
            page_repository,
            structure_repository,
            chunk_repository,
        )

        content_analysis_service = ContentAnalysisService(
            document_repository,
            structure_repository,
            topic_repository,
            chunk_repository,
            llm_provider,
        )

        dependency_graph_service = DependencyGraphService(
            document_repository,
            topic_repository,
            dependency_repository,
        )

        prerequisite_linking_service = PrerequisiteLinkingService(
            document_repository,
            topic_repository,
            llm_provider,
        )

        logger.info(
            "Job starting job_id=%s document_id=%s attempt=%s correlation_id=%s",
            job_id,
            job.document_id,
            job.attempt_count + 1,
            job.correlation_id,
        )

        try:
            await job_repository.transition(job, IngestionState.VALIDATING)
            await job_repository.commit()

            document = await document_repository.get_by_id(job.document_id)
            if document is None:
                raise DocumentNotFound(f"Document {job.document_id} was not found.")

            await job_repository.transition(job, IngestionState.EXTRACTING)
            await job_repository.commit()

            # Resume semantics: a retried job must not recompute stages
            # that already committed successfully. Pages/chapters/chunks
            # are re-read instead of regenerated so their IDs stay
            # stable, which is what lets the analysis stage skip (and
            # keep provenance for) already-analyzed chapters.
            pages = await page_repository.list_by_document(job.document_id)
            if pages:
                logger.info(
                    "Skipping extraction; pages already exist for "
                    "document_id=%s count=%s",
                    job.document_id,
                    len(pages),
                )
            else:
                await ingestion_service.extract_document(job.document_id)

            await job_repository.transition(job, IngestionState.NORMALIZING)
            await job_repository.commit()
            await job_repository.transition(job, IngestionState.STRUCTURING)
            await job_repository.commit()

            chapters = await structure_repository.list_chapters_by_document(
                job.document_id
            )
            if chapters:
                logger.info(
                    "Skipping structure detection; chapters already exist "
                    "for document_id=%s count=%s",
                    job.document_id,
                    len(chapters),
                )
            else:
                await ingestion_service.detect_document_structure(job.document_id)

                # Structure is a prerequisite for chapter-aware chunking;
                # re-read so chunks below are attributed correctly.
                chapters = await structure_repository.list_chapters_by_document(
                    job.document_id
                )

            await job_repository.transition(job, IngestionState.CHUNKING)
            await job_repository.commit()

            chunks = await chunk_repository.list_by_document(job.document_id)
            if chunks:
                logger.info(
                    "Skipping chunking; chunks already exist for "
                    "document_id=%s count=%s",
                    job.document_id,
                    len(chunks),
                )
            else:
                await ingestion_service.chunk_document(job.document_id)

            await job_repository.transition(job, IngestionState.ANALYZING)
            await job_repository.commit()

            await content_analysis_service.analyze_document(job.document_id)

            # An analysis that yields nothing must not look like success.
            # Chapters can legitimately be skipped for being too thin, but
            # a document that ends with zero topics cannot produce a
            # curriculum, and reporting COMPLETED hides that until someone
            # notices the curriculum is empty. This is the symptom of chunks
            # pointing at a replaced structure, so say so explicitly.
            persisted_topics = await topic_repository.list_by_document(job.document_id)
            await job_repository.commit()

            if not persisted_topics:
                unlinked_chunks = await chunk_repository.count_unlinked_by_document(
                    job.document_id
                )
                total_chunks = (
                    await chunk_repository.count_by_document(job.document_id)
                ).get(job.document_id, 0)
                await job_repository.commit()

                raise ContentAnalysisEmptyError(
                    f"Analysis produced no topics for document "
                    f"{job.document_id}. "
                    f"chapters={len(chapters)} "
                    f"chunks={total_chunks} "
                    f"chunks_without_chapter={unlinked_chunks}. "
                    "If chunks_without_chapter is greater than zero, the "
                    "structure was replaced without re-linking chunks; "
                    "re-run chunking."
                )

            # Resolve the AI-extracted prerequisite titles into a real,
            # acyclic topic graph. Curriculum planning orders weeks by this
            # topological order, so leaving it unbuilt silently degrades
            # sequencing to a workload sort. Idempotent: rebuilding
            # replaces the document's previous edges.
            await job_repository.transition(job, IngestionState.KNOWLEDGE_BUILDING)
            await job_repository.commit()

            # Cross-chapter prerequisites can only be named now that every
            # chapter's topics exist. Per-chapter extraction deliberately
            # skipped them, so without this pass the graph would hold only
            # within-chapter links and sequencing would ignore the real
            # cross-chapter spine.
            linking = await prerequisite_linking_service.link_document(job.document_id)
            await job_repository.commit()

            for rejected in linking.rejected:
                logger.warning(
                    "Rejected prerequisite link document_id=%s topic=%r "
                    "prerequisite=%r reason=%s",
                    job.document_id,
                    rejected.topic_title,
                    rejected.prerequisite_title,
                    rejected.reason,
                )

            graph = await dependency_graph_service.build_document_dependencies(
                job.document_id,
                additional_edges=linking.edges,
            )
            await job_repository.commit()

            logger.info(
                "Dependency graph built document_id=%s topics_ordered=%s "
                "rejected_cycles=%s unresolved=%s",
                job.document_id,
                len(graph.topological_order),
                len(graph.rejected_cycle_edges),
                len(graph.unresolved_prerequisites),
            )

            for unresolved in graph.unresolved_prerequisites:
                logger.warning(
                    "Unresolved prerequisite document_id=%s topic=%r "
                    "prerequisite=%r reason=%s",
                    job.document_id,
                    unresolved.topic_title,
                    unresolved.prerequisite_title,
                    unresolved.reason,
                )

            for cycle in graph.rejected_cycle_edges:
                logger.warning(
                    "Rejected dependency cycle edge document_id=%s "
                    "topic_id=%s depends_on=%s",
                    job.document_id,
                    cycle.topic_id,
                    cycle.depends_on_topic_id,
                )

            # PLANNING/VALIDATING_OUTPUT remain for the planner and
            # curriculum-quality stages, which run on demand rather than as
            # part of document ingestion.
            # Clear any error from an earlier attempt: the job is succeeding
            # now, and a stale message next to COMPLETED reads as an
            # unresolved failure. Clear before the transition so both
            # writes land in one commit.
            job.error_message = None
            await job_repository.transition(job, IngestionState.COMPLETED)
            await job_repository.commit()

            logger.info(
                "Job succeeded job_id=%s document_id=%s attempt=%s",
                job_id,
                job.document_id,
                job.attempt_count,
            )

        except Exception as exc:  # noqa: BLE001 - must catch all to record failure
            # The failing operation may have poisoned the session's
            # transaction (e.g. a failed flush expires every loaded
            # object). Roll back first so logging and the failure
            # handling below never raise a PendingRollbackError. If the
            # rollback itself raises (e.g. the pooled connection went
            # stale during a long LLM wait), the failure handling below
            # still schedules the retry instead of killing the worker.
            try:
                await session.rollback()
            except Exception:  # noqa: BLE001 - must still handle the failure
                logger.warning(
                    "Rollback after job failure raised; continuing "
                    "with failure handling job_id=%s",
                    job_id,
                    exc_info=True,
                )

            # The rollback expires every loaded attribute. Any ORM
            # attribute access then triggers a lazy async load in the
            # sync failure-handling context and raises MissingGreenlet,
            # so reload the job through the repository before logging or
            # writing fail/retry state.
            try:
                job = await job_repository.get_by_id(job_id)
            except Exception:  # noqa: BLE001 - must not lose the job
                job = None

            if job is None:
                logger.warning(
                    "Job could not be reloaded after failure job_id=%s; "
                    "scheduling plain retry",
                    job_id,
                    exc_info=True,
                )
                await schedule_retry(
                    redis_client, job_id_str, DEFAULT_BACKOFF_BASE_SECONDS
                )
                return

            logger.exception(
                "Job failed job_id=%s document_id=%s attempt=%s state=%s",
                job_id,
                job.document_id,
                job.attempt_count,
                job.status,
            )

            try:
                await job_repository.fail(job, str(exc))
                await job_repository.commit()

                retried = await job_repository.retry(job)
                await job_repository.commit()

                if retried:
                    delay = compute_backoff_seconds(job.attempt_count)
                    await schedule_retry(redis_client, job_id_str, delay)
                    logger.info(
                        "Job scheduled for retry job_id=%s delay_seconds=%s",
                        job_id,
                        delay,
                    )
                else:
                    logger.warning(
                        "Job exhausted retries job_id=%s attempts=%s",
                        job_id,
                        job.attempt_count,
                    )
            except (InvalidStateTransition, Exception):  # noqa: BLE001
                logger.warning(
                    "Job already in a non-retryable state after failure, "
                    "dropping job_id=%s status=%s",
                    job_id,
                    job.status.value,
                )


async def run_worker() -> None:
    """Main worker loop."""
    settings = get_settings()
    configure_logging(settings)

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    redis_client = create_redis_client(settings)
    llm_provider = create_llm_provider(settings)

    logger.info("Ingestion worker starting")

    try:
        last_reconcile = 0.0

        while not _shutdown_requested:
            await promote_due_delayed_jobs(redis_client)

            now = time.monotonic()
            if now - last_reconcile >= RECONCILE_INTERVAL_SECONDS:
                try:
                    requeued = await reconcile_stale_jobs(redis_client, session_factory)
                    if requeued:
                        logger.info(
                            "Reconciled stale ingestion jobs count=%s",
                            requeued,
                        )
                except Exception:  # noqa: BLE001 - must not kill the worker loop
                    logger.exception("Stale-job reconciliation failed")
                last_reconcile = now

            job_id = await dequeue(redis_client, poll_timeout=5)

            if job_id is None:
                continue

            try:
                await _process_job(job_id, session_factory, redis_client, llm_provider)
            except Exception:  # noqa: BLE001 - one bad job must not kill the loop
                logger.exception(
                    "Job crashed the processing path job_id=%s; "
                    "retry scheduled by failure handling or reconciliation",
                    job_id,
                )
            finally:
                await ack(redis_client, job_id)
    finally:
        logger.info("Ingestion worker shutting down")
        await redis_client.aclose()
        await engine.dispose()


def main() -> None:
    """Entry point: registers signal handlers and runs the worker loop."""
    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
