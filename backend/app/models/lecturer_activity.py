"""LearnerActivity model: one event surfaced on the lecturer review feed."""

from __future__ import annotations

import enum
import uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


class LecturerActivityType(str, enum.Enum):
    """The kinds of learner progress events the lecturer feed shows."""

    ENROLLED = "enrolled"
    WITHDREW = "withdrew"
    LESSON_COMPLETED = "lesson_completed"
    SUBMISSION_RECEIVED = "submission_received"
    SUBMISSION_GRADED = "submission_graded"
    SUBMISSION_RETURNED = "submission_returned"


class LecturerActivity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One learner-progress event for the lecturer's review feed.

    Written by the learner and lecturer services whenever a learner
    enrols, completes a lesson or hands in work, and whenever a
    lecturer grades or returns a submission, so a lecturer sees course
    activity without opening each learner's record.

    ``actor_user_id`` is who performed the action; ``subject_user_id``
    is the learner it concerns (the same account for self-service
    events). ``details`` carries event-specific extras such as the
    lesson title or the grade awarded.
    """

    __tablename__ = "lecturer_activities"

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    subject_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    event_type: Mapped[LecturerActivityType] = mapped_column(
        Enum(
            LecturerActivityType,
            name="lecturer_activity_type",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        index=True,
    )

    summary: Mapped[str] = mapped_column(String(500), nullable=False)

    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<LecturerActivity id={self.id} course_id={self.course_id} "
            f"event={self.event_type.value} summary={self.summary!r}>"
        )
