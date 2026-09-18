"""Repository for Topic, Concept, and provenance persistence operations."""

from __future__ import annotations

import uuid

from app.models.chunks import Chunk
from app.models.page import Page
from app.models.topic import Topic
from app.models.topic_source_chunk import TopicSourceChunk
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class TopicRepository:
    """Data-access layer for Topic records and their provenance links."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_document(self, document_id: uuid.UUID) -> list[Topic]:
        """
        Return all top-level topics (parent_topic_id is null) for a
        document, with subtopics and concepts eagerly loaded, ordered.
        """
        stmt = (
            select(Topic)
            .where(
                Topic.document_id == document_id,
                Topic.parent_topic_id.is_(None),
            )
            .options(
                selectinload(Topic.subtopics).selectinload(Topic.concepts),
                selectinload(Topic.concepts),
            )
            .order_by(Topic.order_index)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all())

    async def list_flat_by_document(self, document_id: uuid.UUID) -> list[Topic]:
        """
        Return every topic row for a document (top-level topics and
        subtopics) as a flat list, ordered.

        The curriculum service passes this flat list straight to the
        planner, which assembles subtree aggregates from
        ``parent_topic_id`` pointers instead of walking the ORM
        relationship graph — that keeps the planner free of database
        lazy loads.
        """
        stmt = (
            select(Topic)
            .where(Topic.document_id == document_id)
            .order_by(Topic.order_index)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_chapter(self, chapter_id: uuid.UUID) -> list[Topic]:
        """
        Return all top-level topics for a chapter, with subtopics and
        concepts eagerly loaded, ordered. Used to skip re-analysis of
        chapters that already have persisted topics.
        """
        stmt = (
            select(Topic)
            .where(
                Topic.chapter_id == chapter_id,
                Topic.parent_topic_id.is_(None),
            )
            .options(
                selectinload(Topic.subtopics).selectinload(Topic.concepts),
                selectinload(Topic.concepts),
            )
            .order_by(Topic.order_index)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all())

    async def list_unassociated_by_document(
        self, document_id: uuid.UUID
    ) -> list[Topic]:
        """
        Return top-level topics persisted without a chapter (the
        whole-document-as-one-chapter fallback), with subtopics and
        concepts eagerly loaded, ordered.
        """
        stmt = (
            select(Topic)
            .where(
                Topic.document_id == document_id,
                Topic.chapter_id.is_(None),
                Topic.parent_topic_id.is_(None),
            )
            .options(
                selectinload(Topic.subtopics).selectinload(Topic.concepts),
                selectinload(Topic.concepts),
            )
            .order_by(Topic.order_index)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all())

    async def count_by_document(self) -> dict[uuid.UUID, int]:
        """Return top-level topic counts grouped by document id."""
        stmt = (
            select(Topic.document_id, func.count())
            .where(Topic.parent_topic_id.is_(None))
            .group_by(Topic.document_id)
        )
        result = await self._session.execute(stmt)
        return {row[0]: int(row[1]) for row in result.all()}

    async def get_by_id(self, topic_id: uuid.UUID) -> Topic | None:
        """Fetch a single topic by ID, with concepts eagerly loaded."""
        stmt = (
            select(Topic)
            .where(Topic.id == topic_id)
            .options(selectinload(Topic.concepts))
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_provenance_chain(
        self, topic_id: uuid.UUID
    ) -> list[tuple[Chunk, Page]]:
        """
        Return the (Chunk, Page) pairs that support a topic — the
        concrete Topic -> Chunk -> Page -> Document provenance chain.
        Document is reachable via Page.document_id on the caller side.
        """
        stmt = (
            select(Chunk, Page)
            .join(TopicSourceChunk, TopicSourceChunk.chunk_id == Chunk.id)
            .join(Page, Page.id == Chunk.page_id)
            .where(TopicSourceChunk.topic_id == topic_id)
            .order_by(Page.page_number)
        )
        result = await self._session.execute(stmt)
        return [(row.Chunk, row.Page) for row in result]

    async def delete_by_chapter(self, chapter_id: uuid.UUID) -> None:
        """
        Delete all top-level topics for a chapter (cascades to
        subtopics, concepts, and source-chunk links), for idempotent
        re-analysis.
        """
        stmt = delete(Topic).where(
            Topic.chapter_id == chapter_id,
            Topic.parent_topic_id.is_(None),
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def delete_by_document(self, document_id: uuid.UUID) -> None:
        """
        Delete all top-level topics for a document with no chapter
        association (fallback single-implicit-chapter case).
        """
        stmt = delete(Topic).where(
            Topic.document_id == document_id,
            Topic.chapter_id.is_(None),
            Topic.parent_topic_id.is_(None),
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def add_many(self, topics: list[Topic]) -> list[Topic]:
        """Stage top-level topics (with nested subtopics/concepts) for persistence."""
        self._session.add_all(topics)
        await self._session.flush()
        return topics

    async def add_source_links(
        self, links: list[TopicSourceChunk]
    ) -> list[TopicSourceChunk]:
        """Stage topic-to-chunk provenance links for persistence."""
        if links:
            self._session.add_all(links)
            await self._session.flush()
        return links

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()
