"""Source-context building for lesson generation.

Each lesson is generated from the actual source chunks that support the
topic being taught (Topic -> TopicSourceChunk -> Chunk provenance). The
builder produces one grounded context per planned topic, reusing the same
marker-annotation approach as topic extraction so the LLM can cite the
exact chunks it relied on and never needs to invent provenance.

A topic with no supporting chunks (possible when markers were dropped or
the planner composed an unsourced topic) falls back to the other chunks
of its weekly unit; if the unit itself has no source chunks at all, the
caller is expected to refuse generation rather than fabricate content.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.models.chunks import Chunk
from app.models.curriculum import Curriculum, CurriculumStatus
from app.models.curriculum_unit import CurriculumUnit
from app.models.topic import Topic
from app.services.content_analysis.chunk_context import (
    build_marker_annotated_context,
)


@dataclass
class LessonContext:
    """A single grounded generation context for one lesson."""

    topic_id: uuid.UUID | None
    topic_title: str
    curriculum_id: uuid.UUID
    curriculum_unit_id: uuid.UUID
    week_number: int
    order_index: int
    learning_objectives: list[str] = field(default_factory=list)
    content_level: str | None = None
    concept_descriptions: list[str] = field(default_factory=list)
    prerequisite_topics: list[str] = field(default_factory=list)
    neighboring_topics: list[str] = field(default_factory=list)
    annotated_text: str = ""
    marker_map: dict[str, uuid.UUID] = field(default_factory=dict)
    chunk_ids: list[uuid.UUID] = field(default_factory=list)


def _flatten_topic_source_chunk_ids(topic: Topic) -> list[uuid.UUID]:
    """Collect source chunk ids across a topic and its subtopics."""
    chunk_ids: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()

    def walk(node: Topic) -> None:
        for link in node.source_chunk_links:
            if link.chunk_id not in seen:
                seen.add(link.chunk_id)
                chunk_ids.append(link.chunk_id)
        for subtopic in node.subtopics:
            walk(subtopic)

    walk(topic)
    return chunk_ids


def build_unit_lesson_contexts(
    unit: CurriculumUnit,
    *,
    chunks_by_id: dict[uuid.UUID, Chunk],
    max_chars: int,
    max_lessons: int,
    prerequisite_topics_by_topic_id: dict[uuid.UUID, list[str]] | None = None,
) -> list[LessonContext]:
    """
    Build one LessonContext per planned topic of a weekly unit, in the
    order the topics appear within the unit.

    ``unit`` must carry its ``topic_links`` with topics loaded with
    subtopics and source-chunk links (as produced by
    ``CurriculumRepository.get_unit_with_lesson_context``). ``chunks_by_id``
    should cover every chunk id reachable from the topics.
    """
    contexts: list[LessonContext] = []
    limit = max(max_lessons, 1)
    prerequisite_topics_by_topic_id = prerequisite_topics_by_topic_id or {}
    unit_topics = [link.topic for link in unit.topic_links if link.topic is not None]

    for link in unit.topic_links:
        topic = link.topic
        if topic is None:
            continue

        chunk_ids = _flatten_topic_source_chunk_ids(topic)

        if not chunk_ids:
            chunk_ids = _unit_fallback_chunk_ids(unit, chunks_by_id)

        ordered_chunks = [
            chunks_by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in chunks_by_id
        ]

        annotated_text, marker_map = build_marker_annotated_context(
            ordered_chunks,
            max_chars=max_chars,
        )

        contexts.append(
            LessonContext(
                topic_id=topic.id,
                topic_title=topic.title,
                curriculum_id=unit.curriculum_id,
                curriculum_unit_id=unit.id,
                week_number=unit.week_number,
                order_index=link.order_index,
                learning_objectives=list(topic.learning_objectives),
                content_level=(
                    topic.content_level.value
                    if hasattr(topic.content_level, "value")
                    else topic.content_level
                ),
                concept_descriptions=[
                    f"{concept.name}: {concept.description}"
                    for concept in topic.concepts
                ],
                prerequisite_topics=list(
                    prerequisite_topics_by_topic_id.get(topic.id, [])
                ),
                neighboring_topics=[
                    candidate.title
                    for candidate in unit_topics
                    if candidate.id != topic.id
                ],
                annotated_text=annotated_text,
                marker_map=marker_map,
                chunk_ids=[c.id for c in ordered_chunks],
            )
        )

        if len(contexts) >= limit:
            break

    return contexts


def collect_unit_chunk_ids(unit: CurriculumUnit) -> list[uuid.UUID]:
    """
    All source chunk ids reachable from a unit's planned topics, including
    subtopics, in document/planning order and deduplicated. This is the
    set the caller must load before building lesson contexts.
    """
    chunk_ids: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for link in unit.topic_links:
        if link.topic is None:
            continue
        for chunk_id in _flatten_topic_source_chunk_ids(link.topic):
            if chunk_id not in seen:
                seen.add(chunk_id)
                chunk_ids.append(chunk_id)
    return chunk_ids


def _unit_fallback_chunk_ids(
    unit: CurriculumUnit, chunks_by_id: dict[uuid.UUID, Chunk]
) -> list[uuid.UUID]:
    """Fall back to the union of all planned topics' chunks for a unit."""
    chunk_ids: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for link in unit.topic_links:
        if link.topic is None:
            continue
        for chunk_id in _flatten_topic_source_chunk_ids(link.topic):
            # Keep document order rather than insertion order.
            if chunk_id not in seen:
                seen.add(chunk_id)
                chunk_ids.append(chunk_id)
    ordered = [
        chunk.id
        for chunk_id in chunk_ids
        if (chunk := chunks_by_id.get(chunk_id)) is not None
    ]
    return ordered


def curriculum_publishable(curriculum: Curriculum) -> bool:
    """Whether a curriculum gate permits lesson publication."""
    return curriculum.status in (
        CurriculumStatus.APPROVED,
        CurriculumStatus.PUBLISHED,
    )
