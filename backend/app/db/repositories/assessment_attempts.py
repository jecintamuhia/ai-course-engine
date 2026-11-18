"""Repository for persisted assessment attempts."""

from __future__ import annotations

import uuid

from app.models.assessment_attempt import AssessmentAttempt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class AssessmentAttemptRepository:
    """Data-access layer for learner assessment attempts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, attempt: AssessmentAttempt) -> AssessmentAttempt:
        """Stage an attempt for persistence."""
        self._session.add(attempt)
        await self._session.flush()
        return attempt

    async def get_by_id(self, attempt_id: uuid.UUID) -> AssessmentAttempt | None:
        """Fetch a single attempt by id."""
        stmt = select(AssessmentAttempt).where(AssessmentAttempt.id == attempt_id)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_for_enrolment(
        self,
        assessment_id: uuid.UUID,
        enrolment_id: uuid.UUID,
    ) -> list[AssessmentAttempt]:
        """Return every attempt at an assessment for one enrolment."""
        stmt = (
            select(AssessmentAttempt)
            .where(
                AssessmentAttempt.assessment_id == assessment_id,
                AssessmentAttempt.enrolment_id == enrolment_id,
            )
            .order_by(AssessmentAttempt.attempt_number.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_enrolment(
        self,
        assessment_id: uuid.UUID,
        enrolment_id: uuid.UUID,
    ) -> int:
        """Count the attempts already recorded for an enrolment."""
        stmt = (
            select(func.count())
            .select_from(AssessmentAttempt)
            .where(
                AssessmentAttempt.assessment_id == assessment_id,
                AssessmentAttempt.enrolment_id == enrolment_id,
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def best_passing(
        self,
        assessment_id: uuid.UUID,
        enrolment_id: uuid.UUID,
    ) -> AssessmentAttempt | None:
        """Return the highest-scoring passing attempt, if any."""
        stmt = (
            select(AssessmentAttempt)
            .where(
                AssessmentAttempt.assessment_id == assessment_id,
                AssessmentAttempt.enrolment_id == enrolment_id,
                AssessmentAttempt.passed.is_(True),
            )
            .order_by(
                AssessmentAttempt.score_percent.desc(),
                AssessmentAttempt.attempt_number.asc(),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()

    async def rollback(self) -> None:
        """Roll back the current transaction."""
        await self._session.rollback()
