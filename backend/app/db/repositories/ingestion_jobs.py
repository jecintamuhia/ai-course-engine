"""Repository for IngestionJob persistence and validated state transitions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.ingestion_job import IngestionJob, IngestionState
from app.services.ingestion.state_machine import validate_transition
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

_TERMINAL_STATES = {IngestionState.COMPLETED, IngestionState.CANCELLED}
_FAILED_STATE = IngestionState.FAILED


class IngestionJobRepository:
    """Data-access layer for IngestionJob records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, job_id: uuid.UUID) -> IngestionJob | None:
        """Fetch a job by primary key."""
        return await self._session.get(IngestionJob, job_id)

    async def get_active_for_document(
        self, document_id: uuid.UUID
    ) -> IngestionJob | None:
        """
        Return an existing non-terminal job for a document, if any.

        Used to make job creation idempotent: a document with an
        in-flight job returns that job instead of creating a duplicate.
        FAILED jobs are not considered active so a new job can be
        created after a previous one exhausted its retries.
        """
        stmt = (
            select(IngestionJob)
            .where(
                IngestionJob.document_id == document_id,
                IngestionJob.status.not_in(_TERMINAL_STATES | {_FAILED_STATE}),
            )
            .order_by(IngestionJob.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def latest_by_document(self, document_id: uuid.UUID) -> IngestionJob | None:
        """Return the most recently created job for a document, if any."""
        stmt = (
            select(IngestionJob)
            .where(IngestionJob.document_id == document_id)
            .order_by(IngestionJob.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_stale_pending(self, older_than: datetime) -> list[IngestionJob]:
        """
        Return jobs stuck in PENDING for longer than the given cutoff.

        Used by reconciliation to recover jobs that were persisted but
        never (or no longer) able to progress through the worker.
        """
        stmt = select(IngestionJob).where(
            IngestionJob.status == IngestionState.PENDING,
            IngestionJob.created_at < older_than,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_document(
        self, document_id: uuid.UUID, *, limit: int | None = None
    ) -> list[IngestionJob]:
        """Return all jobs for a document, newest first (optionally capped)."""
        stmt = (
            select(IngestionJob)
            .where(IngestionJob.document_id == document_id)
            .order_by(IngestionJob.created_at.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_in_progress(self) -> int:
        """
        Count jobs still running (not in a terminal/failed state).

        Used by the dashboard to report how many documents are currently
        processing through the ingestion pipeline.
        """
        stmt = select(func.count(func.distinct(IngestionJob.document_id))).where(
            IngestionJob.status.not_in(_TERMINAL_STATES | {_FAILED_STATE})
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def add(self, job: IngestionJob) -> IngestionJob:
        """Stage a new job for persistence."""
        self._session.add(job)
        await self._session.flush()
        return job

    async def transition(self, job: IngestionJob, target_state: IngestionState) -> None:
        """
        Move a job to target_state, validating the transition first.

        Raises InvalidStateTransition (via validate_transition) if the
        move is not permitted from the job's current state. Sets
        started_at on first leaving PENDING, and completed_at on
        reaching a terminal state.
        """
        validate_transition(job.status, target_state)

        if (
            job.status == IngestionState.PENDING
            and target_state == IngestionState.VALIDATING
        ):
            job.attempt_count += 1
            job.started_at = datetime.now(UTC)

        job.status = target_state

        if target_state in _TERMINAL_STATES:
            job.completed_at = datetime.now(UTC)

        if target_state == IngestionState.FAILED:
            job.completed_at = datetime.now(UTC)

        await self._session.flush()

    async def fail(self, job: IngestionJob, error_message: str) -> None:
        """Transition a job to FAILED and record the error."""
        job.error_message = error_message
        await self.transition(job, IngestionState.FAILED)

    async def retry(self, job: IngestionJob) -> bool:
        """
        Attempt to retry a FAILED job by transitioning it back to PENDING.

        Returns True if the retry was scheduled (attempts remain), or
        False if the job has exhausted max_attempts and stays FAILED.
        Does not itself re-enqueue the job in Redis — the caller is
        responsible for that.
        """
        if job.attempt_count >= job.max_attempts:
            return False

        job.completed_at = None
        await self.transition(job, IngestionState.PENDING)
        return True

    async def cancel(self, job: IngestionJob) -> None:
        """Cancel a job, validating that it is not already in a terminal state."""
        await self.transition(job, IngestionState.CANCELLED)

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()
