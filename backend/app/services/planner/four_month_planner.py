"""Four-month (weekly) curriculum planner: deterministic topic→week scheduling.

The planner is intentionally pure — no database, no AI. It turns an
in-memory set of extracted Topic rows (with their resolved Dependency
edges) into an ordered list of WeekPlan objects, packing topics into
weeks subject to workload constraints.

Nothing is hardcoded to 16 weeks: the week count and weekly workload
budget are caller-supplied. 16 weeks is only the CLI/API default.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from app.models.dependency import Dependency
from app.models.topic import Topic
from app.services.dependency.graph import Edges, break_all_cycles, topological_sort


@dataclass(frozen=True)
class TopicAllocation:
    """A single top-level topic scheduled into a week."""

    topic_id: uuid.UUID
    title: str
    allocated_minutes: int
    difficulty: int
    order_index: int
    learning_objectives: tuple[str, ...] = ()


@dataclass
class WeekPlan:
    """One week of the plan: a list of allocated topics plus goals."""

    week_number: int
    allocations: list[TopicAllocation] = field(default_factory=list)
    learning_objectives: list[str] = field(default_factory=list)

    @property
    def total_minutes(self) -> int:
        """Total planned workload for the week."""
        return sum(alloc.allocated_minutes for alloc in self.allocations)

    @property
    def title(self) -> str:
        """A human-readable week title derived from the allocated topics."""
        if not self.allocations:
            return f"Week {self.week_number}"
        names = ", ".join(a.title for a in self.allocations)
        return f"Week {self.week_number}: {names}"

    @property
    def description(self) -> str:
        """A plain-text description of the week grounded in its topics."""
        if not self.allocations:
            return f"Week {self.week_number}: no topics assigned."
        objectives = " ".join(f"- {o}" for o in self.learning_objectives)
        return (
            f"This week covers: {', '.join(a.title for a in self.allocations)}.\n"
            f"By the end of the week, learners will be able to:\n{objectives}"
        )


@dataclass(frozen=True)
class PlanningConfig:
    """Constraints used by the planner when scheduling topics into weeks."""

    total_weeks: int
    max_weekly_workload_minutes: int
    min_topic_allocation_minutes: int
    max_topic_allocation_minutes: int


@dataclass(frozen=True)
class _PlannableTopic:
    """A top-level topic aggregated with its subtopics for scheduling."""

    topic_id: uuid.UUID
    title: str
    difficulty: int
    workload_minutes: int
    learning_objectives: list[str]


def _aggregate_topics(topics: list[Topic]) -> list[_PlannableTopic]:
    """
    Collapse each top-level topic's subtree into a single plannable
    unit: workload is the sum of the topic and its subtopics, objectives
    are concatenated, difficulty is the max seen in the subtree.

    Subtree membership is resolved from ``parent_topic_id`` pointers on
    the flat topic list rather than the ``subtopics`` ORM relationship,
    so the planner never triggers a lazy load outside an async session.
    """
    children_of: dict[uuid.UUID, list[Topic]] = defaultdict(list)
    for topic in topics:
        if topic.parent_topic_id is not None:
            children_of[topic.parent_topic_id].append(topic)

    def collect_subtree(
        topic: Topic,
    ) -> tuple[int, list[str], int]:
        workload = topic.estimated_workload_minutes
        objectives = list(topic.learning_objectives)
        hardest = topic.difficulty
        for child in children_of.get(topic.id, []):
            child_workload, child_objectives, child_difficulty = collect_subtree(
                child
            )
            workload += child_workload
            objectives.extend(child_objectives)
            hardest = max(hardest, child_difficulty)
        return workload, objectives, hardest

    plannable: list[_PlannableTopic] = []
    for topic in topics:
        if topic.parent_topic_id is not None:
            continue
        workload, objectives, hardest = collect_subtree(topic)
        plannable.append(
            _PlannableTopic(
                topic_id=topic.id,
                title=topic.title,
                difficulty=hardest,
                workload_minutes=workload,
                learning_objectives=objectives,
            )
        )

    return plannable


def _order_topics(
    plannable: list[_PlannableTopic], dependencies: list[Dependency]
) -> list[_PlannableTopic]:
    """
    Order topics for scheduling. If dependency edges exist, use a
    topological order (prerequisites scheduled before dependents);
    otherwise fall back to ordering by workload then difficulty.
    """
    by_id = {topic.topic_id: topic for topic in plannable}

    if dependencies:
        edges: Edges = {topic.topic_id: set() for topic in plannable}
        for dep in dependencies:
            dependent = dep.topic_id
            prerequisite = dep.depends_on_topic_id
            if dependent in by_id and prerequisite in by_id:
                edges[dependent].add(prerequisite)

        acyclic_edges, _ = break_all_cycles(edges)
        try:
            ordered_ids = topological_sort(acyclic_edges)
        except RuntimeError:
            ordered_ids = list(by_id.keys())
        return [by_id[topic_id] for topic_id in ordered_ids]

    # Deterministic fallback: heavier and harder topics first.
    return sorted(
        plannable,
        key=lambda t: (-t.workload_minutes, -t.difficulty, t.title),
    )


def _clamp_topic_allocation(
    workload_minutes: int, config: PlanningConfig
) -> int:
    """Clamp a topic's workload to the configured allocation bounds."""
    return min(
        max(workload_minutes, config.min_topic_allocation_minutes),
        config.max_topic_allocation_minutes,
        config.max_weekly_workload_minutes,
    )


class FourMonthPlanner:
    """
    Spreads a document's topics across a number of weekly units using
    greedy bin-packing under workload constraints, honoring prerequisite
    ordering where dependency edges exist.

    The plan is then padded to exactly ``PlanningConfig.total_weeks``
    weekly units, diluting each packed week across a contiguous run of
    the full horizon so that light content still produces a course of
    the requested length without violating any workload budget.
    """

    def plan(
        self,
        topics: list[Topic],
        dependencies: list[Dependency],
        config: PlanningConfig,
    ) -> list[WeekPlan]:
        """
        Produce week plans (WeekPlan) from the given topics.

        Raises CurriculumValidationError-style behaviour via ValueError
        if the content cannot fit in the requested number of weeks.
        """
        if config.total_weeks < 1:
            raise ValueError("total_weeks must be at least 1")

        plannable = _aggregate_topics(topics)

        if not plannable:
            return []

        ordered = _order_topics(plannable, dependencies)

        weeks: list[WeekPlan] = [WeekPlan(week_number=1)]
        current = weeks[0]
        remaining_budget = config.max_weekly_workload_minutes

        for index, topic in enumerate(ordered):
            allocation = _clamp_topic_allocation(
                topic.workload_minutes, config
            )

            if allocation > remaining_budget:
                if len(weeks) >= config.total_weeks:
                    raise ValueError(
                        "Content does not fit in the requested number of "
                        f"weeks ({config.total_weeks}). Increase total_weeks "
                        "or reduce topic workload estimates."
                    )
                current = WeekPlan(week_number=len(weeks) + 1)
                weeks.append(current)
                remaining_budget = config.max_weekly_workload_minutes

            current.allocations.append(
                TopicAllocation(
                    topic_id=topic.topic_id,
                    title=topic.title,
                    allocated_minutes=allocation,
                    difficulty=topic.difficulty,
                    order_index=index,
                    learning_objectives=tuple(topic.learning_objectives),
                )
            )
            current.learning_objectives.extend(topic.learning_objectives)
            remaining_budget -= allocation

        return self._spread_to_horizon(
            weeks, config.total_weeks, config.max_weekly_workload_minutes
        )

    @staticmethod
    def _spread_to_horizon(
        weeks: list[WeekPlan],
        total_weeks: int,
        max_weekly_workload_minutes: int,
    ) -> list[WeekPlan]:
        """
        Dilute a packed plan across the full requested horizon.

        The greedy packing uses fewer weeks than requested whenever the
        content is light. To honour an exact course length, every
        allocation is re-projected onto the full horizon by linear
        interpolation over the ordered allocation list: topic order is
        preserved, each week receives at least one topic whenever the
        number of topics is at least the number of weeks, and any week
        that would exceed the workload budget spills its trailing
        allocation one week forward (deterministic, order-preserving).
        """
        if len(weeks) >= total_weeks:
            return weeks

        allocations = [allocation for week in weeks for allocation in week.allocations]
        count = len(allocations)
        if count == 0:
            return weeks

        buckets: list[list[TopicAllocation]] = [
            [] for _ in range(total_weeks)
        ]
        for index, allocation in enumerate(allocations):
            slot = index * total_weeks // count
            buckets[slot].append(allocation)

        for slot in range(total_weeks):
            while (
                buckets[slot]
                and FourMonthPlanner._sum_minutes(buckets[slot])
                > max_weekly_workload_minutes
                and slot + 1 < total_weeks
            ):
                buckets[slot + 1].insert(0, buckets[slot].pop())

        spread: list[WeekPlan] = [
            WeekPlan(week_number=week_number)
            for week_number in range(1, total_weeks + 1)
        ]
        for slot, week in enumerate(spread):
            week.allocations = buckets[slot]
            for allocation in buckets[slot]:
                week.learning_objectives.extend(allocation.learning_objectives)

        return spread

    @staticmethod
    def _sum_minutes(allocations: list[TopicAllocation]) -> int:
        return sum(
            allocation.allocated_minutes for allocation in allocations
        )