"""Repository for Page persistence operations."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.page import Page


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