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


def _practical_payload(**overrides: object) -> dict:
    payload: dict = {
        "brief": "Deploy the documented service stack.",
        "scenario": "A single-node lab.",
        "steps": ["Install the packages.", "Start the service."],
        "deliverable": "A running instance plus notes.",
        "evidence": "A transcript of the documented checks.",
        "difficulty": "medium",
        "estimated_minutes": 60,
        "source_chunk_markers": [],
    }
    payload.update(overrides)
    return payload


def test_practical_task_renders_brief_steps_and_evidence() -> None:
    html = render_block_to_html(
        block_type=LessonBlockType.PRACTICAL_TASK,
        title="Build it",
        payload=_practical_payload(),
    )

    assert "<h4>Build it</h4>" in html
    assert "class='practical-task'" in html
    assert "<strong>Scenario:</strong> A single-node lab." in html
    assert "<strong>Hand in:</strong> A running instance plus notes." in html
    assert "<strong>Proof of completion:</strong>" in html
    assert "<ol><li>Install the packages.</li><li>Start the service.</li></ol>" in html
    assert "<strong>Estimated time:</strong> 60 minutes" in html
    assert "<strong>Difficulty:</strong> medium" in html


def test_practical_task_escapes_every_model_supplied_field() -> None:
    html = render_block_to_html(
        block_type=LessonBlockType.PRACTICAL_TASK,
        title="<script>alert(1)</script>",
        payload=_practical_payload(
            brief="<script>alert(1)</script>",
            scenario="\"><script>alert(1)</script>",
            steps=["<img src=x onerror=alert(1)>"],
            deliverable="<svg onload=alert(1)>",
            evidence="<iframe src=//evil></iframe>",
        ),
    )

    assert "<script" not in html
    assert "<img" not in html
    assert "<svg" not in html
    assert "<iframe" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;img" in html


def test_practical_task_without_steps_omits_the_step_list() -> None:
    html = render_block_to_html(
        block_type=LessonBlockType.PRACTICAL_TASK,
        title=None,
        payload=_practical_payload(steps=[], scenario=""),
    )

    assert "<ol>" not in html
    assert "Steps:" not in html
    assert "Scenario:" not in html


def test_practical_task_ignores_steps_that_are_not_strings() -> None:
    html = render_block_to_html(
        block_type=LessonBlockType.PRACTICAL_TASK,
        title=None,
        payload=_practical_payload(steps=[None, 42, "  Keep me  "]),
    )

    assert "<ol><li>Keep me</li></ol>" in html
    assert "<li>42</li>" not in html
    assert "None" not in html


def test_practical_task_is_published_within_a_lesson() -> None:
    blocks = [
        _block(LessonBlockType.TEXT, {"content": "Background."}),
        _block(
            LessonBlockType.PRACTICAL_TASK,
            _practical_payload(),
            title="Build it",
        ),
    ]
    html = render_lesson_html(_lesson(blocks))

    assert "class='practical-task'" in html
    assert "Deploy the documented service stack." in html
