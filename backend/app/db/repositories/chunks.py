"""Repository for Chunk persistence operations."""

from __future__ import annotations

import uuid

from app.models.chunks import Chunk
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession


class ChunkRepository:
    """Data-access layer for Chunk records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_ids(self, chunk_ids: list[uuid.UUID]) -> list[Chunk]:
        """Return chunks by their ids, in document reading order."""
        if not chunk_ids:
            return []
        stmt = (
            select(Chunk).where(Chunk.id.in_(chunk_ids)).order_by(Chunk.document_index)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_document(self, document_id: uuid.UUID) -> list[Chunk]:
        """Return all chunks for a document, in document order."""
        stmt = (
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.document_index)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_document(self) -> dict[uuid.UUID, int]:
        """Return chunk counts grouped by document id."""
        stmt = select(Chunk.document_id, func.count()).group_by(Chunk.document_id)
        result = await self._session.execute(stmt)
        return {row[0]: int(row[1]) for row in result.all()}

    async def delete_by_document(self, document_id: uuid.UUID) -> None:
        """Delete all existing chunks for a document, for idempotent re-chunking."""
        stmt = delete(Chunk).where(Chunk.document_id == document_id)
        await self._session.execute(stmt)
        await self._session.flush()

    async def add_many(self, chunks: list[Chunk]) -> list[Chunk]:
        """Stage chunks for persistence."""
        self._session.add_all(chunks)
        await self._session.flush()
        return chunks

    async def relink_to_structure(
        self,
        chunks: list[Chunk],
        assignments: dict[uuid.UUID, tuple[uuid.UUID | None, uuid.UUID | None]],
    ) -> int:
        """
        Re-point existing chunks at a freshly detected chapter/section
        structure, keyed by chunk id.

        Structure detection replaces the Chapter rows, so any chunk that
        already referenced the previous ones is left pointing at ids that
        no longer exist. Left alone, analysis then finds every chapter
        empty and silently produces no topics. Re-detecting structure must
        therefore re-link chunks instead of relying on the caller to
        remember to re-chunk.

        ``chunks`` must be the rows loaded by this session, so the dirty
        attributes flush as ordinary ORM updates. Setting the ids is used
        rather than a bulk ``UPDATE ... CASE`` because SQLAlchemy's
        multi-values form needs ORM-specific compilation options and
        asyncpg rejects the mapping form.

        Returns the number of chunks actually changed.
        """
        updated = 0

        for chunk in chunks:
            target = assignments.get(chunk.id)

            if target is None:
                continue

            chapter_id, section_id = target

            if chunk.chapter_id == chapter_id and chunk.section_id == section_id:
                continue

            chunk.chapter_id = chapter_id
            chunk.section_id = section_id
            updated += 1

        await self._session.flush()
        return updated

    async def count_unlinked_by_document(self, document_id: uuid.UUID) -> int:
        """Count chunks for a document that are not attached to a chapter."""
        stmt = (
            select(func.count())
            .select_from(Chunk)
            .where(
                Chunk.document_id == document_id,
                Chunk.chapter_id.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()
