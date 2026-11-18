"""Unit tests for the Moodle lesson-page renderer adapter."""

from __future__ import annotations

import uuid

from app.models.lesson import Lesson, LessonStatus
from app.models.lesson_content_block import (
    BlockReviewStatus,
    LessonBlockType,
    LessonContentBlock,
)
from app.services.moodle.lessons import (
    build_lesson_renderer,
    compute_lesson_page_names,
)
from app.services.moodle.mapper import extract_lesson_id, lesson_id_marker


def _lesson(
    curriculum_unit_id: uuid.UUID,
    title: str,
    order_index: int = 0,
    week_number: int = 1,
) -> Lesson:
    lesson = Lesson(
        id=uuid.uuid4(),
        curriculum_id=uuid.uuid4(),
        curriculum_unit_id=curriculum_unit_id,
        topic_id=None,
        week_number=week_number,
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

    lesson.content_blocks[0].review_status = BlockReviewStatus.REJECTED

    renderer = build_lesson_renderer([lesson])
    plans = renderer(_unit(lesson.curriculum_unit_id))
    assert len(plans) == 1
    assert "Some content." not in plans[0].content_html


def test_renderer_with_no_lessons_returns_empty():
    renderer = build_lesson_renderer([])
    assert renderer(_unit(uuid.uuid4())) == []


def test_renderer_embeds_lesson_identity_marker():
    lesson = _lesson(uuid.uuid4(), "Lesson")

    renderer = build_lesson_renderer([lesson])
    (plan,) = renderer(_unit(lesson.curriculum_unit_id))

    assert plan.lesson_id == lesson.id
    assert plan.content_html.startswith(lesson_id_marker(lesson.id))
    assert extract_lesson_id(plan.content_html) == lesson.id


def test_renderer_collapses_duplicate_lesson_items_to_single_page():
    unit_a = uuid.uuid4()
    original = _lesson(unit_a, "Duplicate Lesson", order_index=0)
    duplicate = _lesson(unit_a, "Duplicate Lesson", order_index=1)

    renderer = build_lesson_renderer([original, duplicate])
    plans = renderer(_unit(unit_a))

    assert len(plans) == 1
    assert plans[0].name == "Duplicate Lesson"
    assert plans[0].lesson_id == original.id


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
    # Course-wide unique names: the second distinct lesson with the same
    # title is published under a deterministic disambiguated name.
    assert [p.name for p in plans] == ["Shared Title", "Shared Title (Week 1)"]
    assert plans[0].content_html != plans[1].content_html
    assert [p.lesson_id for p in plans] == [first.id, second.id]
    assert extract_lesson_id(plans[0].content_html) == first.id
    assert extract_lesson_id(plans[1].content_html) == second.id


def test_renderer_disambiguates_same_title_across_units_by_week():
    unit_w1 = uuid.uuid4()
    unit_w3 = uuid.uuid4()
    week1 = _lesson(unit_w1, "Shared Title", order_index=0, week_number=1)
    week3 = _lesson(unit_w3, "Shared Title", order_index=0, week_number=3)

    renderer = build_lesson_renderer([week3, week1])  # input order must not matter

    assert [p.name for p in renderer(_unit(unit_w1))] == ["Shared Title"]
    assert [p.name for p in renderer(_unit(unit_w3))] == ["Shared Title (Week 3)"]


def test_renderer_names_stay_unique_for_same_title_same_week():
    unit = uuid.uuid4()
    lessons = [
        _lesson(unit, "Same", order_index=0),
        _lesson(unit, "Same", order_index=1),
        _lesson(unit, "Same", order_index=2),
    ]
    for index, lesson in enumerate(lessons):
        lesson.content_blocks[0].payload = {
            "content": f"Distinct content {index}.",
            "source_chunk_markers": [],
        }

    renderer = build_lesson_renderer(lessons)
    plans = renderer(_unit(unit))

    names = [p.name for p in plans]
    assert len(names) == 3
    assert len(set(names)) == 3
    assert names[0] == "Same"


def test_page_names_are_deterministic_across_input_order():
    unit_a = uuid.uuid4()
    unit_b = uuid.uuid4()
    lessons = [
        _lesson(unit_a, "Lesson A1", order_index=0),
        _lesson(unit_a, "Shared Title", order_index=1),
        _lesson(unit_b, "Shared Title", order_index=0, week_number=2),
        _lesson(unit_b, "Lesson B2", order_index=1, week_number=2),
    ]

    forwards = compute_lesson_page_names(lessons)
    backwards = compute_lesson_page_names(list(reversed(lessons)))

    assert forwards == backwards
    assert len(set(forwards.values())) == len(forwards)
    assert forwards[lessons[0].id] == "Lesson A1"
    assert forwards[lessons[1].id] == "Shared Title"
    assert forwards[lessons[2].id] == "Shared Title (Week 2)"
    assert forwards[lessons[3].id] == "Lesson B2"


def test_page_names_map_collapsed_duplicates_to_survivor_page():
    unit = uuid.uuid4()
    original = _lesson(unit, "Duplicate Lesson", order_index=0)
    duplicate = _lesson(unit, "Duplicate Lesson", order_index=1)

    names = compute_lesson_page_names([original, duplicate])

    assert names[original.id] == "Duplicate Lesson"
    assert names[duplicate.id] == "Duplicate Lesson"
    renderer = build_lesson_renderer([original, duplicate])
    (plan,) = renderer(_unit(unit))
    assert plan.name == "Duplicate Lesson"
