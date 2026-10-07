"""Unit tests for CourseContentService lesson-generation orchestration."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from app.core.config import Settings
from app.core.exceptions import AIOutputValidationError, CurriculumUnitNotFound
from app.models.chunks import Chunk
from app.models.curriculum_unit import CurriculumUnit
from app.models.curriculum_unit_topic import CurriculumUnitTopic
from app.models.lesson import Lesson, LessonStatus
from app.models.lesson_content_block import LessonBlockType
from app.models.topic import Topic
from app.models.topic_source_chunk import TopicSourceChunk
from app.schemas.ai_content import (
    ActivityGenerationResult,
    DiagramGenerationResult,
    DiagramNode,
    GeneratedActivity,
    GeneratedDiagram,
    GeneratedKnowledgeCheck,
    GeneratedLesson,
    GeneratedTextBlock,
    KnowledgeCheckGenerationResult,
    LessonGenerationResult,
    ResourceCandidateResult,
)
from app.schemas.course_content import ExternalResourcePayload
from app.services.course_content.service import (
    CourseContentService,
    _resolved_payload_chunk_ids,
)

_TIMELINE: list[str] = []


def _reset_timeline() -> None:
    _TIMELINE.clear()


def _chunk(content: str, index: int) -> Chunk:
    return Chunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        page_id=uuid.uuid4(),
        document_index=index,
        page_index=index,
        content=content,
        char_count=len(content),
        content_hash="fake",
    )


def _topic(title: str, chunk_ids: list[uuid.UUID]) -> Topic:
    topic = Topic(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        title=title,
        learning_objectives=[f"Objective for {title}"],
        difficulty=1,
        estimated_workload_minutes=60,
        order_index=0,
    )
    topic.source_chunk_links = [
        TopicSourceChunk(topic_id=topic.id, chunk_id=chunk_id) for chunk_id in chunk_ids
    ]
    return topic


def _unit(topics: list[Topic]) -> CurriculumUnit:
    unit = CurriculumUnit(
        id=uuid.uuid4(),
        curriculum_id=uuid.uuid4(),
        week_number=1,
        title="Week 1",
        description="First week.",
        learning_objectives=[],
        estimated_workload_minutes=120,
        order_index=0,
    )
    unit.topic_links = [
        CurriculumUnitTopic(
            id=uuid.uuid4(),
            curriculum_unit_id=unit.id,
            topic_id=topic.id,
            order_index=index,
            topic=topic,
        )
        for index, topic in enumerate(topics)
    ]
    return unit


class _FakeCurriculumRepository:
    def __init__(self, unit: CurriculumUnit) -> None:
        self._unit = unit

    async def get_unit_with_lesson_context(self, curriculum_unit_id):
        if self._unit.id != curriculum_unit_id:
            return None
        return self._unit


class _FakeChunkRepository:
    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks_by_id = {chunk.id: chunk for chunk in chunks}

    async def get_by_ids(self, chunk_ids: list[uuid.UUID]) -> list[Chunk]:
        return [
            self._chunks_by_id[cid] for cid in chunk_ids if cid in self._chunks_by_id
        ]

    async def commit(self) -> None:
        _TIMELINE.append("chunk_commit")


class _FakeLessonRepository:
    def __init__(self, existing: list[Lesson] | None = None) -> None:
        self.existing = existing or []
        self.added: list[Lesson] = []

    async def list_by_unit(self, curriculum_unit_id: uuid.UUID) -> list[Lesson]:
        return list(self.existing)

    async def delete_not_approved_by_unit(self, curriculum_unit_id: uuid.UUID) -> None:
        _TIMELINE.append("delete_lessons")

    async def add(self, lesson: Lesson) -> Lesson:
        _TIMELINE.append("add_lesson")
        self.added.append(lesson)
        return lesson

    async def add_source_links(self, links) -> list:
        _TIMELINE.append("add_source_links")
        return list(links)

    async def commit(self) -> None:
        _TIMELINE.append("lesson_commit")


class _RecordingLLM:
    def __init__(
        self, fail_diagrams: bool = False, heading_content: str = "Deep dive"
    ) -> None:
        self._fail_diagrams = fail_diagrams
        self._heading_content = heading_content

    async def complete_structured(self, **kwargs):
        _TIMELINE.append("llm_call")
        response_model = kwargs["response_model"]
        if response_model is LessonGenerationResult:
            return LessonGenerationResult(
                lesson=GeneratedLesson(
                    title="Intro to Alpha",
                    description="Covers the essentials of Alpha.",
                    learning_objectives=["Explain Alpha."],
                    estimated_workload_minutes=40,
                    blocks=[
                        GeneratedTextBlock(
                            kind="text",
                            content="Alpha is fundamental.",
                            source_chunk_markers=["C1", "C9"],
                        ),
                        GeneratedTextBlock(
                            kind="heading",
                            content=self._heading_content,
                            heading_level=2,
                        ),
                        GeneratedTextBlock(kind="summary", content="Wrapped up."),
                    ],
                )
            )
        if response_model is DiagramGenerationResult:
            if self._fail_diagrams:
                raise AIOutputValidationError("No edges validate.")
            return DiagramGenerationResult(
                diagrams=[
                    GeneratedDiagram(
                        title="Alpha map",
                        diagram_type="concept_map",
                        caption="Alpha concepts.",
                        nodes=[DiagramNode(id="n1", label="Alpha")],
                        edges=[],
                    )
                ]
            )
        if response_model is KnowledgeCheckGenerationResult:
            return KnowledgeCheckGenerationResult(
                checks=[
                    GeneratedKnowledgeCheck(
                        question="What is Alpha?",
                        options=[
                            {"id": "o1", "text": "Yes"},
                            {"id": "o2", "text": "No"},
                        ],
                        correct_option_id="o1",
                        explanation="Because Alpha.",
                        difficulty="easy",
                    )
                ]
            )
        if response_model is ActivityGenerationResult:
            return ActivityGenerationResult(
                activities=[
                    GeneratedActivity(
                        kind="practice_exercise",
                        title="Try Alpha",
                        instructions="Practice.",
                        estimated_minutes=15,
                    )
                ]
            )
        if response_model is ResourceCandidateResult:
            return ResourceCandidateResult(candidates=[])
        raise AssertionError(f"Unexpected response model {response_model!r}")

    async def complete_text(self, **kwargs) -> str:
        return ""


def _settings() -> Settings:
    return Settings(
        youtube_api_key="",
        content_max_lessons_per_week=10,
        content_max_resources=0,
        content_max_diagrams=2,
        content_max_knowledge_checks=3,
        content_max_activities=2,
        content_max_tokens=4000,
        ai_max_context_chars=100_000,
        content_resource_timeout_seconds=2,
    )


def _make_service(
    unit: CurriculumUnit,
    chunks: list[Chunk],
    *,
    existing: list[Lesson] | None = None,
    heading_content: str = "Deep dive",
) -> tuple[CourseContentService, _FakeLessonRepository]:
    lesson_repository = _FakeLessonRepository(existing)
    service = CourseContentService(
        _FakeCurriculumRepository(unit),
        _FakeChunkRepository(chunks),
        lesson_repository,
        _RecordingLLM(heading_content=heading_content),
        settings=_settings(),
    )
    return service, lesson_repository


def _existing_lesson(topic_id: uuid.UUID) -> Lesson:
    return Lesson(
        curriculum_id=uuid.uuid4(),
        curriculum_unit_id=uuid.uuid4(),
        topic_id=topic_id,
        week_number=1,
        order_index=0,
        title="Approved lesson",
        description="Already good.",
        learning_objectives=["A"],
        estimated_workload_minutes=20,
        status=LessonStatus.APPROVED,
        generation_errors=[],
    )


async def test_no_db_write_precedes_llm_call() -> None:
    _reset_timeline()
    chunk = _chunk("Alpha source text.", 0)
    unit = _unit([_topic("Alpha Topic", [chunk.id])])
    service, _ = _make_service(unit, [chunk])

    await service.generate_week(unit.id)

    assert _TIMELINE.index("llm_call") > _TIMELINE.index("chunk_commit")
    assert _TIMELINE.index("delete_lessons") > _TIMELINE.index("llm_call")
    assert _TIMELINE.index("add_lesson") > _TIMELINE.index("llm_call")


async def test_generated_lesson_is_awaiting_review_with_blocks() -> None:
    chunk = _chunk("Alpha source text.", 0)
    unit = _unit([_topic("Alpha Topic", [chunk.id])])
    service, lesson_repository = _make_service(unit, [chunk])

    result = await service.generate_week(unit.id)

    lessons = lesson_repository.added
    assert len(lessons) == 1
    lesson = lessons[0]
    assert lesson.status == LessonStatus.AWAITING_REVIEW
    assert lesson.topic_id == unit.topic_links[0].topic_id
    assert lesson.week_number == 1
    block_types = [block.block_type for block in lesson.content_blocks]
    assert LessonBlockType.TEXT in block_types
    assert LessonBlockType.DIAGRAM in block_types
    assert LessonBlockType.KNOWLEDGE_CHECK in block_types
    assert LessonBlockType.ACTIVITY in block_types
    assert len(result["errors"]) == 0


async def test_long_heading_text_is_preserved_as_prose_block() -> None:
    chunk = _chunk("Alpha source text.", 0)
    unit = _unit([_topic("Alpha Topic", [chunk.id])])
    long_content = "Source-grounded explanation. " * 15
    service, lesson_repository = _make_service(
        unit, [chunk], heading_content=long_content
    )

    await service.generate_week(unit.id)

    lesson = lesson_repository.added[0]
    text_blocks = [
        block
        for block in lesson.content_blocks
        if block.block_type == LessonBlockType.TEXT
    ]
    assert any(block.payload["content"] == long_content for block in text_blocks)


async def test_hallucinated_markers_dropped_and_provenance_linked() -> None:
    chunk = _chunk("Alpha source text.", 0)
    unit = _unit([_topic("Alpha Topic", [chunk.id])])
    service, lesson_repository = _make_service(unit, [chunk])

    await service.generate_week(unit.id)

    lesson = lesson_repository.added[0]
    text_block = next(
        block
        for block in lesson.content_blocks
        if block.block_type == LessonBlockType.TEXT
    )
    assert text_block.payload["source_chunk_markers"] == [str(chunk.id)]
    assert [link.chunk_id for link in lesson.source_chunk_links] == [chunk.id]
    assert _resolved_payload_chunk_ids(text_block) == [chunk.id]


async def test_approved_lesson_is_preserved_and_topic_skipped() -> None:
    chunk = _chunk("Alpha source text.", 0)
    topic_a = _topic("Alpha Topic", [chunk.id])
    topic_b = _topic("Beta Topic", [chunk.id])
    unit = _unit([topic_a, topic_b])
    approved = _existing_lesson(topic_a.id)
    service, lesson_repository = _make_service(unit, [chunk], existing=[approved])

    result = await service.generate_week(unit.id)

    assert any(
        "lesson already exists" in item["reason"]
        and str(topic_a.id) == str(item["topic_id"])
        for item in result["skipped"]
    )
    assert [lesson.topic_id for lesson in lesson_repository.added] == [topic_b.id]


async def test_resume_preserves_unapproved_lesson_and_fills_missing_topic() -> None:
    _reset_timeline()
    chunk = _chunk("Alpha source text.", 0)
    topic_a = _topic("Alpha Topic", [chunk.id])
    topic_b = _topic("Beta Topic", [chunk.id])
    unit = _unit([topic_a, topic_b])
    existing = _existing_lesson(topic_a.id)
    existing.status = LessonStatus.AWAITING_REVIEW
    service, lesson_repository = _make_service(unit, [chunk], existing=[existing])

    result = await service.generate_week(unit.id, preserve_existing=True)

    assert result["generated"]
    assert [lesson.topic_id for lesson in lesson_repository.added] == [topic_b.id]
    assert "delete_lessons" not in _TIMELINE


async def test_unsourced_topic_is_skipped_not_fabricated() -> None:
    orphan = _topic("Orphan Topic", [])
    orphan_unit = _unit([orphan])
    service, lesson_repository = _make_service(orphan_unit, [])

    result = await service.generate_week(orphan_unit.id)

    assert any("No source chunks" in item["reason"] for item in result["skipped"])
    assert lesson_repository.added == []


async def test_diagram_component_failure_records_error_but_keeps_lesson() -> None:
    chunk = _chunk("Alpha source text.", 0)
    unit = _unit([_topic("Alpha Topic", [chunk.id])])
    lesson_repository = _FakeLessonRepository()
    service = CourseContentService(
        _FakeCurriculumRepository(unit),
        _FakeChunkRepository([chunk]),
        lesson_repository,
        _RecordingLLM(fail_diagrams=True),
        settings=_settings(),
    )

    result = await service.generate_week(unit.id)

    lesson = lesson_repository.added[0]
    assert lesson.status == LessonStatus.AWAITING_REVIEW
    assert any(item["component"] == "diagrams" for item in lesson.generation_errors)
    assert not any(
        block.block_type == LessonBlockType.DIAGRAM for block in lesson.content_blocks
    )
    assert result["errors"] == []  # core lesson still generated


async def test_video_discovery_disabled_recorded_as_component_note() -> None:
    chunk = _chunk("Alpha source text.", 0)
    unit = _unit([_topic("Alpha Topic", [chunk.id])])
    service, lesson_repository = _make_service(unit, [chunk])

    await service.generate_week(unit.id)

    lesson = lesson_repository.added[0]
    assert any(item["component"] == "videos" for item in lesson.generation_errors)
    assert not any(
        block.block_type == LessonBlockType.VIDEO for block in lesson.content_blocks
    )


async def test_unknown_unit_raises() -> None:
    service, _ = _make_service(_unit([]), [])
    with pytest.raises(CurriculumUnitNotFound):
        await service.generate_week(uuid.uuid4())


def test_validated_resource_payload_is_jsonb_serializable() -> None:
    """Regression: a datetime in a block payload broke the JSONB insert."""
    from types import SimpleNamespace

    chunk = _chunk("Alpha source text.", 0)
    unit = _unit([_topic("Alpha Topic", [chunk.id])])
    service, _ = _make_service(unit, [chunk])
    lesson = Lesson(
        curriculum_id=unit.curriculum_id,
        curriculum_unit_id=unit.id,
        topic_id=unit.topic_links[0].topic_id,
        week_number=1,
        order_index=0,
        title="Lesson",
        description="",
        learning_objectives=[],
        estimated_workload_minutes=10,
        status=LessonStatus.AWAITING_REVIEW,
        generation_errors=[],
    )
    resource = ExternalResourcePayload(
        kind="documentation",
        title="Docs",
        url="https://example.com/doc",
        description="desc",
        why_recommended="reason",
        source_chunk_markers=[str(chunk.id)],
        validated_at=datetime.now(UTC),
    )
    blocks: list = []
    service._append_resource_blocks(
        [resource],
        SimpleNamespace(marker_map={}),
        lesson,
        blocks,
        0,
    )
    assert len(blocks) == 1
    payload = blocks[0].payload
    json.dumps(payload)  # mirrors the PostgreSQL JSONB serializer
    assert isinstance(payload["validated_at"], str)
