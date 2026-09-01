"""Repository for Document persistence operations."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus


class DocumentRepository:
    """Data-access layer for Document records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        """Fetch a document by primary key."""
        return await self._session.get(Document, document_id)

    async def get_latest_by_hash(self, sha256_hash: str) -> Document | None:
        """
        Fetch the latest-version document matching a content hash, if any.

        Used for duplicate-content detection at upload time.
        """
        stmt = select(Document).where(
            Document.sha256_hash == sha256_hash,
            Document.is_latest_version.is_(True),
            Document.status != DocumentStatus.DELETED,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add(self, document: Document) -> Document:
        """Stage a new document for persistence."""
        self._session.add(document)
        await self._session.flush()
        return document

    async def mark_superseded(self, document: Document) -> None:
        """Mark a document as no longer the latest version."""
        document.is_latest_version = False
        document.status = DocumentStatus.SUPERSEDED
        await self._session.flush()

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()