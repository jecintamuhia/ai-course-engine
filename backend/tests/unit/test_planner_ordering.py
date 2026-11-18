"""Unit tests for planner document ordering and duplicate exclusion.

These lock in two production fixes:

* independent topics are tie-broken by their document ``order_index``
  instead of an arbitrary UUID order, so front-matter/foundational
  topics stay near the start of the course; and
* topics flagged as duplicates by canonicalization are never scheduled
  (top-level or as a subtopic).
"""

from __future__ import annotations

import uuid

from app.models.dependency import Dependency
from app.models.topic import Topic
from app.services.dependency.graph import topological_sort
from app.services.planner.four_month_planner import (
    FourMonthPlanner,
    PlanningConfig,
)


def _config(total_weeks: int) -> PlanningConfig:
    return PlanningConfig(
        total_weeks=total_weeks,
        max_weekly_workload_minutes=300,
        min_topic_allocation_minutes=5,
        max_topic_allocation_minutes=300,
    )


def _topic(
    *,
    title: str,
    workload: int,
    order_index: int | None,
    topic_id: uuid.UUID | None = None,
) -> Topic:
    topic = Topic(
        document_id=uuid.uuid4(),
        title=title,
        difficulty=1,
        estimated_workload_minutes=workload,
        learning_objectives=[],
        prerequisite_titles=[],
    )
    if order_index is not None:
        topic.order_index = order_index
    if topic_id is not None:
        topic.id = topic_id
    return topic


def test_independent_topics_keep_document_order_with_dependencies() -> None:
    # The topics are delivered in document order (A, B, C). IDs are chosen
    # so the OLD UUID tie-break would emit C first; only the document-order
    # priority produces A, B, C.
    a = _topic(title="A", workload=100, order_index=0, topic_id=uuid.UUID(int=2))
    b = _topic(title="B", workload=100, order_index=1, topic_id=uuid.UUID(int=3))
    c = _topic(title="C", workload=100, order_index=2, topic_id=uuid.UUID(int=1))

    dependencies = [Dependency(topic_id=b.id, depends_on_topic_id=a.id)]

    weeks = FourMonthPlanner().plan([a, b, c], dependencies, _config(total_weeks=3))

    titles = [allocation.title for week in weeks for allocation in week.allocations]
    assert titles == ["A", "B", "C"]


def test_priority_follows_delivered_order_not_topic_order_index() -> None:
    # ``Topic.order_index`` restarts per chapter, so it is NOT a global
    # order; the planner must use the delivered (document) order instead.
    x = _topic(title="X", workload=100, order_index=5, topic_id=uuid.UUID(int=1))
    y = _topic(title="Y", workload=100, order_index=0, topic_id=uuid.UUID(int=2))
    z = _topic(title="Z", workload=100, order_index=1, topic_id=uuid.UUID(int=3))

    dependencies = [Dependency(topic_id=z.id, depends_on_topic_id=x.id)]

    weeks = FourMonthPlanner().plan([x, y, z], dependencies, _config(total_weeks=3))

    titles = [allocation.title for week in weeks for allocation in week.allocations]
    assert titles == ["X", "Y", "Z"]


def test_topological_sort_priority_breaks_ties_deterministically() -> None:
    a = uuid.UUID(int=2)
    b = uuid.UUID(int=3)
    c = uuid.UUID(int=1)
    edges = {b: {a}, a: set(), c: set()}

    prioritized = topological_sort(edges, priority={a: 0, b: 1, c: 2})
    assert prioritized == [a, b, c]

    # Without a priority the tie between a and c falls back to UUID order.
    unprioritized = topological_sort(edges)
    assert unprioritized.index(a) < unprioritized.index(b)
    assert unprioritized == [c, a, b]


def test_duplicate_top_level_topic_is_not_scheduled() -> None:
    canonical = _topic(title="Canonical", workload=100, order_index=0)
    canonical.id = uuid.uuid4()
    duplicate = _topic(title="Canonical (again)", workload=100, order_index=1)
    duplicate.id = uuid.uuid4()
    duplicate.duplicate_of_id = canonical.id

    weeks = FourMonthPlanner().plan(
        [canonical, duplicate], [], _config(total_weeks=1)
    )

    titles = [allocation.title for week in weeks for allocation in week.allocations]
    assert titles == ["Canonical"]


def test_duplicate_subtopic_is_excluded_from_subtree() -> None:
    parent = _topic(title="Parent", workload=100, order_index=0)
    parent.id = uuid.uuid4()

    child = _topic(title="Child", workload=50, order_index=1)
    child.id = uuid.uuid4()
    child.parent_topic_id = parent.id

    duplicate_child = _topic(title="Child (again)", workload=50, order_index=2)
    duplicate_child.id = uuid.uuid4()
    duplicate_child.parent_topic_id = parent.id
    duplicate_child.duplicate_of_id = child.id

    weeks = FourMonthPlanner().plan(
        [parent, child, duplicate_child], [], _config(total_weeks=1)
    )

    assert len(weeks[0].allocations) == 1
    assert weeks[0].allocations[0].title == "Parent"
    assert weeks[0].allocations[0].allocated_minutes == 150
