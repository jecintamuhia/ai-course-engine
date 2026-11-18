"""Repository for learner enrolment persistence operations."""

from __future__ import annotations

import uuid

from app.models.learner_enrolment import EnrolmentStatus, LearnerEnrolment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class LearnerEnrolmentRepository:
    """Data-access layer for learner enrolments in published courses."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, enrolment: LearnerEnrolment) -> LearnerEnrolment:
        """Stage a new enrolment for persistence."""
        self._session.add(enrolment)
        await self._session.flush()
        return enrolment

    async def get_by_id(self, enrolment_id: uuid.UUID) -> LearnerEnrolment | None:
        """Fetch an enrolment by primary key."""
        return await self._session.get(LearnerEnrolment, enrolment_id)

    async def get(
        self,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> LearnerEnrolment | None:
        """Fetch a learner's enrolment in a course regardless of status."""
        stmt = select(LearnerEnrolment).where(
            LearnerEnrolment.user_id == user_id,
            LearnerEnrolment.course_id == course_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active(
        self,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> LearnerEnrolment | None:
        """Fetch a learner's active enrolment in a course."""
        stmt = select(LearnerEnrolment).where(
            LearnerEnrolment.user_id == user_id,
            LearnerEnrolment.course_id == course_id,
            LearnerEnrolment.status == EnrolmentStatus.ACTIVE,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: uuid.UUID) -> list[LearnerEnrolment]:
        """Return every enrolment belonging to a learner, newest first."""
        stmt = (
            select(LearnerEnrolment)
            .where(LearnerEnrolment.user_id == user_id)
            .order_by(LearnerEnrolment.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_active_by_user(self, user_id: uuid.UUID) -> list[LearnerEnrolment]:
        """Return the learner's active enrolments, newest first."""
        stmt = (
            select(LearnerEnrolment)
            .where(
                LearnerEnrolment.user_id == user_id,
                LearnerEnrolment.status == EnrolmentStatus.ACTIVE,
            )
            .order_by(LearnerEnrolment.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_active_course_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        """Return the ids of the courses the learner is actively enrolled in."""
        stmt = select(LearnerEnrolment.course_id).where(
            LearnerEnrolment.user_id == user_id,
            LearnerEnrolment.status == EnrolmentStatus.ACTIVE,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_active_by_course(
        self, course_id: uuid.UUID
    ) -> list[LearnerEnrolment]:
        """Return every active enrolment in a course, newest first."""
        stmt = (
            select(LearnerEnrolment)
            .where(
                LearnerEnrolment.course_id == course_id,
                LearnerEnrolment.status == EnrolmentStatus.ACTIVE,
            )
            .order_by(LearnerEnrolment.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()
