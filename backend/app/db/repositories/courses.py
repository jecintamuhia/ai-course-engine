"""Repository for Course (Moodle publication) persistence operations."""

from __future__ import annotations

import uuid

from app.models.course import Course
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class CourseRepository:
    """Data-access layer for published Course records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, course: Course) -> Course:
        """Stage a new course record for persistence."""
        self._session.add(course)
        await self._session.flush()
        return course

    async def count_all(self) -> int:
        """Count all published course records."""
        stmt = select(func.count()).select_from(Course)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_by_id(self, course_id: uuid.UUID) -> Course | None:
        """Fetch a course record by primary key."""
        return await self._session.get(Course, course_id)

    async def get_by_curriculum(self, curriculum_id: uuid.UUID) -> Course | None:
        """Fetch the course record for a curriculum, if published."""
        stmt = select(Course).where(Course.curriculum_id == curriculum_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_idnumber(self, idnumber: str) -> Course | None:
        """Fetch a course record by its Moodle idnumber."""
        stmt = select(Course).where(Course.idnumber == idnumber)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Course]:
        """Return all published course records, newest first."""
        stmt = select(Course).order_by(Course.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()
