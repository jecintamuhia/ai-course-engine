"""Repository for lecturer activity feed persistence operations."""

from __future__ import annotations

import uuid

from app.models.lecturer_activity import LecturerActivity
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class LecturerActivityRepository:
    """Data-access layer for the lecturer activity feed."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, activity: LecturerActivity) -> LecturerActivity:
        """Stage a new activity record for persistence."""
        self._session.add(activity)
        await self._session.flush()
        return activity

    async def list_by_course(
        self,
        course_id: uuid.UUID,
        limit: int = 50,
    ) -> list[LecturerActivity]:
        """Return the most recent activity records for a course."""
        stmt = (
            select(LecturerActivity)
            .where(LecturerActivity.course_id == course_id)
            .order_by(LecturerActivity.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()
