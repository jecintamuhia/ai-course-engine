"""LessonSourceChunk: provenance link between a Lesson and its citing Chunks."""

from __future__ import annotations

import uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class LessonSourceChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Links a Lesson to a Chunk the AI cited as supporting evidence.

    This is the provenance edge for course content: Lesson ->
    LessonSourceChunk -> Chunk -> Page -> Document is fully traceable,
    mirroring the TopicSourceChunk relationship used by topic extraction.
    """

    __tablename__ = "lesson_source_chunks"
    __table_args__ = (
        UniqueConstraint(
            "lesson_id", "chunk_id", name="uq_lesson_source_chunks_lesson_chunk"
        ),
    )

    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<LessonSourceChunk lesson_id={self.lesson_id} chunk_id={self.chunk_id}>"
        )
