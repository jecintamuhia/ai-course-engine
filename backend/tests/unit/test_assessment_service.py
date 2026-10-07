"""Unit tests for assessment generation, alignment, and review."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from app.core.config import Settings
from app.core.exceptions import (
    AIOutputValidationError,
    AssessmentNotFound,
    CurriculumValidationError,
)
from app.db.repositories.assessments import AssessmentRepository
from app.db.repositories.chunks import ChunkRepository
from app.db.repositories.curriculum import CurriculumRepository
from app.db.repositories.lessons import LessonRepository
from app.models.assessment import (
    Assessment,
    AssessmentStatus,
    AssessmentType,
)
from app.models.curriculum_unit import CurriculumUnit
from app.models.lesson import Lesson
from app.models.lesson_content_block import LessonBlockType, LessonContentBlock
from app.schemas.ai_assessment import GeneratedAssessment
from app.schemas.assessment import AssessmentItem, AssessmentOption
from app.services.ai.base import LLMProvider
from app.services.assessment.generators import generate_assessment
from app.services.assessment.service import AssessmentService


def _assessment(
    *,
    status: AssessmentStatus = AssessmentStatus.AWAITING_REVIEW,
    curriculum_id: uuid.UUID | None = None,
) -> Assessment:
    return Assessment(
        id=uuid.uuid4(),
        curriculum_id=curriculum_id or uuid.uuid4(),
        title="Quiz",
        description="d",
        assessment_type=AssessmentType.WEEKLY_QUIZ,
        learning_objectives=["LO"],
        estimated_minutes=30,
        items=[],
        status=status,
    )


def _service(repo: AsyncMock | None = None) -> AssessmentService:
    return AssessmentService(
        curriculum_repository=AsyncMock(spec=CurriculumRepository),
        assessment_repository=repo or AsyncMock(spec=AssessmentRepository),
        chunk_repository=AsyncMock(spec=ChunkRepository),
        lesson_repository=AsyncMock(spec=LessonRepository),
        provider=AsyncMock(spec=LLMProvider),
        settings=Settings(),
    )


def _item(
    objective: str,
    *,
    markers: list[str] | None = None,
    correct: bool = True,
) -> AssessmentItem:
    options = [
        AssessmentOption(id="a", text="A"),
        AssessmentOption(id="b", text="B"),
    ]
    return AssessmentItem(
        kind="multiple_choice",
        prompt="Which is right?",
        learning_objective=objective,
        options=options,
        correct_option_id="a" if correct else None,
        correct_answer="A",
        explanation="Because A is correct.",
        source_chunk_markers=markers or ["chunk-marker-1"],
    )


@pytest.mark.anyio
async def test_get_by_id_scopes_to_curriculum():
    assessment = _assessment(curriculum_id=uuid.uuid4())
    repo = AsyncMock(spec=AssessmentRepository)
    repo.get_by_id.return_value = assessment
    service = _service(repo)

    found = await service.get_by_id(assessment.id)
    assert found.id == assessment.id
    assert (
        await service.get_by_id(assessment.id, curriculum_id=assessment.curriculum_id)
    ).id == assessment.id
    with pytest.raises(AssessmentNotFound):
        await service.get_by_id(assessment.id, curriculum_id=uuid.uuid4())


@pytest.mark.anyio
async def test_get_by_id_missing_raises():
    repo = AsyncMock(spec=AssessmentRepository)
    repo.get_by_id.return_value = None
    service = _service(repo)

    with pytest.raises(AssessmentNotFound):
        await service.get_by_id(uuid.uuid4())


@pytest.mark.anyio
async def test_review_approve_sets_status_and_reviewer():
    assessment = _assessment()
    repo = AsyncMock(spec=AssessmentRepository)
    repo.get_by_id.return_value = assessment
    service = _service(repo)

    updated = await service.review(
        assessment.id,
        decision="approved",
        reviewer_name="Dr. Smith",
        comments="Looks good.",
    )

    assert updated.status == AssessmentStatus.APPROVED
    assert updated.reviewer_name == "Dr. Smith"
    assert updated.review_comments == "Looks good."
    repo.commit.assert_awaited()


@pytest.mark.anyio
async def test_review_rejects_and_blocks_rejecting_approved():
    assessment = _assessment(status=AssessmentStatus.APPROVED)
    repo = AsyncMock(spec=AssessmentRepository)
    repo.get_by_id.return_value = assessment
    service = _service(repo)

    assert (
        await service.review(
            assessment.id, decision="approved", reviewer_name=None, comments=None
        )
    ).status == AssessmentStatus.APPROVED

    with pytest.raises(CurriculumValidationError):
        await service.review(
            assessment.id, decision="rejected", reviewer_name=None, comments=None
        )


def test_build_alignment_prefers_exact_objective_match():
    unit = CurriculumUnit(
        id=uuid.uuid4(),
        curriculum_id=uuid.uuid4(),
        week_number=2,
        title="Week 2",
        description="u",
        learning_objectives=[],
        estimated_workload_minutes=120,
        order_index=0,
    )

    exact = Lesson(
        id=uuid.uuid4(),
        curriculum_id=uuid.uuid4(),
        curriculum_unit_id=unit.id,
        topic_id=uuid.uuid4(),
        week_number=2,
        order_index=0,
        title="Exact Lesson",
        description="d",
        learning_objectives=["Build a decision tree"],
        estimated_workload_minutes=60,
    )
    partial = Lesson(
        id=uuid.uuid4(),
        curriculum_id=uuid.uuid4(),
        curriculum_unit_id=unit.id,
        topic_id=uuid.uuid4(),
        week_number=2,
        order_index=1,
        title="Partial Lesson",
        description="d",
        learning_objectives=["Understand trees in general"],
        estimated_workload_minutes=60,
    )
    partial.content_blocks = [
        LessonContentBlock(
            id=uuid.uuid4(),
            lesson_id=partial.id,
            order_index=0,
            block_type=LessonBlockType.ACTIVITY,
            title="Build a small tree",
            payload={"content": "go"},
        )
    ]

    result = GeneratedAssessment(
        title="Quiz",
        description="d",
        estimated_minutes=30,
        items=[_item("Build a decision tree")],
    )

    service = _service()
    alignment = service._build_alignment(result, [partial, exact])

    assert alignment[0].lesson_id == exact.id
    assert alignment[0].unit_week == 2
    assert alignment[0].evidence == []

    result2 = result.model_copy(update={"items": [_item("Understand trees")]})
    alignment2 = service._build_alignment(result2, [partial, exact])
    assert alignment2[0].lesson_id == partial.id
    assert alignment2[0].evidence == ["Build a small tree"]


def test_collect_markers_deduplicates_and_resolves():
    service = _service()
    result = GeneratedAssessment(
        title="Quiz",
        description="d",
        estimated_minutes=30,
        items=[
            _item("LO1", markers=["m1", "m2"]),
            _item("LO2", markers=["m1"]),
        ],
    )
    marker_map = {
        "m1": uuid.uuid4(),
        "m2": uuid.uuid4(),
        "m3": uuid.uuid4(),
    }

    markers = service._collect_markers(result, marker_map)

    assert markers == [str(marker_map["m1"]), str(marker_map["m2"])]


@pytest.mark.anyio
async def test_generate_assessment_validates_and_trims_items():
    items = [_item("LO1", correct=False) for _ in range(25)]
    result = GeneratedAssessment(
        title="Quiz",
        description="d",
        estimated_minutes=30,
        items=items,
    )

    provider = AsyncMock(spec=LLMProvider)
    provider.complete_structured.return_value = result
    settings = Settings(content_max_tokens=2000)

    validated = await generate_assessment(
        provider,
        settings,
        assessment_type=AssessmentType.WEEKLY_QUIZ,
        unit_title="Week 1",
        learning_objectives=["LO1"],
        annotated_text="[CHUNK:1] text",
    )

    assert len(validated.items) == 20
    assert validated.items[0].correct_option_id is None


@pytest.mark.anyio
async def test_generate_assessment_rejects_bad_correct_option():
    result = GeneratedAssessment(
        title="Quiz",
        description="d",
        estimated_minutes=30,
        items=[_item("LO1", correct=True)],
    )
    bad = result.model_copy()
    bad.items[0].correct_option_id = "zzz"

    provider = AsyncMock(spec=LLMProvider)
    provider.complete_structured.return_value = bad
    settings = Settings(content_max_tokens=2000)

    with pytest.raises(AIOutputValidationError):
        await generate_assessment(
            provider,
            settings,
            assessment_type=AssessmentType.WEEKLY_QUIZ,
            unit_title="Week 1",
            learning_objectives=["LO1"],
            annotated_text="text",
        )
