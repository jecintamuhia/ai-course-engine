"""Unit tests for bulk content-generation job progress accounting.

The regression these guard: a run whose LLM calls all fail (e.g. an
exhausted provider balance returning HTTP 402) used to increment
``completed_weeks`` and finish as COMPLETED, so the UI reported a fully
generated course while several weeks held no lessons at all.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from app.models.content_generation_job import (
    ContentGenerationJob,
    ContentGenerationState,
)
from app.models.curriculum import CurriculumStatus
from app.workers.content_worker import _process_job


class _FakeUnit:
    def __init__(self, week_number: int, topic_count: int = 4) -> None:
        self.id = uuid.uuid4()
        self.week_number = week_number
        self.topic_links = [
            SimpleNamespace(topic_id=uuid.uuid4()) for _ in range(topic_count)
        ]


class _FakeCurriculum:
    def __init__(self, units: list[_FakeUnit]) -> None:
        self.id = uuid.uuid4()
        self.status = CurriculumStatus.APPROVED
        self.units = units


class _FakeJob:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.curriculum_id = uuid.uuid4()
        self.status = ContentGenerationState.PENDING
        self.correlation_id = "corr"
        self.total_weeks = 0
        self.completed_weeks = 0
        self.lessons_generated = 0
        self.skipped_weeks = 0
        self.failed_weeks = 0
        self.rebuild_existing = False
        self.error_message: str | None = None
        self.completed_at = None

        self.is_terminal = False
        self.is_partial = False

    def _refresh(self) -> None:
        self.is_terminal = self.status in {
            ContentGenerationState.COMPLETED,
            ContentGenerationState.FAILED,
            ContentGenerationState.CANCELLED,
        }
        self.is_partial = self.failed_weeks > 0 and self.lessons_generated > 0

    async def start(self) -> None:
        self.status = ContentGenerationState.RUNNING
        self._refresh()

    async def record_week(
        self,
        job,
        *,
        lessons_generated: int,
        skipped: bool = False,
        failed: bool = False,
    ) -> None:
        if failed:
            self.failed_weeks += 1
        else:
            self.completed_weeks += 1
        self.lessons_generated += lessons_generated
        if skipped:
            self.skipped_weeks += 1
        self._refresh()

    async def complete(self, job) -> None:
        self.status = ContentGenerationState.COMPLETED
        self._refresh()

    async def fail(self, job, error_message: str) -> None:
        self.status = ContentGenerationState.FAILED
        self.error_message = error_message
        self._refresh()


class _FakeJobRepository:
    """Mirrors ContentGenerationJobRepository, delegating to the fake job."""

    def __init__(self, job: _FakeJob) -> None:
        self._job = job

    async def get_by_id(self, job_id):
        return self._job

    async def start(self, job) -> None:
        await self._job.start()

    async def record_week(
        self,
        job,
        *,
        lessons_generated: int,
        skipped: bool = False,
        failed: bool = False,
    ) -> None:
        await self._job.record_week(
            job, lessons_generated=lessons_generated, skipped=skipped, failed=failed
        )

    async def complete(self, job) -> None:
        await self._job.complete(job)

    async def fail(self, job, error_message: str) -> None:
        await self._job.fail(job, error_message)

    async def commit(self) -> None:
        return None


class _FakeUnitRepository:
    def __init__(self, counts: dict[uuid.UUID, int]) -> None:
        self._counts = counts

    async def get_by_id_for_content(self, curriculum_id):
        return self._curriculum

    async def count_unit_topics(self, unit_ids):
        return {unit_id: self._counts.get(unit_id, 0) for unit_id in unit_ids}


class _FakeLessonRepository:
    def __init__(
        self,
        existing: dict[uuid.UUID, list],
        relinked: int = 0,
    ) -> None:
        self._existing = existing
        self.relinked = relinked
        self.relink_calls: list[uuid.UUID] = []

    async def list_by_unit(self, unit_id):
        return self._existing.get(unit_id, [])

    async def relink_orphan_lessons(self, curriculum_id):
        self.relink_calls.append(curriculum_id)
        return self.relinked


async def _run(
    *,
    units: list[_FakeUnit],
    results: dict[int, dict],
    topic_counts: dict[uuid.UUID, int],
    existing: dict[uuid.UUID, list] | None = None,
    relinked: int = 0,
):
    job = _FakeJob()
    job.total_weeks = len(units)

    curriculum = _FakeCurriculum(units)

    unit_repo = _FakeUnitRepository(topic_counts)
    unit_repo._curriculum = curriculum

    job_repository = _FakeJobRepository(job)
    lesson_repository = _FakeLessonRepository(existing or {}, relinked=relinked)
    job.lesson_repository = lesson_repository

    session = AsyncMock()
    session.get = AsyncMock(return_value=None)

    class _Factory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return session

        async def __aexit__(self, *exc_info):
            return False

    # Patch the repositories the worker constructs from the session.
    import app.workers.content_worker as worker

    original = (
        worker.ContentGenerationJobRepository,
        worker.CurriculumRepository,
        worker.ChunkRepository,
        worker.LessonRepository,
        worker.CourseContentService,
    )

    worker.ContentGenerationJobRepository = lambda _s: job_repository
    worker.CurriculumRepository = lambda _s: unit_repo
    worker.ChunkRepository = lambda _s: AsyncMock()
    worker.LessonRepository = lambda _s: lesson_repository
    worker.CourseContentService = lambda *a, **k: Mock(
        generate_week=AsyncMock(
            side_effect=lambda unit_id, **kwargs: results[
                next(u.week_number for u in units if u.id == unit_id)
            ]
        )
    )

    try:
        await _process_job(str(job.id), _Factory(), AsyncMock(), AsyncMock())
    finally:
        (
            worker.ContentGenerationJobRepository,
            worker.CurriculumRepository,
            worker.ChunkRepository,
            worker.LessonRepository,
            worker.CourseContentService,
        ) = original

    return job


def _ok(unit: _FakeUnit, lessons: int = 4) -> dict:
    return {
        "generated": [
            SimpleNamespace(topic_id=link.topic_id)
            for link in unit.topic_links[:lessons]
        ],
        "errors": [],
        "skipped": [],
    }


def _all_failed() -> dict:
    return {
        "generated": [],
        "errors": [{"error": "HTTP 402: insufficient credits", "component": "llm"}],
    }


async def test_all_weeks_generated_marks_completed() -> None:
    units = [_FakeUnit(1), _FakeUnit(2)]
    job = await _run(
        units=units,
        results={1: _ok(units[0]), 2: _ok(units[1])},
        topic_counts={u.id: 4 for u in units},
    )

    assert job.status is ContentGenerationState.COMPLETED
    assert job.completed_weeks == 2
    assert job.failed_weeks == 0
    assert job.lessons_generated == 8


async def test_credit_exhaustion_does_not_report_completed() -> None:
    """A provider-wide failure must not be reported as a finished course."""
    units = [_FakeUnit(1), _FakeUnit(2)]
    job = await _run(
        units=units,
        results={1: _ok(units[0]), 2: _all_failed()},
        topic_counts={u.id: 4 for u in units},
    )

    assert job.status is ContentGenerationState.FAILED
    assert job.completed_weeks == 1
    assert job.failed_weeks == 1
    assert job.lessons_generated == 4
    assert "1 of 2 weeks remain incomplete" in (job.error_message or "")
    assert "week 2" not in (job.error_message or "")
    assert "402" in (job.error_message or "")


async def test_failed_weeks_are_listed_in_the_error() -> None:
    units = [_FakeUnit(w) for w in (1, 2, 3)]
    job = await _run(
        units=units,
        results={1: _ok(units[0]), 2: _all_failed(), 3: _all_failed()},
        topic_counts={u.id: 4 for u in units},
    )

    assert job.status is ContentGenerationState.FAILED
    assert job.completed_weeks == 1
    assert job.failed_weeks == 2
    assert "weeks 2, 3" in (job.error_message or "")
    assert job.is_partial is True


async def test_unit_with_no_topics_is_not_a_failure() -> None:
    """An empty unit legitimately generates nothing; it is not a failure."""
    units = [_FakeUnit(1), _FakeUnit(2, topic_count=0)]
    job = await _run(
        units=units,
        results={1: _ok(units[0]), 2: _all_failed()},
        topic_counts={units[0].id: 4, units[1].id: 0},
    )

    assert job.status is ContentGenerationState.COMPLETED
    assert job.failed_weeks == 0
    assert job.completed_weeks == 2


async def test_skipped_weeks_count_as_completed() -> None:
    units = [_FakeUnit(1), _FakeUnit(2)]
    job = await _run(
        units=units,
        results={2: _ok(units[1])},
        topic_counts={u.id: 4 for u in units},
        existing={
            units[0].id: [
                SimpleNamespace(topic_id=link.topic_id)
                for link in units[0].topic_links
            ]
        },
    )

    assert job.status is ContentGenerationState.COMPLETED
    assert job.completed_weeks == 2
    assert job.skipped_weeks == 1
    assert job.lessons_generated == 4


async def test_partial_week_remains_failed_and_retryable() -> None:
    """A week missing mapped topics is not treated as complete."""
    units = [_FakeUnit(1, topic_count=5)]
    job = await _run(
        units=units,
        results={
            1: {
                "generated": [
                    SimpleNamespace(topic_id=units[0].topic_links[0].topic_id),
                    SimpleNamespace(topic_id=units[0].topic_links[1].topic_id),
                ],
                "errors": [{"error": "generation failed"}],
                "skipped": [],
            }
        },
        topic_counts={units[0].id: 5},
    )

    assert job.status is ContentGenerationState.FAILED
    assert job.completed_weeks == 0
    assert job.failed_weeks == 1
    assert job.lessons_generated == 2


async def test_worker_repairs_orphan_lessons_at_job_start() -> None:
    """Orphans are relinked before week processing so retries self-heal."""
    units = [_FakeUnit(1)]
    job = await _run(
        units=units,
        results={1: _ok(units[0])},
        topic_counts={units[0].id: 4},
        relinked=3,
    )

    assert job.status is ContentGenerationState.COMPLETED
    assert job.lesson_repository.relink_calls == [job.curriculum_id]


def test_failed_weeks_column_defaults_to_zero() -> None:
    """The column carries a DB-side default of 0 for existing rows."""
    column = ContentGenerationJob.__table__.c.failed_weeks
    assert column.nullable is False
    assert column.default.arg == 0
    assert column.server_default is not None


@pytest.mark.parametrize(
    ("failed", "lessons", "expected"),
    [(0, 0, False), (1, 0, False), (1, 4, True), (2, 8, True)],
)
def test_is_partial(failed: int, lessons: int, expected: bool) -> None:
    job = _FakeJob()
    job.failed_weeks = failed
    job.lessons_generated = lessons
    job._refresh()
    assert job.is_partial is expected
