"""Regression tests for ingestion integrity gaps.

Two real defects let a job report success while producing nothing usable:

1. ``detect_document_structure`` replaces the Chapter rows, so any chunk
   already pointing at the previous ones was orphaned. Content analysis
   groups chunks by chapter, so every chapter then read as empty.
2. Analysis that yields zero topics completed silently instead of failing.

A third, smaller one: a successful retry left the previous attempt's
error message attached to a COMPLETED job.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from app.models.ingestion_job import IngestionJob, IngestionState
from app.models.page import Page
from app.services.ingestion.service import IngestionService
from app.workers.ingestion_worker import _process_job


class _FakeChunkRow:
    def __init__(self, chunk_id: uuid.UUID, page_id: uuid.UUID) -> None:
        self.id = chunk_id
        self.page_id = page_id
        self.chapter_id = None
        self.section_id = None


def _apply_relink(rows, assignments) -> int:
    """Stand-in for ChunkRepository.relink_to_structure."""
    updated = 0
    for row in rows:
        target = assignments.get(row.id)
        if target is None:
            continue
        chapter_id, section_id = target
        if row.chapter_id == chapter_id and row.section_id == section_id:
            continue
        row.chapter_id = chapter_id
        row.section_id = section_id
        updated += 1
    return updated


def _make_ingestion_service(
    chunks: list[_FakeChunkRow], page_count: int | None = None
) -> IngestionService:
    """Build an IngestionService over an in-memory chunk set.

    The re-link path needs a chunk repository that behaves like the real
    one: listing returns the chunk rows and the relink write actually
    mutates their chapter_id, so the assertion observes the same rows the
    real UPDATE would have touched.
    """
    chunk_repository = Mock()
    chunk_repository.list_by_document = AsyncMock(return_value=chunks)
    # Mirror the real repository's semantics: set the ids on the loaded
    # rows and count only the ones that actually changed, so these tests
    # observe the same effect the real ORM flush would produce.
    chunk_repository.relink_to_structure = AsyncMock(side_effect=_apply_relink)
    chunk_repository.add_many = AsyncMock(side_effect=lambda rows: rows)
    chunk_repository.commit = AsyncMock()

    # Each distinct page_id gets its own page number, in the order the
    # chunks reference them, so the tests control which chapter a chunk
    # falls into simply by how many chunks they declare. Structure
    # detection requires pages to exist, so a test may declare pages
    # without any chunks having been cut from them yet.
    page_numbers: dict[uuid.UUID, int] = {}
    for chunk in chunks:
        page_numbers.setdefault(chunk.page_id, len(page_numbers) + 1)

    for extra in range(len(page_numbers), page_count or 0):
        page_numbers[uuid.uuid4()] = extra + 1

    pages = [
        Page(id=page_id, page_number=number, normalized_text="body text")
        for page_id, number in page_numbers.items()
    ]
    page_repository = Mock()
    page_repository.list_by_document = AsyncMock(return_value=pages)
    page_repository.commit = AsyncMock()

    document_repository = Mock()
    document_repository.get_by_id = AsyncMock(return_value=Mock(id=uuid.uuid4()))

    structure_repository = Mock()
    structure_repository.delete_by_document = AsyncMock()
    structure_repository.add_chapters = AsyncMock()
    structure_repository.commit = AsyncMock()

    return IngestionService(
        document_repository,
        page_repository,
        structure_repository,
        chunk_repository,
    )


async def test_redetecting_structure_relinks_existing_chunks(monkeypatch) -> None:
    """Re-detecting structure must re-point existing chunks, not orphan them.

    Regression: deleting and recreating Chapter rows left every chunk
    referencing ids that no longer existed, so analysis found no content
    and the job finished with zero topics.
    """
    page_one, page_two = uuid.uuid4(), uuid.uuid4()
    chunks = [
        _FakeChunkRow(uuid.uuid4(), page_one),
        _FakeChunkRow(uuid.uuid4(), page_two),
    ]

    # Both start out pointing at a chapter that is about to be deleted.
    stale = uuid.uuid4()
    chunks[0].chapter_id = stale
    chunks[1].chapter_id = stale

    service = _make_ingestion_service(chunks)

    # Two chapters: page 1 belongs to the first, page 2 to the second.
    detected = [
        _DetectedChapter(1, "Foundations", 1, 1, 0),
        _DetectedChapter(2, "Operations", 2, 2, 1),
    ]
    monkeypatch.setattr(
        "app.services.ingestion.service.detect_structure",
        lambda page_tuples: detected,
    )

    chapters = await service.detect_document_structure(uuid.uuid4())

    service._chunk_repository.relink_to_structure.assert_awaited_once()

    # Assert on the rows themselves: the persisted ids are what matters.
    assert chunks[0].chapter_id == chapters[0].id
    assert chunks[0].section_id is None
    assert chunks[1].chapter_id == chapters[1].id
    assert chunks[1].section_id is None


async def test_relink_assigns_section_when_page_falls_inside_one(
    monkeypatch,
) -> None:
    """A page inside a section's range links to that section id."""
    page_one = uuid.uuid4()
    chunks = [_FakeChunkRow(uuid.uuid4(), page_one)]

    # Pre-set a stale parent so the test also proves a stale id is
    # replaced rather than merely filled in.
    chunks[0].chapter_id = uuid.uuid4()

    service = _make_ingestion_service(chunks)

    detected = [
        _DetectedChapter(
            1,
            "Security",
            1,
            2,
            0,
            sections=[_DetectedSection(2, "TLS", 1, 1, 0)],
        )
    ]
    monkeypatch.setattr(
        "app.services.ingestion.service.detect_structure",
        lambda page_tuples: detected,
    )

    chapters = await service.detect_document_structure(uuid.uuid4())

    assert chunks[0].chapter_id == chapters[0].id
    assert chunks[0].section_id == chapters[0].sections[0].id


async def test_relink_is_skipped_when_no_chunks_exist(monkeypatch) -> None:
    """A document with pages but no chunks yet has nothing to re-link."""
    service = _make_ingestion_service([], page_count=2)

    monkeypatch.setattr(
        "app.services.ingestion.service.detect_structure",
        lambda page_tuples: [_DetectedChapter(1, "Only", 1, 1, 0)],
    )

    await service.detect_document_structure(uuid.uuid4())

    service._chunk_repository.relink_to_structure.assert_not_awaited()


async def test_relink_clears_stale_structure_when_page_outside_chapters(
    monkeypatch,
) -> None:
    """Front matter before the first chapter links to no chapter.

    Leaving the old chapter_id in place would be worse than nulling it:
    the chunk would appear to belong to a chapter it is not in.
    """
    page_one = uuid.uuid4()
    chunks = [_FakeChunkRow(uuid.uuid4(), page_one)]

    # Pretend this chunk was previously linked to a chapter that no
    # longer exists.
    chunks[0].chapter_id = uuid.uuid4()

    service = _make_ingestion_service(chunks)

    detected = [_DetectedChapter(1, "Body", 5, 9, 0)]
    monkeypatch.setattr(
        "app.services.ingestion.service.detect_structure",
        lambda page_tuples: detected,
    )

    await service.detect_document_structure(uuid.uuid4())

    assert chunks[0].chapter_id is None
    assert chunks[0].section_id is None


class _DetectedSection:
    def __init__(self, number, title, start, end, order_index) -> None:
        self.number = number
        self.title = title
        self.start_page = start
        self.end_page = end
        self.order_index = order_index


class _DetectedChapter:
    def __init__(self, number, title, start, end, order_index, sections=None) -> None:
        self.number = number
        self.title = title
        self.start_page = start
        self.end_page = end
        self.order_index = order_index
        self.sections = sections or []


class _FakeJob:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.document_id = uuid.uuid4()
        self.status = IngestionState.PENDING
        self.attempt_count = 0
        self.max_attempts = 3
        self.correlation_id = "test-correlation"
        self.error_message = None


class _FakeSession:
    def __init__(self, job: _FakeJob) -> None:
        self._job = job

    async def get(self, model, pk):
        if model is IngestionJob:
            return self._job
        return Mock()

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def execute(self, *args, **kwargs):
        return Mock()

    async def rollback(self) -> None:
        return None


class _FakeSessionFactory:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def __call__(self) -> _FakeSessionFactory:
        return self

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, *exc_info) -> bool:
        return False


def _patch_worker_repositories(
    monkeypatch,
    *,
    topics: list,
    unlinked_chunks: int = 0,
) -> Mock:
    """Stub worker repositories so processing reaches the analysis guard."""
    chunk_repo = Mock()
    chunk_repo.list_by_document = AsyncMock(return_value=[Mock()])
    chunk_repo.count_unlinked_by_document = AsyncMock(return_value=unlinked_chunks)
    chunk_repo.count_by_document = AsyncMock(return_value={uuid.uuid4(): 10})
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
    structure_repo.list_chapters_by_document = AsyncMock(return_value=[Mock(), Mock()])
    monkeypatch.setattr(
        "app.workers.ingestion_worker.StructureRepository",
        MagicMock(return_value=structure_repo),
    )

    topic_repo = Mock()
    topic_repo.list_by_document = AsyncMock(return_value=topics)
    topic_repo.list_in_reading_order = AsyncMock(return_value=([], {}))
    monkeypatch.setattr(
        "app.workers.ingestion_worker.TopicRepository",
        MagicMock(return_value=topic_repo),
    )

    graph_service = AsyncMock()
    graph_service.build_document_dependencies.return_value = Mock(
        topological_order=[], rejected_cycle_edges=[], unresolved_prerequisites=[]
    )
    monkeypatch.setattr(
        "app.workers.ingestion_worker.DependencyGraphService",
        MagicMock(return_value=graph_service),
    )

    return chunk_repo


async def test_job_fails_when_analysis_produces_no_topics(monkeypatch) -> None:
    """Zero topics must fail the job instead of reporting success.

    Regression: every chapter was skipped as empty, yet the job reached
    COMPLETED and only surfaced later as a mysteriously empty curriculum.
    """
    job = _FakeJob()
    session_factory = _FakeSessionFactory(_FakeSession(job))

    _patch_worker_repositories(monkeypatch, topics=[])

    ingestion_service = AsyncMock()
    monkeypatch.setattr(
        "app.workers.ingestion_worker.IngestionService",
        MagicMock(return_value=ingestion_service),
    )

    analysis = AsyncMock()
    monkeypatch.setattr(
        "app.workers.ingestion_worker.ContentAnalysisService",
        MagicMock(return_value=analysis),
    )

    await _process_job(str(job.id), session_factory, Mock(), Mock())

    assert job.status != IngestionState.COMPLETED
    assert "no topics" in (job.error_message or "")


async def test_empty_analysis_error_names_orphaned_chunks(monkeypatch) -> None:
    """The failure message points at the orphan-link cause when present."""
    job = _FakeJob()
    session_factory = _FakeSessionFactory(_FakeSession(job))

    _patch_worker_repositories(monkeypatch, topics=[], unlinked_chunks=279)

    ingestion_service = AsyncMock()
    monkeypatch.setattr(
        "app.workers.ingestion_worker.IngestionService",
        MagicMock(return_value=ingestion_service),
    )
    monkeypatch.setattr(
        "app.workers.ingestion_worker.ContentAnalysisService",
        MagicMock(return_value=AsyncMock()),
    )

    await _process_job(str(job.id), session_factory, Mock(), Mock())

    message = job.error_message or ""
    assert "chunks_without_chapter=279" in message
    assert "re-run chunking" in message


async def test_successful_retry_clears_previous_error(monkeypatch) -> None:
    """A COMPLETED job must not still show the prior attempt's error.

    Regression: OpenRouter returned empty content on the first attempt,
    the retry succeeded, and the job was left reading as completed with
    "OpenRouter returned empty content" still attached.
    """
    job = _FakeJob()
    job.error_message = "OpenRouter returned empty content."
    session_factory = _FakeSessionFactory(_FakeSession(job))

    _patch_worker_repositories(monkeypatch, topics=[Mock()])

    ingestion_service = AsyncMock()
    monkeypatch.setattr(
        "app.workers.ingestion_worker.IngestionService",
        MagicMock(return_value=ingestion_service),
    )
    monkeypatch.setattr(
        "app.workers.ingestion_worker.ContentAnalysisService",
        MagicMock(return_value=AsyncMock()),
    )

    from app.services.dependency.linker import LinkResolution

    linking = AsyncMock()
    linking.link_document.return_value = LinkResolution(edges={}, rejected=[])
    monkeypatch.setattr(
        "app.workers.ingestion_worker.PrerequisiteLinkingService",
        MagicMock(return_value=linking),
    )

    await _process_job(str(job.id), session_factory, Mock(), Mock())

    assert job.status == IngestionState.COMPLETED
    assert job.error_message is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
