"""Repository for Topic, Concept, and provenance persistence operations."""

from __future__ import annotations

import uuid

from app.models.chapter import Chapter
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

    async def list_flat_by_document(
        self, document_id: uuid.UUID, *, exclude_duplicates: bool = False
    ) -> list[Topic]:
        """
        Return every topic row for a document (top-level topics and
        subtopics) as a flat list, ordered.

        The curriculum service passes this flat list straight to the
        planner, which assembles subtree aggregates from
        ``parent_topic_id`` pointers instead of walking the ORM
        relationship graph — that keeps the planner free of database
        lazy loads.

        ``concepts`` and ``source_chunk_links`` are eagerly loaded
        because the canonicalization pass (``apply_canonicalization``)
        classifies importance from concept counts and sizes evidence
        from source-chunk links; doing so lazily inside an async
        session would raise ``MissingGreenlet``.

        When ``exclude_duplicates`` is true, topics flagged as
        duplicates (``duplicate_of_id`` set) are omitted, so the
        canonical topic inventory drives curriculum generation without
        accidental repetition.
        """
        stmt = select(Topic).where(Topic.document_id == document_id)
        if exclude_duplicates:
            stmt = stmt.where(Topic.duplicate_of_id.is_(None))
        stmt = stmt.options(
            selectinload(Topic.concepts),
            selectinload(Topic.source_chunk_links),
        ).order_by(Topic.order_index)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_duplicates_by_document(self, document_id: uuid.UUID) -> list[Topic]:
        """
        Return every topic row flagged as a duplicate (``duplicate_of_id``
        set) for a document, ordered — used by QA coverage reporting.
        """
        stmt = (
            select(Topic)
            .where(
                Topic.document_id == document_id,
                Topic.duplicate_of_id.is_not(None),
            )
            .order_by(Topic.order_index)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_top_level_by_document(self, document_id: uuid.UUID) -> list[Topic]:
        """
        Return all top-level topics for a document, ordered. Unlike
        ``list_by_document`` this does not eager load subtopics/concepts,
        which keeps canonicalization and QA passes light.
        """
        stmt = (
            select(Topic)
            .where(
                Topic.document_id == document_id,
                Topic.parent_topic_id.is_(None),
            )
            .order_by(Topic.order_index)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_in_reading_order(
        self, document_id: uuid.UUID
    ) -> tuple[list[Topic], dict[uuid.UUID, str]]:
        """
        Return every top-level topic for a document ordered the way a
        reader meets them, plus a chapter-id to chapter-label map.

        ``list_by_document`` orders by ``order_index`` alone, which is
        scoped to a chapter, so it interleaves chapters unpredictably.
        Prerequisite linking has to reason about what comes *earlier* in
        the book, so it needs the real order: chapter reading order first,
        then position within the chapter. Topics with no chapter are kept
        and sort last, matching where an un-chaptered document lands.
        """
        chapter_rows = (
            await self._session.execute(
                select(Chapter.id, Chapter.number, Chapter.order_index)
                .where(Chapter.document_id == document_id)
                .order_by(Chapter.order_index, Chapter.id)
            )
        ).all()

        chapter_order = {
            chapter_id: index for index, (chapter_id, _, _) in enumerate(chapter_rows)
        }
        chapter_labels = {
            chapter_id: ((number or "").strip() or str(order_index + 1))
            for chapter_id, number, order_index in chapter_rows
        }

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
        )
        topics = list((await self._session.execute(stmt)).scalars().unique())

        topics.sort(
            key=lambda topic: (
                chapter_order.get(topic.chapter_id, len(chapter_order)),
                topic.order_index,
                str(topic.id),
            )
        )

        return topics, chapter_labels

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
