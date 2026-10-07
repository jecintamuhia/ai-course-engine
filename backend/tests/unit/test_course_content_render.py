"""Unit tests for Moodle-safe lesson content rendering."""

from __future__ import annotations

import uuid

from app.models.lesson import Lesson
from app.models.lesson_content_block import (
    BlockReviewStatus,
    LessonBlockType,
    LessonContentBlock,
)
from app.services.course_content.render import (
    render_block_to_html,
    render_lesson_html,
)
from app.services.course_content.service import (
    _dedupe_links,
    _resolved,
)

CHUNK_ID = uuid.uuid4()


def _block(
    block_type: LessonBlockType,
    payload: dict,
    *,
    title: str | None = None,
    review_status: BlockReviewStatus = BlockReviewStatus.APPROVED,
) -> LessonContentBlock:
    return LessonContentBlock(
        lesson_id=uuid.uuid4(),
        block_type=block_type,
        order_index=0,
        title=title,
        payload=payload,
        review_status=review_status,
    )


def _lesson(blocks: list[LessonContentBlock]) -> Lesson:
    lesson = Lesson(
        curriculum_id=uuid.uuid4(),
        curriculum_unit_id=uuid.uuid4(),
        week_number=1,
        order_index=0,
        title="Test Lesson",
        description="A description.",
        learning_objectives=["Do the thing"],
        estimated_workload_minutes=30,
    )
    lesson.content_blocks = blocks
    return lesson


def test_text_block_preserves_content() -> None:
    html = render_block_to_html(
        block_type=LessonBlockType.TEXT,
        title=None,
        payload={"content": "Hello world."},
    )
    assert "<p>Hello world.</p>" in html


def test_text_block_escapes_markup() -> None:
    html = render_block_to_html(
        block_type=LessonBlockType.TEXT,
        title=None,
        payload={"content": "<script>alert(1)</script>"},
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_heading_block_uses_its_level() -> None:
    html = render_block_to_html(
        block_type=LessonBlockType.HEADING,
        title=None,
        payload={"level": 3, "text": "Subsection"},
    )
    assert "<h3>Subsection</h3>" in html


def test_knowledge_check_answer_hidden_without_include_answers() -> None:
    payload = {
        "question": "What is X?",
        "options": [{"id": "o1", "text": "One"}, {"id": "o2", "text": "Two"}],
        "correct_option_id": "o1",
        "explanation": "Because X.",
        "difficulty": "easy",
    }
    with_answers = render_block_to_html(
        block_type=LessonBlockType.KNOWLEDGE_CHECK,
        title=None,
        payload=payload,
        include_answers=True,
    )
    without_answers = render_block_to_html(
        block_type=LessonBlockType.KNOWLEDGE_CHECK,
        title=None,
        payload=payload,
        include_answers=False,
    )

    assert "<details>" in with_answers
    assert "<details>" not in without_answers
    assert "<strong>One</strong>" in with_answers


def test_external_resource_only_links_http_urls() -> None:
    html = render_block_to_html(
        block_type=LessonBlockType.EXTERNAL_RESOURCE,
        title="Docs",
        payload={
            "url": "https://example.com/docs",
            "description": "The docs.",
            "why_recommended": "Authoritative.",
        },
    )
    assert "href='https://example.com/docs'" in html


def test_external_resource_with_unsafe_url_is_not_a_link() -> None:
    html = render_block_to_html(
        block_type=LessonBlockType.EXTERNAL_RESOURCE,
        title="Suspicious",
        payload={
            "url": "javascript:alert(1)",
            "description": "Nope.",
            "why_recommended": "Nope.",
        },
    )
    assert "<a " not in html
    assert "href" not in html


def test_diagram_renders_nodes_and_edges() -> None:
    html = render_block_to_html(
        block_type=LessonBlockType.DIAGRAM,
        title="Flow",
        payload={
            "diagram_type": "flowchart",
            "caption": "A flow.",
            "nodes": [{"id": "a", "label": "Start"}, {"id": "b", "label": "End"}],
            "edges": [{"source": "a", "target": "b", "label": "go"}],
        },
    )
    assert "Start" in html
    assert "End" in html
    assert "go" in html


def test_lesson_rendering_excludes_rejected_blocks() -> None:
    blocks = [
        _block(LessonBlockType.TEXT, {"content": "Keep me."}),
        _block(
            LessonBlockType.TEXT,
            {"content": "Drop me."},
            review_status=BlockReviewStatus.REJECTED,
        ),
    ]
    html = render_lesson_html(_lesson(blocks))

    assert "Keep me." in html
    assert "Drop me." not in html


def test_lesson_rendering_includes_objectives() -> None:
    html = render_lesson_html(_lesson([]))
    assert "Learning objectives" in html
    assert "Do the thing" in html


def test_resolved_markers_map_to_uuid_strings() -> None:
    marker_map = {"C1": CHUNK_ID, "C2": uuid.uuid4()}

    resolved = _resolved(["C1", "C9"], marker_map)

    assert resolved == [str(CHUNK_ID)]
    assert "C9" not in resolved


def test_dedupe_links_keeps_one_link_per_chunk() -> None:
    from app.models.lesson_source_chunk import LessonSourceChunk

    links = [
        LessonSourceChunk(lesson_id=uuid.uuid4(), chunk_id=CHUNK_ID),
        LessonSourceChunk(lesson_id=uuid.uuid4(), chunk_id=CHUNK_ID),
    ]
    unique = _dedupe_links(links)

    assert len(unique) == 1
