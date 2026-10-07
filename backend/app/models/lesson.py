"""Lesson model: one generated, lecturer-reviewable lesson within a week."""

from __future__ import annotations

import enum
import uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import ARRAY, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class LessonStatus(str, enum.Enum):
    """Lifecycle status of a generated lesson."""

    DRAFT = "draft"
    GENERATING = "generating"
    FAILED = "failed"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class Lesson(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A single generated lesson that teaches the topics scheduled into one
    weekly unit of an approved curriculum.

    ``content_blocks`` hold the actual teaching blocks (text, diagrams,
    activities, knowledge checks, ...) in reading order, each carrying
    its own review state. ``source_chunk_links`` (via LessonSourceChunk)
    provide the per-lesson provenance back to the source material that
    grounded the generation.

    ``generation_errors`` records per-component failures or skips (for
    example an external-resource URL that failed validation or video
    discovery being disabled) so the lecturer can see what was NOT
    generated instead of silently receiving partial content.
    """

    __tablename__ = "lessons"

    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curricula.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    curriculum_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    learning_objectives: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    estimated_workload_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    status: Mapped[LessonStatus] = mapped_column(
        Enum(
            LessonStatus,
            name="lesson_status",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=LessonStatus.DRAFT,
        index=True,
    )

    generation_errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    reviewer_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    review_comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    content_blocks: Mapped[list[LessonContentBlock]] = relationship(
        "LessonContentBlock",
        cascade="all, delete-orphan",
        order_by="LessonContentBlock.order_index",
    )

    source_chunk_links: Mapped[list[LessonSourceChunk]] = relationship(
        "LessonSourceChunk",
        cascade="all, delete-orphan",
    )

    @property
    def blocks(self) -> list[LessonContentBlock]:
        """
        Alias for ``content_blocks`` so the ``from_attributes`` read
        schema ``LessonRead.blocks`` maps to the ordered content blocks.
        """
        return self.content_blocks

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<Lesson id={self.id} week={self.week_number} "
            f"title={self.title!r} status={self.status}>"
        )
