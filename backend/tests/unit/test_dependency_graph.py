"""Unit tests for dependency graph algorithms."""

from __future__ import annotations

import uuid

from app.services.dependency.graph import (
    break_all_cycles,
    find_cycle,
    topological_sort,
)


def test_acyclic_graph_produces_correct_order() -> None:
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    edges = {b: {a}, c: {b}}

    assert find_cycle(edges) is None

    order = topological_sort(edges)

    assert order.index(a) < order.index(b) < order.index(c)


def test_simple_cycle_is_detected_and_broken() -> None:
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    edges = {a: {c}, b: {a}, c: {b}}

    assert find_cycle(edges) is not None

    cleaned, removed = break_all_cycles(edges)

    assert find_cycle(cleaned) is None
    assert len(removed) == 1

    order = topological_sort(cleaned)
    assert len(order) == 3


def test_disjoint_cycle_does_not_affect_acyclic_component() -> None:
    a, b, c, d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    edges = {b: {a}, a: {b}, d: {c}}

    cleaned, removed = break_all_cycles(edges)

    assert find_cycle(cleaned) is None
    order = topological_sort(cleaned)
    assert order.index(c) < order.index(d)


def test_self_loop_is_detected_and_broken() -> None:
    a = uuid.uuid4()
    edges = {a: {a}}

    assert find_cycle(edges) is not None

    cleaned, removed = break_all_cycles(edges)

    assert find_cycle(cleaned) is None
    assert removed == [(a, a)]


def test_topological_sort_raises_if_cycle_not_broken_first() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    edges = {a: {b}, b: {a}}

    try:
        topological_sort(edges)
        raise AssertionError("expected RuntimeError")
    except RuntimeError:
        pass