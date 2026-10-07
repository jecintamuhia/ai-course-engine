"""Repository for ContentGenerationJob persistence."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.content_generation_job import (
    ContentGenerationJob,
    ContentGenerationState,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_ACTIVE_STATES = {
    ContentGenerationState.PENDING,
    ContentGenerationState.RUNNING,
}


class ContentGenerationJobRepository:
    """Data-access layer for ContentGenerationJob records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, job_id: uuid.UUID) -> ContentGenerationJob | None:
        """Fetch a job by primary key."""
        return await self._session.get(ContentGenerationJob, job_id)

    async def get_active_for_curriculum(
        self, curriculum_id: uuid.UUID
    ) -> ContentGenerationJob | None:
        """
        Return the in-flight job for a curriculum, if any.

        Used to make enqueueing idempotent: a curriculum that already has a
        PENDING/RUNNING generation job returns it instead of starting a
        second concurrent run over the same units.
        """
        stmt = (
            select(ContentGenerationJob)
            .where(
                ContentGenerationJob.curriculum_id == curriculum_id,
                ContentGenerationJob.status.in_(_ACTIVE_STATES),
            )
            .order_by(ContentGenerationJob.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def latest_by_curriculum(
        self, curriculum_id: uuid.UUID
    ) -> ContentGenerationJob | None:
        """Return the most recently created job for a curriculum, if any."""
        stmt = (
            select(ContentGenerationJob)
            .where(ContentGenerationJob.curriculum_id == curriculum_id)
            .order_by(ContentGenerationJob.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_stale_running(
        self, older_than: datetime
    ) -> list[ContentGenerationJob]:
        """
        Return RUNNING jobs whose worker died mid-generation.

        Progress is committed per week, so reconciliation only has to
        re-enqueue the job: ``generate_week`` skips units that already
        have APPROVED lessons and is safe to re-run over the rest.
        """
        stmt = select(ContentGenerationJob).where(
            ContentGenerationJob.status == ContentGenerationState.RUNNING,
            ContentGenerationJob.updated_at < older_than,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, job: ContentGenerationJob) -> ContentGenerationJob:
        """Stage a new job for persistence."""
        self._session.add(job)
        await self._session.flush()
        return job

    async def start(self, job: ContentGenerationJob) -> None:
        """Mark a job as running and stamp its start time."""
        job.status = ContentGenerationState.RUNNING
        if job.started_at is None:
            job.started_at = datetime.now(UTC)
        await self._session.flush()

    async def record_week(
        self,
        job: ContentGenerationJob,
        *,
        lessons_generated: int,
        skipped: bool = False,
        failed: bool = False,
    ) -> None:
        """
        Persist progress after one week is finished with.

        Committed by the worker between weeks so the UI can poll live
        progress and a crash resumes from the next unfinished unit.

        A ``failed`` week increments ``failed_weeks`` instead of
        ``completed_weeks``. Weeks are only "completed" once they actually
        hold lessons (or were already populated and deliberately skipped),
        so a provider-wide failure cannot be reported as success.
        """
        if failed:
            job.failed_weeks += 1
        else:
            job.completed_weeks += 1
        job.lessons_generated += lessons_generated
        if skipped:
            job.skipped_weeks += 1
        await self._session.flush()

    async def complete(self, job: ContentGenerationJob) -> None:
        """Mark a job finished."""
        job.status = ContentGenerationState.COMPLETED
        job.completed_at = datetime.now(UTC)
        await self._session.flush()

    async def fail(self, job: ContentGenerationJob, error_message: str) -> None:
        """Mark a job failed and record the error."""
        job.status = ContentGenerationState.FAILED
        job.error_message = error_message[:4000]
        job.completed_at = datetime.now(UTC)
        await self._session.flush()

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()

    async def rollback(self) -> None:
        """Roll back the current transaction."""
        await self._session.rollback()
