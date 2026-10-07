"""Repository for Curriculum and CurriculumUnit persistence operations."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from app.models.curriculum import Curriculum, CurriculumStatus
from app.models.curriculum_review import CurriculumReview
from app.models.curriculum_unit import CurriculumUnit
from app.models.curriculum_unit_topic import CurriculumUnitTopic
from app.models.topic import Topic
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class CurriculumRepository:
    """Data-access layer for Curriculum records and their units/reviews."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, curriculum: Curriculum) -> Curriculum:
        """Stage a new curriculum (with units and topic links) for persistence."""
        self._session.add(curriculum)
        await self._session.flush()
        return curriculum

    async def count_by_status(self, status: CurriculumStatus) -> int:
        """Count latest-version curricula in the given status."""
        stmt = (
            select(func.count())
            .select_from(Curriculum)
            .where(
                Curriculum.status == status,
                Curriculum.is_latest_version.is_(True),
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def count_latest_by_document(self) -> dict[uuid.UUID, int]:
        """Return latest-version curriculum counts grouped by document id."""
        stmt = (
            select(Curriculum.document_id, func.count())
            .where(Curriculum.is_latest_version.is_(True))
            .group_by(Curriculum.document_id)
        )
        result = await self._session.execute(stmt)
        return {row[0]: int(row[1]) for row in result.all()}

    async def get_by_id(self, curriculum_id: uuid.UUID) -> Curriculum | None:
        """
        Fetch a curriculum by ID, eagerly loading its weekly units,
        their topic links/topics, and its review history.
        """
        stmt = (
            select(Curriculum)
            .where(Curriculum.id == curriculum_id)
            .options(
                selectinload(Curriculum.units)
                .selectinload(CurriculumUnit.topic_links)
                .selectinload(CurriculumUnitTopic.topic),
                selectinload(Curriculum.reviews),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_by_id_for_content(
        self, curriculum_id: uuid.UUID
    ) -> Curriculum | None:
        """
        Fetch a curriculum with the graph needed for course-content
        generation: weekly units with their topic links, each planned
        topic with its subtopics and their source-chunk provenance links.
        """
        stmt = (
            select(Curriculum)
            .where(Curriculum.id == curriculum_id)
            .options(
                selectinload(Curriculum.units)
                .selectinload(CurriculumUnit.topic_links)
                .selectinload(CurriculumUnitTopic.topic)
                .selectinload(Topic.subtopics)
                .selectinload(Topic.source_chunk_links),
                selectinload(Curriculum.units)
                .selectinload(CurriculumUnit.topic_links)
                .selectinload(CurriculumUnitTopic.topic)
                .selectinload(Topic.source_chunk_links),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_by_document(self, document_id: uuid.UUID) -> list[Curriculum]:
        """Return all curricula for a document, newest version first."""
        stmt = (
            select(Curriculum)
            .where(Curriculum.document_id == document_id)
            .options(
                selectinload(Curriculum.units)
                .selectinload(CurriculumUnit.topic_links)
                .selectinload(CurriculumUnitTopic.topic),
            )
            .order_by(Curriculum.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all())

    async def get_unit_by_id(self, unit_id: uuid.UUID) -> CurriculumUnit | None:
        """Fetch a single weekly unit with its topic links loaded."""
        stmt = (
            select(CurriculumUnit)
            .where(CurriculumUnit.id == unit_id)
            .options(
                selectinload(CurriculumUnit.topic_links).selectinload(
                    CurriculumUnitTopic.topic
                )
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def count_unit_topics(
        self, unit_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, int]:
        """
        Count planned topics per unit in one query.

        The bulk content worker needs this to tell a genuinely empty week
        apart from a week that failed: a unit with no topics legitimately
        produces no lessons, while a unit *with* topics that produced none
        has failed and must not be reported as complete.
        """
        if not unit_ids:
            return {}

        stmt = (
            select(
                CurriculumUnitTopic.curriculum_unit_id,
                func.count(CurriculumUnitTopic.id),
            )
            .where(CurriculumUnitTopic.curriculum_unit_id.in_(unit_ids))
            .group_by(CurriculumUnitTopic.curriculum_unit_id)
        )
        result = await self._session.execute(stmt)
        return {unit_id: count for unit_id, count in result.all()}

    async def get_unit_with_lesson_context(
        self, unit_id: uuid.UUID
    ) -> CurriculumUnit | None:
        """
        Fetch a weekly unit with the graph needed for lesson generation:
        topic links with each planned topic, its subtopics, and their
        source-chunk provenance links.
        """
        stmt = (
            select(CurriculumUnit)
            .where(CurriculumUnit.id == unit_id)
            .options(
                selectinload(CurriculumUnit.topic_links)
                .selectinload(CurriculumUnitTopic.topic)
                .selectinload(Topic.subtopics)
                .selectinload(Topic.source_chunk_links),
                selectinload(CurriculumUnit.topic_links)
                .selectinload(CurriculumUnitTopic.topic)
                .selectinload(Topic.concepts),
                selectinload(CurriculumUnit.topic_links)
                .selectinload(CurriculumUnitTopic.topic)
                .selectinload(Topic.source_chunk_links),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_latest_by_document(self, document_id: uuid.UUID) -> list[Curriculum]:
        """Return latest-version curricula for a document."""
        stmt = (
            select(Curriculum)
            .where(
                Curriculum.document_id == document_id,
                Curriculum.is_latest_version.is_(True),
            )
            .options(
                selectinload(Curriculum.units)
                .selectinload(CurriculumUnit.topic_links)
                .selectinload(CurriculumUnitTopic.topic),
            )
            .order_by(Curriculum.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all())

    async def latest_version_number(self, document_id: uuid.UUID) -> int:
        """Return the highest version_number existing for a document."""
        stmt = select(Curriculum.version_number).where(
            Curriculum.document_id == document_id
        )
        result = await self._session.execute(stmt)
        numbers = list(result.scalars().all())
        return max(numbers, default=0)

    async def mark_superseded(self, curriculum: Curriculum) -> None:
        """Mark a curriculum as no longer the latest version."""
        curriculum.is_latest_version = False
        await self._session.flush()

    async def add_review(self, review: CurriculumReview) -> CurriculumReview:
        """Stage a review record for persistence."""
        self._session.add(review)
        await self._session.flush()
        return review

    async def delete_by_document(self, document_id: uuid.UUID) -> None:
        """Delete all curricula for a document (cascades to units/reviews)."""
        stmt = delete(Curriculum).where(Curriculum.document_id == document_id)
        await self._session.execute(stmt)
        await self._session.flush()

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()
