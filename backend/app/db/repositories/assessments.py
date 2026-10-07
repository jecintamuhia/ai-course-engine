"""Repository for persisted Assessment records."""

from __future__ import annotations

import uuid

from app.models.assessment import Assessment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class AssessmentRepository:
    """Data-access layer for assessment records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, assessment: Assessment) -> Assessment:
        """Stage an assessment for persistence."""
        self._session.add(assessment)
        await self._session.flush()
        return assessment

    async def get_by_id(self, assessment_id: uuid.UUID) -> Assessment | None:
        """Fetch a single assessment by id."""
        stmt = select(Assessment).where(Assessment.id == assessment_id)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_by_curriculum(self, curriculum_id: uuid.UUID) -> list[Assessment]:
        """Return all assessments for a curriculum, newest first."""
        stmt = (
            select(Assessment)
            .where(Assessment.curriculum_id == curriculum_id)
            .order_by(
                Assessment.week_number.asc().nulls_last(),
                Assessment.created_at.asc(),
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_unit(self, curriculum_unit_id: uuid.UUID) -> list[Assessment]:
        """Return assessments attached to one weekly unit."""
        stmt = (
            select(Assessment)
            .where(Assessment.curriculum_unit_id == curriculum_unit_id)
            .order_by(Assessment.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()
