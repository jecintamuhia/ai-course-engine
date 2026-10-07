"""Unit tests for lesson-context building from a weekly unit's topics."""

from __future__ import annotations

import uuid

from app.models.chunks import Chunk
from app.models.concept import Concept
from app.models.curriculum_unit import CurriculumUnit
from app.models.curriculum_unit_topic import CurriculumUnitTopic
from app.models.topic import Topic
from app.models.topic_source_chunk import TopicSourceChunk
from app.services.course_content.context import (
    build_unit_lesson_contexts,
    collect_unit_chunk_ids,
)


def _chunk(content: str) -> Chunk:
    return Chunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        page_id=uuid.uuid4(),
        document_index=0,
        page_index=0,
        content=content,
        char_count=len(content),
        content_hash="fake",
    )


def _topic(title: str, chunk_ids: list[uuid.UUID], subtopics=None) -> Topic:
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
    if subtopics:
        topic.subtopics = subtopics
    return topic


def _unit(topic_links: list[CurriculumUnitTopic]) -> CurriculumUnit:
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
    unit.topic_links = topic_links
    return unit


def _link(topic: Topic, order_index: int) -> CurriculumUnitTopic:
    return CurriculumUnitTopic(
        id=uuid.uuid4(),
        curriculum_unit_id=uuid.uuid4(),
        topic_id=topic.id,
        order_index=order_index,
        topic=topic,
    )


def _chunks_by_id(chunks: list[Chunk]) -> dict[uuid.UUID, Chunk]:
    return {chunk.id: chunk for chunk in chunks}


def test_one_context_per_planned_topic_with_grounding() -> None:
    chunk_a = _chunk("Alpha content.")
    chunk_b = _chunk("Beta content.")
    topic_a = _topic("First Topic", [chunk_a.id])
    topic_b = _topic("Second Topic", [chunk_b.id])
    unit = _unit([_link(topic_a, 0), _link(topic_b, 1)])

    contexts = build_unit_lesson_contexts(
        unit,
        chunks_by_id=_chunks_by_id([chunk_a, chunk_b]),
        max_chars=10_000,
        max_lessons=4,
    )

    assert [c.topic_title for c in contexts] == ["First Topic", "Second Topic"]
    assert contexts[0].topic_id == topic_a.id
    assert contexts[1].topic_id == topic_b.id
    assert contexts[0].order_index == 0
    assert contexts[1].order_index == 1


def test_context_carries_graph_and_progression_context() -> None:
    chunk = _chunk("The source explains DNS zones.")
    topic_a = _topic("DNS zones", [chunk.id])
    topic_b = _topic("DNS records", [])
    topic_a.content_level = "intermediate"
    topic_a.concepts = [
        Concept(
            topic_id=topic_a.id,
            name="Zone file",
            description="A collection of DNS records",
            order_index=0,
        )
    ]
    unit = _unit([_link(topic_a, 0), _link(topic_b, 1)])

    contexts = build_unit_lesson_contexts(
        unit,
        chunks_by_id=_chunks_by_id([chunk]),
        max_chars=10_000,
        max_lessons=4,
        prerequisite_topics_by_topic_id={topic_a.id: ["IP addressing"]},
    )

    assert contexts[0].content_level == "intermediate"
    assert contexts[0].concept_descriptions == [
        "Zone file: A collection of DNS records"
    ]
    assert contexts[0].prerequisite_topics == ["IP addressing"]
    assert contexts[0].neighboring_topics == ["DNS records"]
    assert contexts[0].week_number == 1
    assert contexts[0].order_index == 0


def test_context_carries_unit_identity_fields() -> None:
    chunk = _chunk("Solo content.")
    topic = _topic("Solo Topic", [chunk.id])
    unit = _unit([_link(topic, 0)])

    context = build_unit_lesson_contexts(
        unit,
        chunks_by_id=_chunks_by_id([chunk]),
        max_chars=10_000,
        max_lessons=4,
    )[0]

    assert context.curriculum_id == unit.curriculum_id
    assert context.curriculum_unit_id == unit.id
    assert context.week_number == unit.week_number
    assert context.chunk_ids == [chunk.id]


def test_marker_map_resolves_annotated_text() -> None:
    chunk_a = _chunk("Alpha content.")
    chunk_b = _chunk("Beta content.")
    topic = _topic("Grounded Topic", [chunk_a.id, chunk_b.id])
    unit = _unit([_link(topic, 0)])

    context = build_unit_lesson_contexts(
        unit,
        chunks_by_id=_chunks_by_id([chunk_a, chunk_b]),
        max_chars=10_000,
        max_lessons=4,
    )[0]

    assert "[C1] Alpha content." in context.annotated_text
    assert "[C2] Beta content." in context.annotated_text
    assert context.marker_map["C1"] == chunk_a.id
    assert context.marker_map["C2"] == chunk_b.id


def test_subtopic_chunks_are_included_in_topic_grounding() -> None:
    subtopic_chunk = _chunk("Sub content.")
    subtopic = _topic("A Subtopic", [subtopic_chunk.id])
    topic = _topic("Parent Topic", [], subtopics=[subtopic])
    unit = _unit([_link(topic, 0)])

    context = build_unit_lesson_contexts(
        unit,
        chunks_by_id=_chunks_by_id([subtopic_chunk]),
        max_chars=10_000,
        max_lessons=4,
    )[0]

    assert context.chunk_ids == [subtopic_chunk.id]
    assert context.marker_map["C1"] == subtopic_chunk.id
    assert list(collect_unit_chunk_ids(unit)) == [subtopic_chunk.id]


def test_topic_without_chunks_falls_back_to_unit_chunks() -> None:
    chunk = _chunk("Unit-wide content.")
    unsourced = _topic("Unsourced Topic", [])
    sourced = _topic("Sourced Topic", [chunk.id])
    unit = _unit([_link(unsourced, 0), _link(sourced, 1)])

    context = build_unit_lesson_contexts(
        unit,
        chunks_by_id=_chunks_by_id([chunk]),
        max_chars=10_000,
        max_lessons=4,
    )[0]

    assert context.marker_map["C1"] == chunk.id


def test_unit_with_no_chunks_anywhere_yields_empty_grounding() -> None:
    topic = _topic("Lonely Topic", [])
    unit = _unit([_link(topic, 0)])

    context = build_unit_lesson_contexts(
        unit,
        chunks_by_id={},
        max_chars=10_000,
        max_lessons=4,
    )[0]

    assert context.annotated_text.strip() == ""
    assert context.marker_map == {}


def test_max_lessons_caps_number_of_contexts() -> None:
    topics = [_topic(f"Topic {i}", []) for i in range(4)]
    unit = _unit([_link(topic, i) for i, topic in enumerate(topics)])

    contexts = build_unit_lesson_contexts(
        unit,
        chunks_by_id={},
        max_chars=10_000,
        max_lessons=2,
    )

    assert len(contexts) == 2


def test_collect_unit_chunk_ids_is_deduplicated() -> None:
    chunk = _chunk("Shared content.")
    topic_a = _topic("Topic One", [chunk.id])
    topic_b = _topic("Topic Two", [chunk.id])
    unit = _unit([_link(topic_a, 0), _link(topic_b, 1)])

    ids = collect_unit_chunk_ids(unit)

    assert ids.count(chunk.id) == 1
