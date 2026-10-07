"""Repository for Dependency persistence operations."""

from __future__ import annotations

import uuid

from app.models.dependency import Dependency
from app.models.topic import Topic
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased


class DependencyRepository:
    """Data-access layer for Dependency records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_document(self, document_id: uuid.UUID) -> list[Dependency]:
        """Return all dependency edges whose topic belongs to a document."""
        stmt = (
            select(Dependency)
            .join(Topic, Topic.id == Dependency.topic_id)
            .where(Topic.document_id == document_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def prerequisite_titles_by_topic(
        self, topic_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[str]]:
        """Return titles for persisted prerequisite edges, keyed by topic."""
        if not topic_ids:
            return {}
        dependent_topic = aliased(Topic)
        prerequisite_topic = aliased(Topic)
        stmt = (
            select(Dependency.topic_id, prerequisite_topic.title)
            .join(dependent_topic, dependent_topic.id == Dependency.topic_id)
            .join(
                prerequisite_topic,
                prerequisite_topic.id == Dependency.depends_on_topic_id,
            )
            .where(
                Dependency.topic_id.in_(topic_ids),
                dependent_topic.document_id == prerequisite_topic.document_id,
            )
            .order_by(Dependency.topic_id, prerequisite_topic.title)
        )
        result = await self._session.execute(stmt)
        prerequisites: dict[uuid.UUID, list[str]] = {}
        for topic_id, title in result.all():
            prerequisites.setdefault(topic_id, []).append(title)
        return prerequisites

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
