"""Repository for Dependency persistence operations."""

from __future__ import annotations

import uuid

from app.models.dependency import Dependency
from app.models.topic import Topic
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession


class DependencyRepository:
    """Data-access layer for Dependency records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_document(
        self, document_id: uuid.UUID
    ) -> list[Dependency]:
        """Return all dependency edges whose topic belongs to a document."""
        stmt = (
            select(Dependency)
            .join(Topic, Topic.id == Dependency.topic_id)
            .where(Topic.document_id == document_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_document(self, document_id: uuid.UUID) -> None:
        """
        Delete all dependency edges whose topic belongs to a document,
        for idempotent re-building of the graph.
        """
        subquery = (
            select(Topic.id).where(Topic.document_id == document_id)
        ).scalar_subquery()

        stmt = delete(Dependency).where(Dependency.topic_id.in_(subquery))
        await self._session.execute(stmt)
        await self._session.flush()

    async def add_many(self, dependencies: list[Dependency]) -> list[Dependency]:
        """Stage multiple dependency edges for persistence."""
        if dependencies:
            self._session.add_all(dependencies)
            await self._session.flush()
        return dependencies

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()