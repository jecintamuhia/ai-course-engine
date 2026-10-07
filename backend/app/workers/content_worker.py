"""Background worker process for bulk course-content generation.

Runs as a separate process from the API (see docker-compose.yml). Polls
its own Redis queue — never the ingestion queue — and drives one
ContentGenerationJob at a time, calling the existing
``CourseContentService.generate_week`` for each weekly unit of an
approved curriculum.

Generating a full 16-week course is thousands of LLM calls, far longer
than any HTTP request can hold open, so the API only enqueues and the UI
polls this job's progress.
"""

from __future__ import annotations

import asyncio
import signal
import time
import uuid
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.redis import create_redis_client
from app.db.database import create_database_engine
from app.db.repositories.chunks import ChunkRepository
from app.db.repositories.content_generation_jobs import (
    ContentGenerationJobRepository,
)
from app.db.repositories.curriculum import CurriculumRepository
from app.db.repositories.dependencies import DependencyRepository
from app.db.repositories.lessons import LessonRepository
from app.db.session import create_session_factory
from app.models.curriculum import CurriculumStatus
from app.services.ai.factory import create_llm_provider
from app.services.course_content.job_queue import (
    ack,
    dequeue,
    enqueue,
    promote_due_delayed_jobs,
)
from app.services.course_content.service import CourseContentService

logger = get_logger(__name__)

_shutdown_requested = False

RECONCILE_INTERVAL_SECONDS = 60
# A RUNNING job whose updated_at is older than this is assumed orphaned
# (worker killed mid-week) and re-enqueued.
STALE_RUNNING_MINUTES = 30


def _request_shutdown(signum: int, frame: object) -> None:
    global _shutdown_requested
    logger.info("Content worker shutdown requested signal=%s", signum)
    _shutdown_requested = True


async def _process_job(
    job_id_str: str, session_factory, redis_client, llm_provider
) -> None:
    """Generate lessons for every outstanding weekly unit of one curriculum."""
    job_id = uuid.UUID(job_id_str)

    async with session_factory() as session:
        job_repository = ContentGenerationJobRepository(session)
        job = await job_repository.get_by_id(job_id)

        if job is None:
            logger.warning("Content job not found, dropping job_id=%s", job_id_str)
            return

        if job.is_terminal:
            logger.info(
                "Dropping terminal content job job_id=%s status=%s",
                job_id,
                job.status.value,
            )
            return

        curriculum_repository = CurriculumRepository(session)
        chunk_repository = ChunkRepository(session)
        lesson_repository = LessonRepository(session)

        curriculum = await curriculum_repository.get_by_id_for_content(
            job.curriculum_id
        )
        if curriculum is None:
            await job_repository.fail(job, "Curriculum was not found.")
            await job_repository.commit()
            return

        if curriculum.status != CurriculumStatus.APPROVED:
            await job_repository.fail(
                job,
                "Curriculum must be approved before lessons can be generated.",
            )
            await job_repository.commit()
            return

        service = CourseContentService(
            curriculum_repository,
            chunk_repository,
            lesson_repository,
            llm_provider,
            dependency_repository=DependencyRepository(session),
        )

        await job_repository.start(job)
        await job_repository.commit()

        logger.info(
            "Content job starting job_id=%s curriculum_id=%s correlation_id=%s",
            job_id,
            job.curriculum_id,
            job.correlation_id,
        )

        # Lessons generated before topic linkage existed carry a NULL
        # topic_id; restore those links before week processing so retries
        # self-heal orphan lessons instead of skipping over them.
        relinked = await lesson_repository.relink_orphan_lessons(
            job.curriculum_id
        )
        if relinked:
            await session.commit()
            logger.info(
                "Relinked %s orphan lesson(s) to topics job_id=%s "
                "curriculum_id=%s",
                relinked,
                job_id,
                job.curriculum_id,
            )

        units = sorted(curriculum.units, key=lambda unit: unit.week_number)
        await job_repository.commit()

        failed_week_numbers: list[int] = []
        first_error: str | None = None

        for unit in units:
            if _shutdown_requested:
                logger.info(
                    "Shutdown requested mid-job; stopping after committed "
                    "progress job_id=%s",
                    job_id,
                )
                return

            # generate_week commits its own writes, so read the unit's
            # existing lessons on a fresh query.
            existing = await lesson_repository.list_by_unit(unit.id)
            expected_topic_ids = {
                link.topic_id
                for link in unit.topic_links
                if link.topic_id is not None
            }
            existing_topic_ids = {
                lesson.topic_id for lesson in existing if lesson.topic_id is not None
            }
            if (
                expected_topic_ids
                and expected_topic_ids.issubset(existing_topic_ids)
                and not job.rebuild_existing
            ):
                await job_repository.record_week(job, lessons_generated=0, skipped=True)
                await job_repository.commit()
                continue

            result = await service.generate_week(
                unit.id, preserve_existing=not job.rebuild_existing
            )
            generated = len(result["generated"])
            errors = result["errors"]
            skipped = result.get("skipped", [])
            preserved_topic_ids = (
                existing_topic_ids if not job.rebuild_existing else set()
            )
            generated_topic_ids = {
                getattr(lesson, "topic_id", None)
                for lesson in result["generated"]
                if getattr(lesson, "topic_id", None) is not None
            }
            missing_topic_ids = expected_topic_ids - (
                preserved_topic_ids | generated_topic_ids
            )

            if missing_topic_ids:
                # A partial week must remain retryable. Existing lesson
                # content is kept, while failed or ungrounded topics remain
                # visible as missing instead of counting the unit complete.
                failed_week_numbers.append(unit.week_number)
                await job_repository.record_week(
                    job, lessons_generated=generated, failed=True
                )
                if first_error is None:
                    details = errors or skipped
                    if details:
                        first_error = str(
                            details[0].get("error") or details[0].get("reason")
                        )
                logger.error(
                    "Week remains incomplete job_id=%s week=%s "
                    "missing_topics=%s topic_errors=%s",
                    job_id,
                    unit.week_number,
                    len(missing_topic_ids),
                    len(errors),
                )
            else:
                await job_repository.record_week(job, lessons_generated=generated)

            await job_repository.commit()

            if errors:
                logger.warning(
                    "Week generated with topic-level errors job_id=%s "
                    "week=%s errors=%s",
                    job_id,
                    unit.week_number,
                    errors,
                )

        if failed_week_numbers:
            # Report the shortfall instead of a bare success. Weeks that did
            # generate keep their lessons, so re-running only fills the gaps.
            summary = ", ".join(str(number) for number in failed_week_numbers)
            message = (
                f"{len(failed_week_numbers)} of {len(units)} weeks remain "
                f"incomplete (weeks {summary}); at least one mapped topic "
                "has no lesson. "
                f"{job.completed_weeks} week(s) were written and "
                f"{job.lessons_generated} lesson(s) generated. Re-run generation "
                "once the cause is resolved to fill the gaps."
            )
            if first_error:
                message = f"{message} First error: {first_error}"
            await job_repository.fail(job, message)
            await job_repository.commit()

            logger.error(
                "Content job finished with missing weeks job_id=%s "
                "curriculum_id=%s failed_weeks=%s completed_weeks=%s "
                "lessons=%s",
                job_id,
                job.curriculum_id,
                failed_week_numbers,
                job.completed_weeks,
                job.lessons_generated,
            )
            return

        await job_repository.complete(job)
        await job_repository.commit()

        logger.info(
            "Content job succeeded job_id=%s curriculum_id=%s weeks=%s lessons=%s",
            job_id,
            job.curriculum_id,
            job.completed_weeks,
            job.lessons_generated,
        )


async def _reconcile_stale(session_factory, redis_client) -> int:
    """Re-enqueue RUNNING jobs orphaned by a dead worker."""
    async with session_factory() as session:
        repository = ContentGenerationJobRepository(session)
        stale = await repository.list_stale_running(
            datetime.now(UTC) - timedelta(minutes=STALE_RUNNING_MINUTES)
        )
        for job in stale:
            logger.warning(
                "Re-enqueueing stale content job job_id=%s completed_weeks=%s",
                job.id,
                job.completed_weeks,
            )
            await enqueue(redis_client, str(job.id))
        return len(stale)


async def run_worker() -> None:
    """Main worker loop."""
    settings = get_settings()
    configure_logging(settings)

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    redis_client = create_redis_client(settings)
    llm_provider = create_llm_provider(settings)

    logger.info("Content generation worker starting")

    try:
        last_reconcile = 0.0

        while not _shutdown_requested:
            await promote_due_delayed_jobs(redis_client)

            now = time.monotonic()
            if now - last_reconcile >= RECONCILE_INTERVAL_SECONDS:
                try:
                    requeued = await _reconcile_stale(session_factory, redis_client)
                    if requeued:
                        logger.info("Reconciled stale content jobs count=%s", requeued)
                except Exception:  # noqa: BLE001 - must not kill the loop
                    logger.exception("Stale content-job reconciliation failed")
                last_reconcile = now

            job_id = await dequeue(redis_client, poll_timeout=5)

            if job_id is None:
                continue

            try:
                await _process_job(job_id, session_factory, redis_client, llm_provider)
            except Exception as exc:  # noqa: BLE001 - one bad job must not kill the loop
                logger.exception(
                    "Content job crashed the processing path job_id=%s", job_id
                )
                await _record_failure(session_factory, job_id, str(exc))
            finally:
                await ack(redis_client, job_id)
    finally:
        logger.info("Content generation worker shutting down")
        await redis_client.aclose()
        await engine.dispose()


async def _record_failure(session_factory, job_id_str: str, error: str) -> None:
    """Best-effort: persist a fatal error against a crashed job."""
    try:
        async with session_factory() as session:
            repository = ContentGenerationJobRepository(session)
            job = await repository.get_by_id(uuid.UUID(job_id_str))
            if job is None or job.is_terminal:
                return
            await repository.fail(job, error)
            await repository.commit()
    except Exception:  # noqa: BLE001 - never mask the original failure
        logger.exception(
            "Could not record failure for content job job_id=%s", job_id_str
        )


def main() -> None:
    """Entry point: registers signal handlers and runs the worker loop."""
    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
