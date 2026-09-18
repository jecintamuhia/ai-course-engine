"""Unit tests for ingestion worker service construction."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, Mock

from app.models.ingestion_job import IngestionJob, IngestionState
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
    ingestion_service_instance = AsyncMock()
    content_analysis_instance = AsyncMock()

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

    await _process_job(
        str(job.id), session_factory, redis_client, llm_provider
    )

    assert content_analysis_cls.called
    call_args = content_analysis_cls.call_args.args
    assert len(call_args) == 5
    assert call_args[3] is chunk_repo_instance
    assert call_args[4] is llm_provider
    content_analysis_instance.analyze_document.assert_awaited_once_with(
        job.document_id
    )
    ingestion_service_instance.extract_document.assert_awaited_once_with(
        job.document_id
    )
    ingestion_service_instance.detect_document_structure.assert_awaited_once_with(
        job.document_id
    )
    ingestion_service_instance.chunk_document.assert_awaited_once_with(
        job.document_id
    )


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