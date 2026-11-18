"""LessonContentBlock model: one teaching block within a generated lesson."""

from __future__ import annotations

import enum
import uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


class LessonBlockType(str, enum.Enum):
    """The kinds of teaching content a lesson can contain."""

    TEXT = "text"
    HEADING = "heading"
    EXAMPLE = "example"
    DIAGRAM = "diagram"
    TABLE = "table"
    EXTERNAL_RESOURCE = "external_resource"
    VIDEO = "video"
    ACTIVITY = "activity"
    KNOWLEDGE_CHECK = "knowledge_check"
    SUMMARY = "summary"
    PRACTICAL_TASK = "practical_task"


class BlockReviewStatus(str, enum.Enum):
    """Per-block lecturer review state within an otherwise approved lesson."""

    GENERATED = "generated"
    APPROVED = "approved"
    REJECTED = "rejected"


class LessonContentBlock(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One teaching block of a lesson, in reading order.

    ``payload`` is a JSONB object whose shape depends on ``block_type``
    (validated by the Pydantic payload schemas in
    ``app.schemas.course_content``). Blocks are individually reviewable:
    a lecturer can approve/reject a single block without re-reviewing the
    whole lesson, and rejected blocks are excluded from Moodle publishing.
    """

    __tablename__ = "lesson_content_blocks"
    __table_args__ = (
        UniqueConstraint(
            "lesson_id", "order_index", name="uq_lesson_content_blocks_lesson_order"
        ),
    )

    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    block_type: Mapped[LessonBlockType] = mapped_column(
        Enum(
            LessonBlockType,
            name="lesson_block_type",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        index=True,
    )

    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    title: Mapped[str | None] = mapped_column(String(300), nullable=True)

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    review_status: Mapped[BlockReviewStatus] = mapped_column(
        Enum(
            BlockReviewStatus,
            name="block_review_status",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=BlockReviewStatus.GENERATED,
    )

    review_comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<LessonContentBlock id={self.id} lesson_id={self.lesson_id} "
            f"type={self.block_type.value} order={self.order_index}>"
        )
