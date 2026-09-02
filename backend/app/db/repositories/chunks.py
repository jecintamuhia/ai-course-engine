"""Repository for Chunk persistence operations."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk


class ChunkRepository:
    """Data-access layer for Chunk records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_document(self, document_id: uuid.UUID) -> list[Chunk]:
        """Return all chunks for a document, in document order."""
        stmt = (
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.document_index)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_document(self, document_id: uuid.UUID) -> None:
        """Delete all existing chunks for a document, for idempotent re-chunking."""
        stmt = delete(Chunk).where(Chunk.document_id == document_id)
        await self._session.execute(stmt)
        await self._session.flush()

    async def add_many(self, chunks: list[Chunk]) -> list[Chunk]:
        """Stage multiple chunks for persistence."""
        self._session.add_all(chunks)
        await self._session.flush()
        return chunks

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()