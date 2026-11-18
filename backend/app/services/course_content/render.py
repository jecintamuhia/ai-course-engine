"""Render course content blocks to safe, Moodle-compatible HTML.

This renderer is pure and deterministic: the stored block payloads are
structured data, and every HTML string is produced here from escaped
labels — the LLM never contributes raw HTML (xss-safe by construction).
The output targets Moodle's HTML editor (plain tags, tables, lists,
links, and a ``<details>`` disclosure for self-check answers).
"""

from __future__ import annotations

import html
from typing import Any

from app.models.lesson import Lesson
from app.models.lesson_content_block import LessonBlockType, LessonContentBlock


def _esc(value: Any) -> str:
    """HTML-escape a value for safe interpolation."""
    return html.escape(str(value if value is not None else ""))


def render_block_to_html(
    *,
    block_type: LessonBlockType,
    title: str | None,
    payload: dict[Any, Any],
    include_answers: bool = True,
) -> str:
    """
    Render a single block payload to Moodle-safe HTML.

    ``include_answers`` toggles whether knowledge-check answer/explanation
    content is published (True for the code review UI preview, False to
    hide the answer from a learner-facing page — the mask is implemented
    as a ``<details>`` fallback so content stays self-contained).
    """
    block_type = LessonBlockType(block_type)
    h3 = f"<h4>{_esc(title)}</h4>" if title else ""

    if block_type == LessonBlockType.TEXT:
        return f"{h3}<p>{_esc(payload.get('content', ''))}</p>"

    if block_type == LessonBlockType.HEADING:
        level = payload.get("level", 2)
        if level not in (2, 3):
            level = 2
        return f"<h{level}>{_esc(payload.get('text', ''))}</h{level}>"

    if block_type == LessonBlockType.EXAMPLE:
        content = _esc(payload.get("content", ""))
        return f"{h3}<blockquote>{content}</blockquote>"

    if block_type == LessonBlockType.SUMMARY:
        content = _esc(payload.get("content", ""))
        return f"<div class='lesson-summary'><strong>Summary.</strong> {content}</div>"

    if block_type == LessonBlockType.TABLE:
        return _render_table(payload)

    if block_type == LessonBlockType.DIAGRAM:
        return _render_diagram(payload)

    if block_type == LessonBlockType.EXTERNAL_RESOURCE:
        raw_url = str(payload.get("url", ""))
        safe_url = _safe_url(raw_url)
        if safe_url:
            link = (
                f"<a href='{_esc(safe_url)}' target='_blank' rel='noopener'>"
                f"{_esc(raw_url)}</a>"
            )
        else:
            link = _esc(raw_url)
        return (
            f"{h3}{link}"
            f"<p>{_esc(payload.get('description', ''))}</p>"
            f"<p><em>Why this resource: "
            f"{_esc(payload.get('why_recommended', ''))}</em></p>"
        )

    if block_type == LessonBlockType.VIDEO:
        raw_url = str(payload.get("url", ""))
        safe_url = _safe_url(raw_url)
        if safe_url:
            link = (
                f"<a href='{_esc(safe_url)}' target='_blank' rel='noopener'>"
                f"{_esc(raw_url)}</a>"
            )
        else:
            link = _esc(raw_url)
        channel_text = payload.get("channel")
        channel = f" — {_esc(channel_text)}" if channel_text else ""
        return f"{h3}{link}<p>{_esc(payload.get('description', ''))}{channel}</p>"

    if block_type == LessonBlockType.ACTIVITY:
        minutes = _esc(payload.get("estimated_minutes", ""))
        instructions = _esc(payload.get("instructions", ""))
        return (
            f"{h3}<p><strong>Estimated time:</strong> {minutes} minutes.</p>"
            f"<p>{instructions}</p>"
        )

    if block_type == LessonBlockType.PRACTICAL_TASK:
        return _render_practical_task(payload, heading=h3)

    if block_type == LessonBlockType.KNOWLEDGE_CHECK:
        return _render_knowledge_check(payload, include_answers=include_answers)

    return ""


def render_lesson_html(
    lesson: Lesson,
    *,
    include_answers: bool = True,
) -> str:
    """
    Render a full lesson into a single Moodle Page-style HTML document.

    Only blocks whose review status is not REJECTED are published, so a
    lecturer-approved lesson never carries rejected content into Moodle.
    """
    parts = [f"<h3>{_esc(lesson.title)}</h3>", f"<p>{_esc(lesson.description)}</p>"]

    objectives = getattr(lesson, "learning_objectives", None) or []
    if objectives:
        items = "".join(f"<li>{_esc(obj)}</li>" for obj in objectives)
        parts.append(f"<h4>Learning objectives</h4><ul>{items}</ul>")

    for block in _publishable_blocks(lesson.content_blocks):
        rendered = render_block_to_html(
            block_type=block.block_type,
            title=block.title,
            payload=block.payload,
            include_answers=include_answers,
        )
        if rendered:
            parts.append(rendered)

    return "\n".join(parts) or f"<p>{_esc(lesson.title)}</p>"


def _publishable_blocks(blocks: list[LessonContentBlock]) -> list[LessonContentBlock]:
    """Return the blocks that may be published (not rejected), in order."""
    from app.models.lesson_content_block import BlockReviewStatus

    return [b for b in blocks if b.review_status != BlockReviewStatus.REJECTED]


def _render_table(payload: dict[Any, Any]) -> str:
    headers = payload.get("headers") or []
    rows = payload.get("rows") or []
    caption = _esc(payload.get("caption")) if payload.get("caption") else ""
    head = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    thead = f"<thead><tr>{head}</tr></thead>" if head else ""
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{_esc(c)}</td>" for c in row)
        body_rows.append(f"<tr>{cells}</tr>")
    tbody = f"<tbody>{''.join(body_rows)}</tbody>" if body_rows else ""
    if not thead and not tbody:
        return ""
    return f"<figure>{caption if caption else ''}<table>{thead}{tbody}</table></figure>"


def _render_diagram(payload: dict[Any, Any]) -> str:
    diagram_type = payload.get("diagram_type", "concept_map")
    caption = _esc(payload.get("caption", ""))
    nodes = payload.get("nodes") or []
    edges = payload.get("edges") or []
    label_by_id = {str(node.get("id")): _esc(node.get("label", "")) for node in nodes}

    if not nodes:
        empty = caption
        figcaption = f"<figcaption>{empty}</figcaption>" if empty else ""
        return f"<figure>{figcaption}<p>Diagram with no nodes.</p></figure>"

    node_items = "".join(f"<li>{label}</li>" for label in label_by_id.values())

    edge_items = ""
    for edge in edges:
        source_label = label_by_id.get(
            str(edge.get("source")), _esc(edge.get("source"))
        )
        target_label = label_by_id.get(
            str(edge.get("target")), _esc(edge.get("target"))
        )
        arrow_label = _esc(edge.get("label")) if edge.get("label") else ""
        prefix = (
            f"<span class='edge-label'>{arrow_label}: </span>" if arrow_label else ""
        )
        edge_items += f"<li>{prefix}{source_label} &rarr; {target_label}</li>"

    kind_label = diagram_type.replace("_", " ").title()
    return (
        f"<figure><figcaption>{caption}</figcaption>"
        f"<p><strong>Nodes ({kind_label}):</strong></p><ul>{node_items}</ul>"
        f"<p><strong>Edges:</strong></p>"
        f"<ul>{edge_items or '<li>(no edges)</li>'}</ul></figure>"
    )


def _render_knowledge_check(payload: dict[Any, Any], *, include_answers: bool) -> str:
    question = _esc(payload.get("question", ""))
    options = payload.get("options") or []
    correct_id = str(payload.get("correct_option_id", ""))
    explanation = _esc(payload.get("explanation", ""))
    difficulty = _esc(payload.get("difficulty", "medium"))

    option_items = []
    for option in options:
        marker = "&#10003;" if str(option.get("id")) == correct_id else "&#10063;"
        label = f"<span class='answer-marker'>{marker} </span>"
        option_items.append(f"<li>{label}{_esc(option.get('text', ''))}</li>")

    answer_entry = ""
    if include_answers:
        correct_label = next(
            (
                _esc(o.get("text", ""))
                for o in options
                if str(o.get("id")) == correct_id
            ),
            correct_id,
        )
        answer_entry = (
            f"<details><summary>Check your answer</summary>"
            f"<p>Correct answer: <strong>{correct_label}</strong></p>"
            f"<p>{explanation}</p></details>"
        )

    return (
        f"<div class='knowledge-check'>"
        f"<p><strong>Knowledge check ({difficulty}):</strong> {question}</p>"
        f"<ul>{''.join(option_items)}</ul>{answer_entry}</div>"
    )


def _render_practical_task(payload: dict[Any, Any], *, heading: str) -> str:
    """Render a practical project brief to Moodle-safe HTML.

    Everything the model produced is escaped; the ordered step list is
    rebuilt from primitives so no markup can pass through, which keeps
    the brief readable and submit-ready in a Moodle page.
    """
    brief = _esc(payload.get("brief", ""))
    scenario = _esc(payload.get("scenario", ""))
    deliverable = _esc(payload.get("deliverable", ""))
    evidence = _esc(payload.get("evidence", ""))
    difficulty = _esc(payload.get("difficulty", "medium"))
    minutes = _esc(payload.get("estimated_minutes", ""))

    parts = [f"{heading}<div class='practical-task'>"]
    if scenario:
        parts.append(f"<p><strong>Scenario:</strong> {scenario}</p>")
    if brief:
        parts.append(f"<p>{brief}</p>")

    steps = [
        step.strip()
        for step in payload.get("steps") or []
        if isinstance(step, str) and step.strip()
    ]
    if steps:
        items = "".join(f"<li>{_esc(step)}</li>" for step in steps)
        parts.append(f"<p><strong>Steps:</strong></p><ol>{items}</ol>")

    if deliverable:
        parts.append(f"<p><strong>Hand in:</strong> {deliverable}</p>")
    if evidence:
        parts.append(f"<p><strong>Proof of completion:</strong> {evidence}</p>")

    meta = []
    if minutes != "":
        meta.append(f"<strong>Estimated time:</strong> {minutes} minutes")
    if difficulty:
        meta.append(f"<strong>Difficulty:</strong> {difficulty}")
    if meta:
        parts.append(f"<p>{' &middot; '.join(meta)}</p>")

    parts.append("</div>")
    return "".join(parts)


def _safe_url(value: Any) -> str | None:
    """Return the URL only when it is an http(s) absolute URL."""
    raw = str(value or "").strip()
    if raw.startswith(("http://", "https://")):
        return raw
    return None
