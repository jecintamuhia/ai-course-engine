"""PracticalSubmission model: a learner's hand-in for one practical task."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class SubmissionStatus(str, enum.Enum):
    """Review state of a practical submission."""

    SUBMITTED = "submitted"
    GRADED = "graded"
    NEEDS_REVISION = "needs_revision"


class PracticalSubmission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A learner's text/markdown hand-in for one ``practical_task`` block.

    One row per (enrolment, block): handing in again after feedback
    updates the existing row and moves it back to ``SUBMITTED``; a
    ``GRADED`` row is terminal until a lecturer returns it for
    revision. ``lesson_id`` is denormalised from the block so lecturer
    review queries can reach the course through the lesson without an
    extra join. Marks are 0-100.
    """

    __tablename__ = "practical_submissions"
    __table_args__ = (
        UniqueConstraint(
            "enrolment_id", "block_id", name="uq_practical_submissions_enrolment_id"
        ),
        CheckConstraint("grade >= 0 AND grade <= 100", name="grade_range"),
    )

    enrolment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learner_enrolments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    block_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lesson_content_blocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(
            SubmissionStatus,
            name="submission_status",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=SubmissionStatus.SUBMITTED,
        index=True,
    )

    grade: Mapped[int | None] = mapped_column(Integer, nullable=True)

    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    graded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    graded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<PracticalSubmission id={self.id} block_id={self.block_id} "
            f"status={self.status.value} grade={self.grade}>"
        )
