"""Unit tests for the QA service (run, gate, and coverage report)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from app.core.config import Settings
from app.core.exceptions import ContentQAError, CurriculumNotFound
from app.db.repositories.assessments import AssessmentRepository
from app.db.repositories.courses import CourseRepository
from app.db.repositories.curriculum import CurriculumRepository
from app.db.repositories.dependencies import DependencyRepository
from app.db.repositories.documents import DocumentRepository
from app.db.repositories.lessons import LessonRepository
from app.db.repositories.quality_reports import QualityReportRepository
from app.db.repositories.structure import StructureRepository
from app.db.repositories.topics import TopicRepository
from app.models.assessment import Assessment, AssessmentStatus, AssessmentType
from app.models.concept import Concept
from app.models.curriculum import Curriculum, CurriculumStatus
from app.models.curriculum_unit import CurriculumUnit
from app.models.curriculum_unit_topic import CurriculumUnitTopic
from app.models.document import Document, DocumentStatus
from app.models.lesson import Lesson
from app.models.lesson_content_block import LessonBlockType, LessonContentBlock
from app.models.topic import ContentLevel, Topic, TopicImportance
from app.schemas.qa import QAFinding
from app.services.qa.service import (
    QADependencies,
    QAService,
    area_status,
    verdict_for_findings,
)


def _settings() -> Settings:
    return Settings(
        qa_min_major_prose_chars=100,
        qa_min_supporting_prose_chars=50,
    )


def _topic(title: str, *, importance: str | None = None) -> Topic:
    topic = Topic(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        title=title,
        difficulty=2,
        estimated_workload_minutes=120,
        order_index=0,
    )
    topic.importance = importance or TopicImportance.MAJOR.value
    return topic


def _unit(topic: Topic) -> tuple[CurriculumUnit, CurriculumUnitTopic]:
    unit = CurriculumUnit(
        id=uuid.uuid4(),
        curriculum_id=uuid.uuid4(),
        week_number=1,
        title="Week 1",
        description="unit",
        learning_objectives=["LO"],
        estimated_workload_minutes=120,
        order_index=0,
    )
    link = CurriculumUnitTopic(
        id=uuid.uuid4(), curriculum_unit_id=unit.id, topic_id=topic.id, order_index=0
    )
    unit.topic_links = [link]
    return unit, link


def _block(block_type: LessonBlockType, payload: dict) -> LessonContentBlock:
    return LessonContentBlock(
        id=uuid.uuid4(),
        lesson_id=uuid.uuid4(),
        order_index=0,
        block_type=block_type,
        title=block_type.value,
        payload=payload,
    )


def _healthy_curriculum() -> tuple[Curriculum, Topic, Lesson, Assessment]:
    curriculum = Curriculum(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        title="Design of Experiments",
        description=None,
        total_weeks=16,
        learning_days_per_week=5,
        hours_per_day=2,
        max_weekly_workload_minutes=600,
        min_topic_allocation_minutes=60,
        max_topic_allocation_minutes=240,
    )
    topic = _topic("Design of Experiments")
    topic.content_level = ContentLevel.BASIC
    topic.concepts = [
        Concept(
            id=uuid.uuid4(),
            topic_id=topic.id,
            name="Design of Experiments",
            description="core idea",
            order_index=0,
            definition="A structured approach to planning experiments.",
            terminology=["factor", "response"],
            procedures=[],
            formulas=[],
            worked_examples=[],
            exercises=[],
            misconceptions=[],
            provenance=[],
        )
    ]
    unit, _ = _unit(topic)
    curriculum.units = [unit]

    lesson = Lesson(
        id=uuid.uuid4(),
        curriculum_id=curriculum.id,
        curriculum_unit_id=unit.id,
        topic_id=topic.id,
        week_number=1,
        order_index=0,
        title="Design of Experiments Lesson",
        description="d",
        learning_objectives=["LO"],
        estimated_workload_minutes=60,
    )
    lesson.content_blocks = [
        _block(
            LessonBlockType.TEXT,
            {
                "content": "x" * 500,
                "source_chunk_markers": ["marker-1"],
            },
        ),
        _block(
            LessonBlockType.KNOWLEDGE_CHECK,
            {
                "content": "Question?",
                "source_chunk_markers": ["marker-1"],
            },
        ),
        _block(
            LessonBlockType.ACTIVITY,
            {
                "content": "Do the activity",
                "source_chunk_markers": ["marker-1"],
            },
        ),
        _block(
            LessonBlockType.EXTERNAL_RESOURCE,
            {
                "url": "https://example.com/doe",
                "validated_at": "2026-01-01T00:00:00+00:00",
            },
        ),
        _block(
            LessonBlockType.VIDEO,
            {
                "video_id": "dQw4w9WgXcQ",
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            },
        ),
    ]

    assessment = Assessment(
        id=uuid.uuid4(),
        curriculum_id=curriculum.id,
        curriculum_unit_id=unit.id,
        week_number=1,
        title="Week 1 Quiz",
        description="",
        assessment_type=AssessmentType.WEEKLY_QUIZ,
        learning_objectives=["LO"],
        estimated_minutes=30,
        items=[{"prompt": "?"}],
        status=AssessmentStatus.AWAITING_REVIEW,
    )
    return curriculum, topic, lesson, assessment


def _deps(curriculum, topics, lessons, assessments, **overrides):
    deps = {
        "curriculum": AsyncMock(spec=CurriculumRepository),
        "dependencies": AsyncMock(spec=DependencyRepository),
        "topics": AsyncMock(spec=TopicRepository),
        "lessons": AsyncMock(spec=LessonRepository),
        "structure": AsyncMock(spec=StructureRepository),
        "documents": AsyncMock(spec=DocumentRepository),
        "quality_reports": AsyncMock(spec=QualityReportRepository),
        "assessments": AsyncMock(spec=AssessmentRepository),
        "courses": AsyncMock(spec=CourseRepository),
    }
    deps["curriculum"].get_by_id.return_value = curriculum
    deps["topics"].list_flat_by_document.return_value = topics
    deps["dependencies"].list_by_document.return_value = []
    deps["lessons"].list_by_curriculum.return_value = lessons
    deps["assessments"].list_by_curriculum.return_value = assessments
    deps["structure"].list_chapters_by_document.return_value = []
    deps["courses"].get_by_curriculum.return_value = None
    deps["quality_reports"].get_latest_by_curriculum.return_value = None
    for key, value in overrides.items():
        deps[key] = value
    return QADependencies(**deps)


async def _seed_report(report) -> None:
    """Simulate ORM flush defaults (id/created_at) applied by add+commit."""
    report.id = uuid.uuid4()
    report.created_at = datetime(2026, 1, 1, tzinfo=UTC)


def _qa_service(deps: QADependencies) -> QAService:
    service = QAService(deps, _settings())

    async def _seed(report):
        await _seed_report(report)

    deps.quality_reports.add.side_effect = _seed
    deps.quality_reports.commit = AsyncMock()
    return service


def test_verdict_for_findings_ordering():
    assert verdict_for_findings([]) == "pass"
    assert (
        verdict_for_findings(
            [QAFinding(rule="r", code="c", severity="info", message="m")]
        )
        == "pass"
    )
    assert (
        verdict_for_findings(
            [QAFinding(rule="r", code="c", severity="warning", message="m")]
        )
        == "warning"
    )
    assert (
        verdict_for_findings(
            [
                QAFinding(rule="r", code="c", severity="error", message="m"),
                QAFinding(rule="r", code="c", severity="warning", message="m"),
            ]
        )
        == "fail"
    )
    assert area_status([]).status == "pass"


@pytest.mark.anyio
async def test_run_curriculum_qa_passes_and_persists():
    curriculum, topic, lesson, assessment = _healthy_curriculum()
    service = _qa_service(_deps(curriculum, [topic], [lesson], [assessment]))

    response = await service.run_curriculum_qa(curriculum.id)

    assert response.blocked is False
    assert response.report.verdict == "pass"
    assert response.report.version_number == 1
    assert "coverage" in response.report.summary


@pytest.mark.anyio
async def test_persisted_quality_report_is_json_serializable():
    """Regression: the JSONB columns must hold plain JSON, not Pydantic models.

    The repositories are mocked here, so nothing validates the payload before
    it reaches Postgres. Assert real serializability so a JSONB write can
    never raise TypeError mid-request (which surfaced as an HTTP 500 on
    curriculum review).
    """
    curriculum, topic, lesson, assessment = _healthy_curriculum()
    deps = _deps(curriculum, [topic], [lesson], [assessment])
    service = _qa_service(deps)

    await service.run_curriculum_qa(curriculum.id)

    persisted = deps.quality_reports.add.call_args.args[0]
    for column in ("areas", "findings", "summary"):
        value = getattr(persisted, column)
        assert json.dumps(value), f"{column} must be JSON-serializable"
    for domain, status in persisted.areas.items():
        assert set(status) == {"status", "findings"}, domain


@pytest.mark.anyio
async def test_run_curriculum_qa_fails_and_blocks_on_empty_inventory():
    curriculum = Curriculum(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        title="Empty",
        description=None,
        total_weeks=16,
        learning_days_per_week=5,
        hours_per_day=2,
        max_weekly_workload_minutes=600,
        min_topic_allocation_minutes=60,
        max_topic_allocation_minutes=240,
    )
    curriculum.units = []
    service = _qa_service(_deps(curriculum, [], [], []))

    response = await service.run_curriculum_qa(curriculum.id)

    assert response.blocked is True
    assert response.report.verdict == "fail"
    assert any(f.code == "no_canonical_topics" for f in response.report.findings)


@pytest.mark.anyio
async def test_blocking_qa_demotes_published_curriculum_for_recovery():
    curriculum = Curriculum(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        title="Previously published but incomplete",
        description=None,
        total_weeks=16,
        learning_days_per_week=5,
        hours_per_day=2,
        max_weekly_workload_minutes=600,
        min_topic_allocation_minutes=60,
        max_topic_allocation_minutes=240,
        status=CurriculumStatus.PUBLISHED,
    )
    curriculum.units = []
    service = _qa_service(_deps(curriculum, [], [], []))

    response = await service.run_curriculum_qa(curriculum.id)

    assert response.blocked is True
    assert curriculum.status == CurriculumStatus.APPROVED


@pytest.mark.anyio
async def test_assert_qa_pass_raises_on_fail():
    curriculum = Curriculum(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        title="Empty",
        description=None,
        total_weeks=16,
        learning_days_per_week=5,
        hours_per_day=2,
        max_weekly_workload_minutes=600,
        min_topic_allocation_minutes=60,
        max_topic_allocation_minutes=240,
    )
    curriculum.units = []
    service = _qa_service(_deps(curriculum, [], [], []))

    with pytest.raises(ContentQAError):
        await service.assert_qa_pass(curriculum.id)


@pytest.mark.anyio
async def test_assert_qa_pass_accepts_healthy_curriculum():
    curriculum, topic, lesson, assessment = _healthy_curriculum()
    service = _qa_service(_deps(curriculum, [topic], [lesson], [assessment]))

    await service.assert_qa_pass(curriculum.id)  # must not raise


@pytest.mark.anyio
async def test_build_coverage_report():
    curriculum, topic, lesson, _ = _healthy_curriculum()

    document = Document(
        original_filename="textbook.pdf",
        storage_filename="s.pdf",
        storage_path="/tmp/s.pdf",
        mime_type="application/pdf",
        file_extension=".pdf",
        size_bytes=100,
        sha256_hash=uuid.uuid4().hex,
        version_number=1,
        is_latest_version=True,
        status=DocumentStatus.UPLOADED,
    )
    document.id = curriculum.document_id

    deps = _deps(curriculum, [topic], [lesson], [])
    deps.documents.get_by_id.return_value = document
    service = QAService(deps, _settings())

    report = await service.build_coverage_report(curriculum.id)

    assert report.document_id == document.id
    assert report.curriculum_id == curriculum.id
    assert report.document_title == "textbook.pdf"
    assert report.topic_count == 1
    assert report.mapped_topic_count == 1
    assert report.coverage_percent == 100.0
    assert report.lesson_count == 1
    assert report.duplicate_topics_removed == 0
    assert report.resource_count == 1
    assert report.video_count == 1
    assert report.activity_count == 1
    assert report.knowledge_check_count == 1
    assert report.topics[0].title == "Design of Experiments"
    assert report.topics[0].mapped is True
    assert report.topics[0].has_lesson is True


@pytest.mark.anyio
async def test_build_coverage_report_raises_without_context():
    service = QAService(
        _deps(
            Curriculum(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                title="x",
                description=None,
                total_weeks=16,
                learning_days_per_week=5,
                hours_per_day=2,
                max_weekly_workload_minutes=600,
                min_topic_allocation_minutes=60,
                max_topic_allocation_minutes=240,
            ),
            [],
            [],
            [],
        ),
        _settings(),
    )
    service._deps.curriculum = AsyncMock(spec=CurriculumRepository)
    service._deps.curriculum.get_by_id.return_value = None

    with pytest.raises(CurriculumNotFound):
        await service.build_coverage_report(uuid.uuid4())
