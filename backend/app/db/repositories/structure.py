"""Repository for Chapter and Section persistence operations."""

from __future__ import annotations

import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.models.chapter import Chapter
from app.models.section import Section


class StructureRepository:
    """Data-access layer for Chapter and Section records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_chapters_by_document(
        self, document_id: uuid.UUID
    ) -> list[Chapter]:
        """Return all chapters (with sections eagerly loaded) for a document."""
        stmt = (
            select(Chapter)
            .where(Chapter.document_id == document_id)
            .options(selectinload(Chapter.sections))
            .order_by(Chapter.order_index)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_document(self, document_id: uuid.UUID) -> None:
        """
        Delete all existing chapters (and cascading sections) for a
        document, so re-detection is idempotent.
        """
        stmt = delete(Chapter).where(Chapter.document_id == document_id)
        await self._session.execute(stmt)
        await self._session.flush()

    async def add_chapters(self, chapters: list[Chapter]) -> list[Chapter]:
        """Stage chapters (with their nested sections) for persistence."""
        self._session.add_all(chapters)
        await self._session.flush()
        return chapters

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()