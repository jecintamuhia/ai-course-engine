"""Regression tests for orphan-lesson relinking.

Lessons generated before topic linkage existed carry ``topic_id = NULL``,
which breaks coverage, provenance, and QA. The repair restores links from
the deterministic (unit, order_index) mapping without ever rewriting a
link that already exists.
"""

from __future__ import annotations

import asyncio
import uuid

from app.db.repositories.lessons import LessonRepository
from app.models.curriculum_unit_topic import CurriculumUnitTopic
from app.models.lesson import Lesson


class _FakeResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self) -> _FakeResult:
        return self

    def all(self) -> list:
        return self._rows


class _FakeSession:
    def __init__(self, lessons: list[Lesson], links: list[CurriculumUnitTopic]):
        self._lessons = lessons
        self._links = links
        self.flushes = 0
        self.queries: list[str] = []

    async def execute(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        if entity is Lesson:
            self.queries.append("lessons")
            return _FakeResult(self._lessons)
        if entity is CurriculumUnitTopic:
            self.queries.append("links")
            return _FakeResult(self._links)
        raise AssertionError(f"unexpected query for {entity}")

    async def flush(self) -> None:
        self.flushes += 1


def _lesson(
    *, unit_id: uuid.UUID, order_index: int, topic_id: uuid.UUID | None = None
) -> Lesson:
    return Lesson(
        id=uuid.uuid4(),
        curriculum_id=uuid.uuid4(),
        curriculum_unit_id=unit_id,
        topic_id=topic_id,
        week_number=1,
        order_index=order_index,
        title=f"Lesson {order_index}",
        description="d",
        learning_objectives=["LO"],
        estimated_workload_minutes=60,
    )


def _link(*, unit_id: uuid.UUID, order_index: int) -> CurriculumUnitTopic:
    return CurriculumUnitTopic(
        id=uuid.uuid4(),
        curriculum_unit_id=unit_id,
        topic_id=uuid.uuid4(),
        order_index=order_index,
    )


def _relink(session: _FakeSession) -> int:
    repo = LessonRepository(session)
    return asyncio.run(repo.relink_orphan_lessons(uuid.uuid4()))


def test_relinks_orphans_by_unit_and_order_index() -> None:
    unit_id = uuid.uuid4()
    orphan0 = _lesson(unit_id=unit_id, order_index=0)
    orphan1 = _lesson(unit_id=unit_id, order_index=1)
    link0 = _link(unit_id=unit_id, order_index=0)
    link1 = _link(unit_id=unit_id, order_index=1)

    session = _FakeSession([orphan0, orphan1], [link0, link1])

    assert _relink(session) == 2
    assert orphan0.topic_id == link0.topic_id
    assert orphan1.topic_id == link1.topic_id
    assert session.flushes == 1


def test_orphan_without_matching_link_stays_unlinked() -> None:
    unit_id = uuid.uuid4()
    orphan = _lesson(unit_id=unit_id, order_index=5)
    link = _link(unit_id=unit_id, order_index=0)

    session = _FakeSession([orphan], [link])

    assert _relink(session) == 0
    assert orphan.topic_id is None
    assert session.flushes == 0


def test_returns_zero_without_touching_links_query_when_no_orphans() -> None:
    session = _FakeSession([], [])

    assert _relink(session) == 0
    assert session.queries == ["lessons"]
    assert session.flushes == 0


def test_existing_links_are_never_overwritten() -> None:
    unit_id = uuid.uuid4()
    existing_topic = uuid.uuid4()
    linked = _lesson(unit_id=unit_id, order_index=0, topic_id=existing_topic)
    link = _link(unit_id=unit_id, order_index=0)

    session = _FakeSession([linked], [link])

    assert _relink(session) == 0
    assert linked.topic_id == existing_topic
