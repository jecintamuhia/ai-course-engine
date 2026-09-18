"""Unit tests for converting recursive AI extraction results into
flat Topic ORM rows with correct parent linkage and ordering."""

from __future__ import annotations

import uuid

from app.schemas.ai_extraction import ExtractedConcept, ExtractedTopic
from app.services.content_analysis.service import _build_topic_tree_with_provenance


def test_flattens_nested_topics_with_correct_parent_linkage() -> None:
    document_id = uuid.uuid4()

    extracted = [
        ExtractedTopic(
            title="Systems Theory",
            difficulty=2,
            estimated_workload_minutes=60,
            concepts=[ExtractedConcept(name="System", description="A set of parts")],
            subtopics=[
                ExtractedTopic(
                    title="Feedback Loops",
                    difficulty=3,
                    estimated_workload_minutes=45,
                    concepts=[
                        ExtractedConcept(
                            name="Feedback", description="Output shaping input"
                        )
                    ],
                ),
                ExtractedTopic(
                    title="Boundaries",
                    difficulty=2,
                    estimated_workload_minutes=20,
                    subtopics=[
                        ExtractedTopic(
                            title="Open vs Closed Systems",
                            difficulty=3,
                            estimated_workload_minutes=15,
                            concepts=[
                                ExtractedConcept(
                                name="Openness", description="Exchange with environment"
                            )
                            ],
                        )
                    ],
                ),
            ],
        ),
        ExtractedTopic(
            title="Second Top-Level Topic",
            difficulty=1,
            estimated_workload_minutes=10,
        ),
    ]

    topics, _ = _build_topic_tree_with_provenance(
        extracted, document_id=document_id, chapter_id=None, marker_map={}
    )

    assert len(topics) == 2
    assert topics[0].title == "Systems Theory"
    assert topics[0].order_index == 0
    assert topics[1].title == "Second Top-Level Topic"
    assert topics[1].order_index == 1

    systems_theory = topics[0]
    assert len(systems_theory.subtopics) == 2
    assert systems_theory.subtopics[0].title == "Feedback Loops"
    assert systems_theory.subtopics[0].order_index == 0
    assert systems_theory.subtopics[1].title == "Boundaries"
    assert systems_theory.subtopics[1].order_index == 1

    boundaries = systems_theory.subtopics[1]
    assert len(boundaries.subtopics) == 1
    assert boundaries.subtopics[0].title == "Open vs Closed Systems"

    assert len(systems_theory.concepts) == 1
    assert systems_theory.concepts[0].name == "System"


def test_all_topics_carry_document_and_chapter_id() -> None:
    document_id = uuid.uuid4()
    chapter_id = uuid.uuid4()

    extracted = [
        ExtractedTopic(
            title="Top",
            difficulty=1,
            estimated_workload_minutes=10,
            subtopics=[
                ExtractedTopic(
                    title="Nested", difficulty=1, estimated_workload_minutes=5
                )
            ],
        )
    ]

    topics, _ = _build_topic_tree_with_provenance(
        extracted, document_id=document_id, chapter_id=chapter_id, marker_map={}
    )

    assert topics[0].document_id == document_id
    assert topics[0].chapter_id == chapter_id
    assert topics[0].subtopics[0].document_id == document_id
    assert topics[0].subtopics[0].chapter_id == chapter_id


def test_source_links_carry_a_resolvable_topic_fk() -> None:
    document_id = uuid.uuid4()
    chunk_a = uuid.uuid4()
    chunk_b = uuid.uuid4()

    extracted = [
        ExtractedTopic(
            title="Top",
            difficulty=1,
            estimated_workload_minutes=10,
            source_chunk_markers=["C1", "C2"],
            subtopics=[
                ExtractedTopic(
                    title="Nested",
                    difficulty=1,
                    estimated_workload_minutes=5,
                    source_chunk_markers=["C1"],
                )
            ],
        )
    ]

    topics, links = _build_topic_tree_with_provenance(
        extracted,
        document_id=document_id,
        chapter_id=None,
        marker_map={"C1": chunk_a, "C2": chunk_b},
    )

    assert len(links) == 3
    for link in links:
        assert link.topic_id is not None
        assert link.chunk_id is not None

    top_links = [link for link in links if link.topic_id == topics[0].id]
    nested_links = [
        link for link in links if link.topic_id == topics[0].subtopics[0].id
    ]
    assert sorted(link.chunk_id for link in top_links) == sorted(
        [chunk_a, chunk_b]
    )
    assert [link.chunk_id for link in nested_links] == [chunk_a]


def test_hallucinated_markers_are_dropped() -> None:
    document_id = uuid.uuid4()
    chunk_a = uuid.uuid4()

    extracted = [
        ExtractedTopic(
            title="Top",
            difficulty=1,
            estimated_workload_minutes=10,
            source_chunk_markers=["C1", "C99"],
        )
    ]

    _, links = _build_topic_tree_with_provenance(
        extracted,
        document_id=document_id,
        chapter_id=None,
        marker_map={"C1": chunk_a},
    )

    assert len(links) == 1
    assert links[0].chunk_id == chunk_a