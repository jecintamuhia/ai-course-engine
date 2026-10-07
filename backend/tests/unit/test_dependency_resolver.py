"""Unit tests for prerequisite title resolution."""

from __future__ import annotations

import uuid

from app.models.topic import Topic
from app.services.dependency.graph import break_all_cycles, topological_sort
from app.services.dependency.resolver import resolve_prerequisites


def _topic(
    title: str,
    prerequisite_titles: list[str] | None = None,
    **overrides,
) -> Topic:
    topic = Topic(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        title=title,
        prerequisite_titles=prerequisite_titles or [],
        learning_objectives=[],
        difficulty=1,
        estimated_workload_minutes=10,
        order_index=0,
        **overrides,
    )
    return topic


def test_resolves_exact_title_match() -> None:
    a = _topic("Python Basics")
    b = _topic("Functions", prerequisite_titles=["Python Basics"])

    edges, unresolved = resolve_prerequisites([a, b])

    assert edges[b.id] == {a.id}
    assert unresolved == []


def test_resolves_case_and_whitespace_insensitively() -> None:
    a = _topic("Functions")
    c = _topic("OOP", prerequisite_titles=["  functions  "])

    edges, unresolved = resolve_prerequisites([a, c])

    assert edges[c.id] == {a.id}
    assert unresolved == []


def test_not_found_prerequisite_is_reported_and_creates_no_edge() -> None:
    d = _topic("Introduction", prerequisite_titles=["Nonexistent Topic"])

    edges, unresolved = resolve_prerequisites([d])

    assert edges.get(d.id) == set()
    assert len(unresolved) == 1
    assert unresolved[0].reason == "not_found"


def test_ambiguous_title_is_reported_and_creates_no_edge() -> None:
    intro_1 = _topic("Introduction")
    intro_2 = _topic("Introduction")
    referencer = _topic("Chapter 2", prerequisite_titles=["Introduction"])

    edges, unresolved = resolve_prerequisites([intro_1, intro_2, referencer])

    assert edges.get(referencer.id) == set()
    assert len(unresolved) == 1
    assert unresolved[0].reason == "ambiguous"


def test_isolated_topics_are_seeded_with_empty_edges() -> None:
    a = _topic("Alone")
    b = _topic("Depends", prerequisite_titles=["Alone"])
    c = _topic("Standalone")

    edges, unresolved = resolve_prerequisites([a, b, c])

    assert edges[a.id] == set()
    assert edges[c.id] == set()
    assert edges[b.id] == {a.id}
    assert unresolved == []


def test_resolves_across_nested_subtopics() -> None:
    child = _topic("Feedback Loops")
    parent = _topic("Systems Theory", subtopics=[child])
    other = _topic("Advanced Systems", prerequisite_titles=["Feedback Loops"])

    edges, unresolved = resolve_prerequisites([parent, other])

    assert edges[other.id] == {child.id}
    assert unresolved == []


def test_topological_order_includes_isolated_topics() -> None:
    a = _topic("Isolated A")
    b = _topic("Isolated B")

    edges, _ = resolve_prerequisites([a, b])
    acyclic, removed = break_all_cycles(edges)

    assert removed == []
    order = topological_sort(acyclic)
    assert a.id in order
    assert b.id in order
