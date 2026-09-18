"""Unit tests for FourMonthPlanner week-limit enforcement."""

from __future__ import annotations

import uuid

import pytest
from app.models.topic import Topic
from app.services.planner.four_month_planner import (
    FourMonthPlanner,
    PlanningConfig,
)


def _topic(*, title: str, workload: int) -> Topic:
    topic = Topic(
        document_id=uuid.uuid4(),
        title=title,
        difficulty=1,
        estimated_workload_minutes=workload,
        learning_objectives=[],
        prerequisite_titles=[],
    )
    return topic


def test_planner_aggregates_subtopic_subtree_from_flat_list() -> None:
    parent = _topic(title="Parent", workload=100)
    parent.id = uuid.uuid4()
    parent.difficulty = 2
    parent.learning_objectives = ["LO parent"]

    child = _topic(title="Child", workload=50)
    child.difficulty = 4
    child.learning_objectives = ["LO child"]
    child.parent_topic_id = parent.id

    weeks = FourMonthPlanner().plan([parent, child], [], _config(total_weeks=1))

    assert len(weeks) == 1
    assert len(weeks[0].allocations) == 1
    allocation = weeks[0].allocations[0]
    assert allocation.topic_id == parent.id
    assert allocation.allocated_minutes == 150
    assert allocation.difficulty == 4
    assert allocation.title == "Parent"
    assert weeks[0].learning_objectives == ["LO parent", "LO child"]


def _config(total_weeks: int) -> PlanningConfig:
    return PlanningConfig(
        total_weeks=total_weeks,
        max_weekly_workload_minutes=300,
        min_topic_allocation_minutes=5,
        max_topic_allocation_minutes=300,
    )


def test_plan_never_exceeds_total_weeks() -> None:
    topics = [
        _topic(title=f"Topic {i}", workload=150) for i in range(1, 5)
    ]

    weeks = FourMonthPlanner().plan(topics, [], _config(total_weeks=2))

    assert len(weeks) == 2
    allocated = sum(len(week.allocations) for week in weeks)
    assert allocated == 4


def test_plan_uses_all_available_weeks() -> None:
    topics = [
        _topic(title=f"Topic {i}", workload=300) for i in range(1, 4)
    ]

    weeks = FourMonthPlanner().plan(topics, [], _config(total_weeks=3))

    assert [len(week.allocations) for week in weeks] == [1, 1, 1]


def test_plan_raises_when_content_does_not_fit() -> None:
    topics = [
        _topic(title=f"Topic {i}", workload=200) for i in range(1, 5)
    ]

    with pytest.raises(ValueError, match="does not fit"):
        FourMonthPlanner().plan(topics, [], _config(total_weeks=2))


def test_plan_spills_overflow_within_limit() -> None:
    topics = [
        _topic(title=f"Topic {i}", workload=200) for i in range(1, 4)
    ]

    weeks = FourMonthPlanner().plan(topics, [], _config(total_weeks=3))

    assert [len(week.allocations) for week in weeks] == [1, 1, 1]


def test_plan_pads_reaches_exactly_total_weeks() -> None:
    topics = [
        _topic(title=f"Topic {i}", workload=100) for i in range(1, 3)
    ]

    weeks = FourMonthPlanner().plan(topics, [], _config(total_weeks=4))

    assert [week.week_number for week in weeks] == [1, 2, 3, 4]
    assert [len(week.allocations) for week in weeks] == [1, 0, 1, 0]
    assert weeks[0].allocations[0].title == "Topic 1"
    assert weeks[2].allocations[0].title == "Topic 2"


def test_plan_spread_preserves_order_allocations_and_objectives() -> None:
    first = _topic(title="Alpha", workload=100)
    first.id = uuid.uuid4()
    first.learning_objectives = ["Objective Alpha"]
    second = _topic(title="Beta", workload=150)
    second.id = uuid.uuid4()
    second.learning_objectives = ["Objective Beta"]

    weeks = FourMonthPlanner().plan(
        [first, second], [], _config(total_weeks=3)
    )

    assert len(weeks) == 3
    allocations = [a for week in weeks for a in week.allocations]
    assert [a.title for a in allocations] == ["Beta", "Alpha"]
    objectives = [o for week in weeks for o in week.learning_objectives]
    assert objectives == ["Objective Beta", "Objective Alpha"]
    assert all(week.total_minutes <= 300 for week in weeks)
    assert sum(week.total_minutes for week in weeks) == 250


def test_plan_spread_never_exceeds_weekly_budget() -> None:
    topics = [
        _topic(title=f"Topic {i}", workload=80) for i in range(1, 9)
    ]

    weeks = FourMonthPlanner().plan(topics, [], _config(total_weeks=4))

    assert len(weeks) == 4
    allocated = sum(len(week.allocations) for week in weeks)
    assert allocated == 8
    assert [week.week_number for week in weeks] == [1, 2, 3, 4]
    assert all(week.total_minutes <= 300 for week in weeks)
    titles = [a.title for week in weeks for a in week.allocations]
    assert titles == [f"Topic {i}" for i in range(1, 9)]


def test_plan_spread_fills_every_week_when_topics_allow() -> None:
    topics = [
        _topic(title=f"Topic {i}", workload=100) for i in range(1, 21)
    ]

    weeks = FourMonthPlanner().plan(topics, [], _config(total_weeks=16))

    assert len(weeks) == 16
    assert all(len(week.allocations) >= 1 for week in weeks)
    assert all(week.total_minutes <= 300 for week in weeks)
    titles = [a.title for week in weeks for a in week.allocations]
    assert titles == sorted(f"Topic {i}" for i in range(1, 21))