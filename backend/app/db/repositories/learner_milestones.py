"""Repository for learner milestone (lesson completion) persistence operations."""

from __future__ import annotations

import uuid

from app.models.learner_milestone import LearnerMilestone
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class LearnerMilestoneRepository:
    """Data-access layer for per-lesson completion milestones."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, milestone: LearnerMilestone) -> LearnerMilestone:
        """Stage a new milestone for persistence."""
        self._session.add(milestone)
        await self._session.flush()
        return milestone

    async def get(
        self,
        enrolment_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> LearnerMilestone | None:
        """Fetch the milestone for a lesson within an enrolment."""
        stmt = select(LearnerMilestone).where(
            LearnerMilestone.enrolment_id == enrolment_id,
            LearnerMilestone.lesson_id == lesson_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_enrolment(
        self, enrolment_id: uuid.UUID
    ) -> list[LearnerMilestone]:
        """Return every milestone in an enrolment, oldest completion first."""
        stmt = (
            select(LearnerMilestone)
            .where(LearnerMilestone.enrolment_id == enrolment_id)
            .order_by(LearnerMilestone.completed_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_enrolment(self, enrolment_id: uuid.UUID) -> int:
        """Count the completed lessons in an enrolment."""
        stmt = (
            select(func.count())
            .select_from(LearnerMilestone)
            .where(LearnerMilestone.enrolment_id == enrolment_id)
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def delete(self, milestone: LearnerMilestone) -> None:
        """Remove a milestone."""
        await self._session.delete(milestone)

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()
