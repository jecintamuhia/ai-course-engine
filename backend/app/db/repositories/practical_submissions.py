"""Repository for practical task submission persistence operations."""

from __future__ import annotations

import uuid

from app.models.learner_enrolment import LearnerEnrolment
from app.models.practical_submission import PracticalSubmission, SubmissionStatus
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class PracticalSubmissionRepository:
    """Data-access layer for practical task hand-ins."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, submission: PracticalSubmission) -> PracticalSubmission:
        """Stage a new submission for persistence."""
        self._session.add(submission)
        await self._session.flush()
        return submission

    async def get_by_id(self, submission_id: uuid.UUID) -> PracticalSubmission | None:
        """Fetch a submission by primary key."""
        return await self._session.get(PracticalSubmission, submission_id)

    async def get(
        self,
        enrolment_id: uuid.UUID,
        block_id: uuid.UUID,
    ) -> PracticalSubmission | None:
        """Fetch the submission for a block within an enrolment."""
        stmt = select(PracticalSubmission).where(
            PracticalSubmission.enrolment_id == enrolment_id,
            PracticalSubmission.block_id == block_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_enrolment(
        self, enrolment_id: uuid.UUID
    ) -> list[PracticalSubmission]:
        """Return every submission in an enrolment, newest first."""
        stmt = (
            select(PracticalSubmission)
            .where(PracticalSubmission.enrolment_id == enrolment_id)
            .order_by(PracticalSubmission.submitted_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_course(self, course_id: uuid.UUID) -> list[PracticalSubmission]:
        """Return every submission made towards a course, newest first."""
        stmt = (
            select(PracticalSubmission)
            .join(
                LearnerEnrolment,
                LearnerEnrolment.id == PracticalSubmission.enrolment_id,
            )
            .where(LearnerEnrolment.course_id == course_id)
            .order_by(PracticalSubmission.submitted_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_pending_by_course(
        self, course_id: uuid.UUID
    ) -> list[PracticalSubmission]:
        """Return the course's submissions that are still awaiting review."""
        stmt = (
            select(PracticalSubmission)
            .join(
                LearnerEnrolment,
                LearnerEnrolment.id == PracticalSubmission.enrolment_id,
            )
            .where(
                LearnerEnrolment.course_id == course_id,
                PracticalSubmission.status == SubmissionStatus.SUBMITTED,
            )
            .order_by(PracticalSubmission.submitted_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()
