"""Unit tests for OverviewService (mocked repositories, no I/O)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.models.curriculum import CurriculumStatus
from app.services.overview import OverviewService


def _make_document(prefix: int = 0):
    doc = MagicMock()
    doc.id = uuid.uuid4()
    doc.original_filename = f"textbook-{prefix}.pdf"
    return doc


def _make_service():
    document_repository = AsyncMock()
    page_repository = AsyncMock()
    structure_repository = AsyncMock()
    chunk_repository = AsyncMock()
    topic_repository = AsyncMock()
    curriculum_repository = AsyncMock()
    ingestion_job_repository = AsyncMock()
    course_repository = AsyncMock()

    service = OverviewService(
        document_repository,
        page_repository,
        structure_repository,
        chunk_repository,
        topic_repository,
        curriculum_repository,
        ingestion_job_repository,
        course_repository,
    )
    return (
        service,
        document_repository,
        page_repository,
        structure_repository,
        chunk_repository,
        topic_repository,
        curriculum_repository,
        ingestion_job_repository,
        course_repository,
    )


class TestListOverviews:
    @pytest.mark.anyio
    async def test_builds_per_document_overview(self):
        (
            service,
            document_repository,
            page_repository,
            structure_repository,
            chunk_repository,
            topic_repository,
            curriculum_repository,
            ingestion_job_repository,
            _,
        ) = _make_service()

        doc = _make_document(1)
        job = MagicMock()
        job.status = "completed"

        document_repository.list_latest.return_value = [doc]
        page_repository.count_by_document.return_value = {doc.id: 9}
        structure_repository.count_by_document.return_value = {doc.id: 8}
        chunk_repository.count_by_document.return_value = {doc.id: 13}
        topic_repository.count_by_document.return_value = {doc.id: 5}
        curriculum_repository.count_latest_by_document.return_value = {doc.id: 2}
        ingestion_job_repository.latest_by_document.return_value = job

        overviews = await service.list_overviews(limit=100)

        assert len(overviews) == 1
        overview = overviews[0]
        assert overview["document"] is doc
        assert overview["page_count"] == 9
        assert overview["chapter_count"] == 8
        assert overview["chunk_count"] == 13
        assert overview["topic_count"] == 5
        assert overview["curriculum_count"] == 2
        assert overview["latest_job"] is job
        ingestion_job_repository.latest_by_document.assert_awaited_once_with(doc.id)

    @pytest.mark.anyio
    async def test_missing_counts_default_to_zero(self):
        (
            service,
            document_repository,
            page_repository,
            structure_repository,
            chunk_repository,
            topic_repository,
            curriculum_repository,
            ingestion_job_repository,
            _,
        ) = _make_service()

        doc = _make_document(2)
        document_repository.list_latest.return_value = [doc]
        for repository in (
            page_repository,
            structure_repository,
            chunk_repository,
            topic_repository,
        ):
            repository.count_by_document.return_value = {}
        curriculum_repository.count_latest_by_document.return_value = {}
        ingestion_job_repository.latest_by_document.return_value = None

        overviews = await service.list_overviews()

        overview = overviews[0]
        assert overview["page_count"] == 0
        assert overview["chapter_count"] == 0
        assert overview["chunk_count"] == 0
        assert overview["topic_count"] == 0
        assert overview["curriculum_count"] == 0
        assert overview["latest_job"] is None

    @pytest.mark.anyio
    async def test_limit_slices_the_result(self):
        (
            service,
            document_repository,
            page_repository,
            structure_repository,
            chunk_repository,
            topic_repository,
            curriculum_repository,
            ingestion_job_repository,
            _,
        ) = _make_service()

        docs = [_make_document(i) for i in range(5)]
        document_repository.list_latest.return_value = docs
        for repository in (
            page_repository,
            structure_repository,
            chunk_repository,
            topic_repository,
        ):
            repository.count_by_document.return_value = {}
        curriculum_repository.count_latest_by_document.return_value = {}
        ingestion_job_repository.latest_by_document.return_value = None

        overviews = await service.list_overviews(limit=3)

        assert [overview["document"] for overview in overviews] == docs[:3]


class TestDashboard:
    @pytest.mark.anyio
    async def test_aggregates_totals(self):
        (
            service,
            document_repository,
            _,
            _,
            _,
            _,
            curriculum_repository,
            ingestion_job_repository,
            course_repository,
        ) = _make_service()

        document_repository.list_latest.return_value = [
            _make_document(i) for i in range(3)
        ]
        ingestion_job_repository.count_in_progress.return_value = 2

        status_counts = {
            CurriculumStatus.DRAFT: 1,
            CurriculumStatus.AWAITING_REVIEW: 4,
            CurriculumStatus.APPROVED: 2,
            CurriculumStatus.REJECTED: 3,
            CurriculumStatus.PUBLISHED: 6,
        }
        curriculum_repository.count_by_status.side_effect = lambda status: (
            status_counts[status]
        )
        course_repository.count_all.return_value = 5

        stats = await service.dashboard(moodle_status={"connected": True})

        assert stats["documents_total"] == 3
        assert stats["documents_processing"] == 2
        assert stats["curricula_total"] == 16
        assert stats["curricula_pending_review"] == 4
        assert stats["curricula_approved"] == 2
        assert stats["curricula_published"] == 6
        assert stats["courses_published"] == 5
        assert stats["moodle"] == {"connected": True}

    @pytest.mark.anyio
    async def test_moodle_status_may_be_none(self):
        (
            service,
            document_repository,
            _,
            _,
            _,
            _,
            curriculum_repository,
            ingestion_job_repository,
            course_repository,
        ) = _make_service()

        document_repository.list_latest.return_value = []
        ingestion_job_repository.count_in_progress.return_value = 0
        curriculum_repository.count_by_status.side_effect = lambda status: 0
        course_repository.count_all.return_value = 0

        stats = await service.dashboard()

        assert stats["documents_total"] == 0
        assert stats["documents_processing"] == 0
        assert stats["curricula_total"] == 0
        assert stats["courses_published"] == 0
        assert stats["moodle"] is None
