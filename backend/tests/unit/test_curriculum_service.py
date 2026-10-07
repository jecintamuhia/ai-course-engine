"""Unit tests for CurriculumService title/description overrides."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.exceptions import CurriculumValidationError
from app.db.repositories.curriculum import CurriculumRepository
from app.db.repositories.dependencies import DependencyRepository
from app.db.repositories.documents import DocumentRepository
from app.db.repositories.topics import TopicRepository
from app.models.curriculum import Curriculum
from app.models.document import Document, DocumentStatus
from app.services.curriculum.service import CurriculumService
from app.services.planner.four_month_planner import (
    TopicAllocation,
    WeekPlan,
)


def _make_document(prefix: int = 0):
    doc = Document(
        original_filename=f"machine_learning_textbook_v{prefix}.pdf",
        storage_filename=f"storage-{prefix}.pdf",
        storage_path=f"/tmp/storage-{prefix}.pdf",
        mime_type="application/pdf",
        file_extension=".pdf",
        size_bytes=123456,
        sha256_hash=uuid.uuid4().hex,
        version_number=1,
        is_latest_version=True,
        status=DocumentStatus.UPLOADED,
    )
    doc.id = uuid.uuid4()
    doc.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    doc.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
    return doc


def _week_plans(count: int = 16):
    return [
        WeekPlan(
            week_number=week_number,
            allocations=[
                TopicAllocation(
                    topic_id=uuid.uuid4(),
                    title=f"Topic {week_number}A",
                    allocated_minutes=120,
                    difficulty=1,
                    order_index=week_number - 1,
                )
            ],
            learning_objectives=[f"Understand Topic {week_number}A"],
        )
        for week_number in range(1, count + 1)
    ]


def _make_service(*, document=None, plan=None):
    document_repository = AsyncMock(spec=DocumentRepository)
    document_repository.get_by_id.return_value = document or _make_document()
    topic_repository = AsyncMock(spec=TopicRepository)
    topic_repository.list_flat_by_document.return_value = [
        MagicMock(id=uuid.uuid4(), title="Topic A", difficulty=1)
    ]
    dependency_repository = AsyncMock(spec=DependencyRepository)
    dependency_repository.list_by_document.return_value = []
    curriculum_repository = AsyncMock(spec=CurriculumRepository)
    curriculum_repository.latest_version_number.return_value = 4
    curriculum_repository.list_latest_by_document.return_value = []

    planner = MagicMock()
    planner.plan.side_effect = lambda topics, dependencies, config: (
        plan if plan is not None else _week_plans(count=config.total_weeks)
    )

    service = CurriculumService(
        document_repository,
        topic_repository,
        dependency_repository,
        curriculum_repository,
        planner=planner,
    )
    return (
        service,
        document_repository,
        topic_repository,
        dependency_repository,
        curriculum_repository,
        planner,
    )


class TestGenerateCurriculumOverrides:
    @pytest.mark.anyio
    async def test_title_and_description_are_applied(self):
        service, _, _, _, curriculum_repository, _ = _make_service()

        curriculum = await service.generate_curriculum(
            uuid.uuid4(),
            title="  Custom Course Name  ",
            description="A tailored description.",
        )

        assert isinstance(curriculum, Curriculum)
        assert curriculum.title == "Custom Course Name"
        assert curriculum.description == "A tailored description."

    @pytest.mark.anyio
    async def test_title_defaults_to_filename_without_override(self):
        service, _, _, _, curriculum_repository, _ = _make_service()

        curriculum = await service.generate_curriculum(uuid.uuid4())

        assert curriculum.title == "machine_learning_textbook_v0"

    @pytest.mark.anyio
    async def test_description_defaults_to_none(self):
        service, _, _, _, curriculum_repository, _ = _make_service()

        curriculum = await service.generate_curriculum(uuid.uuid4())

        assert curriculum.description is None

    @pytest.mark.anyio
    async def test_whitespace_only_title_falls_back_to_filename(self):
        service, _, _, _, curriculum_repository, _ = _make_service()

        curriculum = await service.generate_curriculum(uuid.uuid4(), title="   ")

        assert curriculum.title == "machine_learning_textbook_v0"

    @pytest.mark.anyio
    async def test_increments_version_number_from_repository(self):
        service, _, _, _, curriculum_repository, _ = _make_service()

        curriculum = await service.generate_curriculum(uuid.uuid4())

        assert curriculum.version_number == 5

    @pytest.mark.anyio
    async def test_supersedes_previous_latest_versions(self):
        service, _, _, _, curriculum_repository, _ = _make_service()
        older = MagicMock()
        curriculum_repository.list_latest_by_document.return_value = [older]

        await service.generate_curriculum(uuid.uuid4())

        curriculum_repository.mark_superseded.assert_awaited_once_with(older)
        curriculum_repository.add.assert_awaited_once()
        curriculum_repository.commit.assert_awaited_once()

    @pytest.mark.anyio
    async def test_topic_links_are_not_appended_twice(self):
        service, _, _, _, _, _ = _make_service()

        curriculum = await service.generate_curriculum(uuid.uuid4())

        assert len(curriculum.units) == 16
        topic_ids = [
            link.topic_id for unit in curriculum.units for link in unit.topic_links
        ]
        assert len(topic_ids) == 16
        assert len(set(topic_ids)) == 16

    @pytest.mark.anyio
    async def test_units_span_exactly_the_requested_total_weeks(self):
        service, _, _, _, _, _ = _make_service()

        curriculum = await service.generate_curriculum(uuid.uuid4(), total_weeks=12)

        assert curriculum.total_weeks == 12
        assert len(curriculum.units) == 12
        assert [unit.week_number for unit in curriculum.units] == list(range(1, 13))

    @pytest.mark.anyio
    async def test_rejects_a_plan_that_does_not_match_total_weeks(self):
        service, _, _, _, _, _ = _make_service(plan=_week_plans(count=3))

        with pytest.raises(CurriculumValidationError, match="do not match"):
            await service.generate_curriculum(uuid.uuid4(), total_weeks=12)
