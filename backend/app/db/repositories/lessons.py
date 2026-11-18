"""Repository for Lesson, LessonContentBlock, and LessonSourceChunk records."""

from __future__ import annotations

import uuid

from app.models.chunks import Chunk
from app.models.curriculum_unit_topic import CurriculumUnitTopic
from app.models.lesson import Lesson, LessonStatus
from app.models.lesson_content_block import LessonContentBlock
from app.models.lesson_source_chunk import LessonSourceChunk
from app.models.page import Page
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class LessonRepository:
    """Data-access layer for lessons and their blocks/provenance."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_unit(self, curriculum_unit_id: uuid.UUID) -> list[Lesson]:
        """Return lessons for one weekly unit, with blocks eager-loaded."""
        stmt = (
            select(Lesson)
            .where(Lesson.curriculum_unit_id == curriculum_unit_id)
            .options(selectinload(Lesson.content_blocks))
            .order_by(Lesson.order_index)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all())

    async def list_by_curriculum(self, curriculum_id: uuid.UUID) -> list[Lesson]:
        """Return all lessons for a curriculum, with blocks eager-loaded."""
        stmt = (
            select(Lesson)
            .where(Lesson.curriculum_id == curriculum_id)
            .options(selectinload(Lesson.content_blocks))
            .order_by(Lesson.week_number, Lesson.order_index)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all())

    async def list_publishable_by_curriculum(
        self, curriculum_id: uuid.UUID
    ) -> list[Lesson]:
        """
        Return APPROVED lessons for a curriculum, ordered by week then
        lesson position, with content blocks eager-loaded. Used by the
        Moodle publisher to attach lesson pages to a course.
        """
        stmt = (
            select(Lesson)
            .where(
                Lesson.curriculum_id == curriculum_id,
                Lesson.status == LessonStatus.APPROVED,
            )
            .options(selectinload(Lesson.content_blocks))
            .order_by(Lesson.week_number, Lesson.order_index)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all())

    async def relink_orphan_lessons(self, curriculum_id: uuid.UUID) -> int:
        """
        Restore lesson → topic links for lessons whose ``topic_id`` is NULL.

        Lessons are generated one per planned unit topic, in topic order,
        so a lesson's ``order_index`` identifies its ``CurriculumUnitTopic``
        within the same unit. Only lessons with a NULL ``topic_id`` are
        fetched; existing links are never rewritten. An orphan without a
        matching (unit, order_index) link is left untouched and not counted.

        Returns the number of relinked lessons.
        """
        stmt = select(Lesson).where(
            Lesson.curriculum_id == curriculum_id,
            Lesson.topic_id.is_(None),
        )
        result = await self._session.execute(stmt)
        orphans = list(result.scalars().all())
        if not orphans:
            return 0

        unit_ids = {lesson.curriculum_unit_id for lesson in orphans}
        link_stmt = select(CurriculumUnitTopic).where(
            CurriculumUnitTopic.curriculum_unit_id.in_(unit_ids)
        )
        link_result = await self._session.execute(link_stmt)
        mapping = {
            (link.curriculum_unit_id, link.order_index): link.topic_id
            for link in link_result.scalars().all()
        }

        relinked = 0
        for lesson in orphans:
            if lesson.topic_id is not None:
                continue
            topic_id = mapping.get(
                (lesson.curriculum_unit_id, lesson.order_index)
            )
            if topic_id is None:
                continue
            lesson.topic_id = topic_id
            relinked += 1

        if relinked:
            await self._session.flush()
        return relinked

    async def delete_not_approved_by_topics(
        self, curriculum_unit_id: uuid.UUID, topic_ids: set[uuid.UUID]
    ) -> None:
        """
        Delete non-approved lessons in a weekly unit for specific topics.

        Regeneration replaces lessons topic by topic, so only topics whose
        lesson was successfully regenerated are deleted. Topics whose
        regeneration failed or was skipped keep their existing lesson
        rather than losing it. Approved lessons are never deleted.
        """
        if not topic_ids:
            return
        stmt = delete(Lesson).where(
            Lesson.curriculum_unit_id == curriculum_unit_id,
            Lesson.status != LessonStatus.APPROVED,
            Lesson.topic_id.in_(topic_ids),
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_by_id(self, lesson_id: uuid.UUID) -> Lesson | None:
        """Fetch a single lesson with blocks and source links loaded."""
        stmt = (
            select(Lesson)
            .where(Lesson.id == lesson_id)
            .options(
                selectinload(Lesson.content_blocks),
                selectinload(Lesson.source_chunk_links),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_block_by_id(self, block_id: uuid.UUID) -> LessonContentBlock | None:
        """Fetch a single content block."""
        stmt = select(LessonContentBlock).where(LessonContentBlock.id == block_id)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def add(self, lesson: Lesson) -> Lesson:
        """Stage a new lesson (with its blocks/source links) for persistence."""
        self._session.add(lesson)
        await self._session.flush()
        return lesson

    async def delete_by_unit(self, curriculum_unit_id: uuid.UUID) -> None:
        """Delete all lessons for a weekly unit (cascades to blocks/links)."""
        stmt = delete(Lesson).where(Lesson.curriculum_unit_id == curriculum_unit_id)
        await self._session.execute(stmt)
        await self._session.flush()

    async def delete_block(self, block: LessonContentBlock) -> None:
        """Delete a single content block."""
        await self._session.delete(block)
        await self._session.flush()

    async def add_source_links(
        self, links: list[LessonSourceChunk]
    ) -> list[LessonSourceChunk]:
        """Stage lesson-to-chunk provenance links for persistence."""
        if links:
            self._session.add_all(links)
            await self._session.flush()
        return links

    async def get_provenance_chain(
        self, lesson_id: uuid.UUID
    ) -> list[tuple[LessonSourceChunk, Chunk, Page]]:
        """
        Return the (LessonSourceChunk, Chunk, Page) tuples supporting a
        lesson, ordered by document reading order.
        """
        stmt = (
            select(LessonSourceChunk, Chunk, Page)
            .join(Chunk, Chunk.id == LessonSourceChunk.chunk_id)
            .join(Page, Page.id == Chunk.page_id)
            .where(LessonSourceChunk.lesson_id == lesson_id)
            .order_by(Chunk.document_index)
        )
        result = await self._session.execute(stmt)
        return [(row.LessonSourceChunk, row.Chunk, row.Page) for row in result]

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()

    async def rollback(self) -> None:
        """Roll back the current transaction."""
        await self._session.rollback()
