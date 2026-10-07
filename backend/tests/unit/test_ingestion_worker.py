"""Unit tests for ingestion worker service construction."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, Mock

from app.models.ingestion_job import IngestionJob, IngestionState
from app.services.dependency.linker import LinkResolution
from app.services.dependency.service import DependencyGraphResult
from app.workers.ingestion_worker import _process_job


class _FakeJob:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.document_id = uuid.uuid4()
        self.status = IngestionState.PENDING
        self.attempt_count = 0
        self.max_attempts = 3
        self.correlation_id = "test-correlation"


class _FakeSession:
    def __init__(self, job: _FakeJob) -> None:
        self._job = job
        self._document = Mock()
        self.rollback_called = False

    async def get(self, model, pk):
        if model is IngestionJob:
            return self._job
        return self._document

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def execute(self, *args, **kwargs):
        return Mock()

    async def rollback(self) -> None:
        self.rollback_called = True


class _FakeSessionFactory:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def __call__(self) -> _FakeSessionFactory:
        return self

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, *exc_info) -> bool:
        return False


async def test_process_job_passes_all_repositories_and_llm_provider(
    monkeypatch,
) -> None:
    job = _FakeJob()
    session_factory = _FakeSessionFactory(_FakeSession(job))

    chunk_repo_instance = Mock()
    chunk_repo_instance.list_by_document = AsyncMock(return_value=[])
    chunk_repo_instance.count_unlinked_by_document = AsyncMock(return_value=0)
    chunk_repo_instance.count_by_document = AsyncMock(return_value={})
    ingestion_service_instance = AsyncMock()
    content_analysis_instance = AsyncMock()

    monkeypatch.setattr(
        "app.workers.ingestion_worker.ChunkRepository",
        MagicMock(return_value=chunk_repo_instance),
    )
    topic_repo_instance = Mock()
    topic_repo_instance.list_by_document = AsyncMock(return_value=[Mock()])
    monkeypatch.setattr(
        "app.workers.ingestion_worker.TopicRepository",
        MagicMock(return_value=topic_repo_instance),
    )
    page_repo_instance = Mock()
    page_repo_instance.list_by_document = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.workers.ingestion_worker.PageRepository",
        MagicMock(return_value=page_repo_instance),
    )
    structure_repo_instance = Mock()
    structure_repo_instance.list_chapters_by_document = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.workers.ingestion_worker.StructureRepository",
        MagicMock(return_value=structure_repo_instance),
    )
    monkeypatch.setattr(
        "app.workers.ingestion_worker.IngestionService",
        MagicMock(return_value=ingestion_service_instance),
    )

    content_analysis_cls = MagicMock(return_value=content_analysis_instance)
    monkeypatch.setattr(
        "app.workers.ingestion_worker.ContentAnalysisService",
        content_analysis_cls,
    )

    redis_client = Mock()
    llm_provider = Mock()

    await _process_job(str(job.id), session_factory, redis_client, llm_provider)

    assert content_analysis_cls.called
    call_args = content_analysis_cls.call_args.args
    assert len(call_args) == 5
    assert call_args[3] is chunk_repo_instance
    assert call_args[4] is llm_provider
    content_analysis_instance.analyze_document.assert_awaited_once_with(job.document_id)
    ingestion_service_instance.extract_document.assert_awaited_once_with(
        job.document_id
    )
    ingestion_service_instance.detect_document_structure.assert_awaited_once_with(
        job.document_id
    )
    ingestion_service_instance.chunk_document.assert_awaited_once_with(job.document_id)


async def test_process_job_drops_terminal_job_without_processing(
    monkeypatch,
) -> None:
    job = _FakeJob()
    job.status = IngestionState.CANCELLED
    session_factory = _FakeSessionFactory(_FakeSession(job))

    ingestion_service_instance = AsyncMock()
    content_analysis_instance = AsyncMock()

    monkeypatch.setattr(
        "app.workers.ingestion_worker.IngestionService",
        MagicMock(return_value=ingestion_service_instance),
    )
    content_analysis_cls = MagicMock(return_value=content_analysis_instance)
    monkeypatch.setattr(
        "app.workers.ingestion_worker.ContentAnalysisService",
        content_analysis_cls,
    )

    await _process_job(str(job.id), session_factory, Mock(), Mock())

    assert not content_analysis_cls.called
    assert not ingestion_service_instance.called


async def test_process_job_survives_analysis_failure_and_rolls_back(
    monkeypatch,
) -> None:
    job = _FakeJob()
    session = _FakeSession(job)
    session_factory = _FakeSessionFactory(session)

    ingestion_service_instance = AsyncMock()
    monkeypatch.setattr(
        "app.workers.ingestion_worker.IngestionService",
        MagicMock(return_value=ingestion_service_instance),
    )
    chunk_repo_instance = Mock()
    chunk_repo_instance.list_by_document = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.workers.ingestion_worker.ChunkRepository",
        MagicMock(return_value=chunk_repo_instance),
    )
    page_repo_instance = Mock()
    page_repo_instance.list_by_document = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.workers.ingestion_worker.PageRepository",
        MagicMock(return_value=page_repo_instance),
    )
    structure_repo_instance = Mock()
    structure_repo_instance.list_chapters_by_document = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.workers.ingestion_worker.StructureRepository",
        MagicMock(return_value=structure_repo_instance),
    )

    failing_analysis_cls = MagicMock()
    failing_analysis_cls.return_value.analyze_document = AsyncMock(
        side_effect=RuntimeError(
            "simulated database flush failure during topic persistence"
        )
    )
    monkeypatch.setattr(
        "app.workers.ingestion_worker.ContentAnalysisService",
        failing_analysis_cls,
    )

    redis_client = Mock()

    await _process_job(str(job.id), session_factory, redis_client, Mock())

    assert session.rollback_called is True
    assert job.error_message is not None
    assert job.error_message != ""
    assert job.status == IngestionState.PENDING  # retried, not stuck
    assert job.attempt_count >= 1
    assert redis_client.zadd.called  # retry scheduled in the delayed queue


def _patch_analysis_repos(monkeypatch) -> None:
    """Stub the repositories the worker uses to skip completed stages."""
    chunk_repo = Mock()
    chunk_repo.list_by_document = AsyncMock(return_value=[])
    chunk_repo.count_unlinked_by_document = AsyncMock(return_value=0)
    chunk_repo.count_by_document = AsyncMock(return_value={})
    monkeypatch.setattr(
        "app.workers.ingestion_worker.ChunkRepository",
        MagicMock(return_value=chunk_repo),
    )
    page_repo = Mock()
    page_repo.list_by_document = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.workers.ingestion_worker.PageRepository",
        MagicMock(return_value=page_repo),
    )
    structure_repo = Mock()
    structure_repo.list_chapters_by_document = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.workers.ingestion_worker.StructureRepository",
        MagicMock(return_value=structure_repo),
    )
    topic_repo = Mock()
    topic_repo.list_in_reading_order = AsyncMock(return_value=([], {}))
    topic_repo.list_by_document = AsyncMock(return_value=[Mock()])
    monkeypatch.setattr(
        "app.workers.ingestion_worker.TopicRepository",
        MagicMock(return_value=topic_repo),
    )


def _patch_linking_service(monkeypatch, edges=None, rejected=None):
    """Stub the document-wide prerequisite linking pass.

    Returns the mocked service class so callers can assert on the edges it
    handed to the graph builder.
    """
    instance = AsyncMock()
    instance.link_document.return_value = LinkResolution(
        edges=edges if edges is not None else {},
        rejected=rejected if rejected is not None else [],
    )
    cls = MagicMock(return_value=instance)
    monkeypatch.setattr("app.workers.ingestion_worker.PrerequisiteLinkingService", cls)
    return instance


async def test_process_job_builds_dependency_graph_after_analysis(
    monkeypatch,
) -> None:
    """Ingestion must resolve prerequisites before reporting completion.

    Regression: the worker transitioned straight from ANALYZING to
    COMPLETED, so every ingested document kept zero persisted dependency
    edges and curriculum sequencing fell back to a workload sort.
    """
    job = _FakeJob()
    session_factory = _FakeSessionFactory(_FakeSession(job))

    monkeypatch.setattr(
        "app.workers.ingestion_worker.IngestionService",
        MagicMock(return_value=AsyncMock()),
    )
    _patch_analysis_repos(monkeypatch)
    _patch_linking_service(monkeypatch)
    monkeypatch.setattr(
        "app.workers.ingestion_worker.ContentAnalysisService",
        MagicMock(return_value=AsyncMock()),
    )

    graph_instance = AsyncMock()
    graph_instance.build_document_dependencies = AsyncMock(
        return_value=DependencyGraphResult(
            topological_order=[uuid.uuid4(), uuid.uuid4()],
            rejected_cycle_edges=[],
            unresolved_prerequisites=[],
        )
    )
    graph_cls = MagicMock(return_value=graph_instance)
    monkeypatch.setattr(
        "app.workers.ingestion_worker.DependencyGraphService", graph_cls
    )

    await _process_job(str(job.id), session_factory, Mock(), Mock())

    graph_cls.assert_called_once()
    graph_instance.build_document_dependencies.assert_awaited_once_with(
        job.document_id, additional_edges={}
    )
    assert job.status == IngestionState.COMPLETED


async def test_process_job_passes_linker_edges_into_graph_build(
    monkeypatch,
) -> None:
    """Cross-chapter links must reach the graph, not just the resolver.

    The linking pass is the only source of cross-chapter edges; if the
    worker dropped them the graph would silently degrade to
    within-chapter links only.
    """
    job = _FakeJob()
    session_factory = _FakeSessionFactory(_FakeSession(job))
    cross_chapter_edges = {uuid.uuid4(): {uuid.uuid4()}}

    monkeypatch.setattr(
        "app.workers.ingestion_worker.IngestionService",
        MagicMock(return_value=AsyncMock()),
    )
    _patch_analysis_repos(monkeypatch)
    _patch_linking_service(monkeypatch, edges=cross_chapter_edges)
    monkeypatch.setattr(
        "app.workers.ingestion_worker.ContentAnalysisService",
        MagicMock(return_value=AsyncMock()),
    )

    graph_instance = AsyncMock()
    graph_instance.build_document_dependencies = AsyncMock(
        return_value=DependencyGraphResult(
            topological_order=[],
            rejected_cycle_edges=[],
            unresolved_prerequisites=[],
        )
    )
    monkeypatch.setattr(
        "app.workers.ingestion_worker.DependencyGraphService",
        MagicMock(return_value=graph_instance),
    )

    await _process_job(str(job.id), session_factory, Mock(), Mock())

    graph_instance.build_document_dependencies.assert_awaited_once_with(
        job.document_id, additional_edges=cross_chapter_edges
    )


async def test_process_job_does_not_complete_when_graph_build_fails(
    monkeypatch,
) -> None:
    """A graph-build failure must not be reported as a completed job."""
    job = _FakeJob()
    session_factory = _FakeSessionFactory(_FakeSession(job))

    monkeypatch.setattr(
        "app.workers.ingestion_worker.IngestionService",
        MagicMock(return_value=AsyncMock()),
    )
    _patch_analysis_repos(monkeypatch)
    monkeypatch.setattr(
        "app.workers.ingestion_worker.ContentAnalysisService",
        MagicMock(return_value=AsyncMock()),
    )

    graph_cls = MagicMock()
    graph_cls.return_value.build_document_dependencies = AsyncMock(
        side_effect=RuntimeError("simulated dependency resolution failure")
    )
    monkeypatch.setattr(
        "app.workers.ingestion_worker.DependencyGraphService", graph_cls
    )

    await _process_job(str(job.id), session_factory, Mock(), Mock())

    assert job.status != IngestionState.COMPLETED
