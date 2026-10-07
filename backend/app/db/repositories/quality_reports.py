"""Repository for persisted QualityReport records."""

from __future__ import annotations

import uuid

from app.models.quality_report import QualityReport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class QualityReportRepository:
    """Data-access layer for content-QA report records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, report: QualityReport) -> QualityReport:
        """Stage a QA report for persistence."""
        self._session.add(report)
        await self._session.flush()
        return report

    async def get_latest_by_curriculum(
        self, curriculum_id: uuid.UUID
    ) -> QualityReport | None:
        """Return the most recent QA report for a curriculum, if any."""
        stmt = (
            select(QualityReport)
            .where(QualityReport.curriculum_id == curriculum_id)
            .order_by(QualityReport.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()
