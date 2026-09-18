"""Repository for Page persistence operations."""

from __future__ import annotations

import uuid

from app.models.page import Page
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession


class PageRepository:
    """Data-access layer for Page records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_document(self, document_id: uuid.UUID) -> list[Page]:
        """Return all pages for a document, ordered by page number."""
        stmt = (
            select(Page)
            .where(Page.document_id == document_id)
            .order_by(Page.page_number)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_document(self) -> dict[uuid.UUID, int]:
        """Return page counts grouped by document id."""
        stmt = select(Page.document_id, func.count()).group_by(Page.document_id)
        result = await self._session.execute(stmt)
        return {row[0]: int(row[1]) for row in result.all()}

    async def delete_by_document(self, document_id: uuid.UUID) -> None:
        """
        Delete all existing pages for a document.

        Called before re-inserting pages so re-extraction is idempotent
        rather than accumulating duplicate rows.
        """
        stmt = delete(Page).where(Page.document_id == document_id)
        await self._session.execute(stmt)
        await self._session.flush()

    async def add_many(self, pages: list[Page]) -> list[Page]:
        """Stage multiple pages for persistence."""
        self._session.add_all(pages)
        await self._session.flush()
        return pages

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()
