"""LearnerMilestone model: one lesson a learner marked complete."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow
from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class LearnerMilestone(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A lesson completion recorded by an enrolled learner.

    The row *is* the completion: it exists once the learner marks the
    lesson complete and disappears if they undo the mark, so no separate
    status enum is needed. Progress for an enrolment is the count of its
    milestones over the number of approved lessons in the course.
    """

    __tablename__ = "learner_milestones"
    __table_args__ = (
        UniqueConstraint(
            "enrolment_id", "lesson_id", name="uq_learner_milestones_enrolment_id"
        ),
    )

    enrolment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learner_enrolments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<LearnerMilestone id={self.id} enrolment_id={self.enrolment_id} "
            f"lesson_id={self.lesson_id}>"
        )
