"""Unit tests for the Moodle lesson-page renderer adapter."""

from __future__ import annotations

import uuid

from app.models.lesson import Lesson, LessonStatus
from app.models.lesson_content_block import LessonBlockType, LessonContentBlock
from app.services.moodle.lessons import build_lesson_renderer


def _lesson(
    curriculum_unit_id: uuid.UUID,
    title: str,
    order_index: int = 0,
) -> Lesson:
    lesson = Lesson(
        curriculum_id=uuid.uuid4(),
        curriculum_unit_id=curriculum_unit_id,
        topic_id=None,
        week_number=1,
        order_index=order_index,
        title=title,
        description=f"About {title}.",
        learning_objectives=["Learn it."],
        estimated_workload_minutes=20,
        status=LessonStatus.APPROVED,
        generation_errors=[],
    )
    lesson.content_blocks = [
        LessonContentBlock(
            lesson_id=lesson.id,
            order_index=0,
            block_type=LessonBlockType.TEXT,
            title="Intro",
            payload={
                "content": "Some content.",
                "source_chunk_markers": [],
            },
        )
    ]
    return lesson


def _unit(unit_id: uuid.UUID):
    class _Unit:
        def __init__(self, id_: uuid.UUID) -> None:
            self.id = id_

    return _Unit(unit_id)


def test_renderer_groups_lessons_by_unit():
    unit_a = uuid.uuid4()
    unit_b = uuid.uuid4()
    lessons = [
        _lesson(unit_a, "Lesson A1", order_index=0),
        _lesson(unit_a, "Lesson A2", order_index=1),
        _lesson(unit_b, "Lesson B", order_index=0),
    ]

    renderer = build_lesson_renderer(lessons)

    unit_a_plans = renderer(_unit(unit_a))
    assert [p.name for p in unit_a_plans] == ["Lesson A1", "Lesson A2"]
    for plan in unit_a_plans:
        assert "Lesson A1" in plan.content_html or "Lesson A2" in plan.content_html
        assert "Some content." in plan.content_html

    unit_b_plans = renderer(_unit(unit_b))
    assert [p.name for p in unit_b_plans] == ["Lesson B"]

    unit_c_plans = renderer(_unit(uuid.uuid4()))
    assert unit_c_plans == []


def test_renderer_excludes_rejected_content_blocks():
    lesson = _lesson(uuid.uuid4(), "Lesson")
    from app.models.lesson_content_block import BlockReviewStatus

    lesson.content_blocks[0].review_status = BlockReviewStatus.REJECTED

    renderer = build_lesson_renderer([lesson])
    plans = renderer(_unit(lesson.curriculum_unit_id))
    assert len(plans) == 1
    assert "Some content." not in plans[0].content_html


def test_renderer_with_no_lessons_returns_empty():
    renderer = build_lesson_renderer([])
    assert renderer(_unit(uuid.uuid4())) == []


def test_renderer_collapses_duplicate_lesson_items_to_single_page():
    unit_a = uuid.uuid4()
    original = _lesson(unit_a, "Duplicate Lesson", order_index=0)
    duplicate = _lesson(unit_a, "Duplicate Lesson", order_index=1)

    renderer = build_lesson_renderer([original, duplicate])
    plans = renderer(_unit(unit_a))

    assert len(plans) == 1
    assert plans[0].name == "Duplicate Lesson"


def test_renderer_preserves_same_title_with_distinct_content():
    unit_a = uuid.uuid4()
    first = _lesson(unit_a, "Shared Title", order_index=0)
    second = _lesson(unit_a, "Shared Title", order_index=1)
    second.content_blocks[0].payload = {
        "content": "Completely different content.",
        "source_chunk_markers": [],
    }

    renderer = build_lesson_renderer([first, second])
    plans = renderer(_unit(unit_a))

    assert len(plans) == 2
    assert [p.name for p in plans] == ["Shared Title", "Shared Title"]
    assert plans[0].content_html != plans[1].content_html
