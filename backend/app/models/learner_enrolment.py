"""LearnerEnrolment model: a learner's opt-in to a published course."""

from __future__ import annotations

import enum
import uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class EnrolmentStatus(str, enum.Enum):
    """Lifecycle of a learner's enrolment in one course."""

    ACTIVE = "active"
    WITHDRAWN = "withdrawn"


class LearnerEnrolment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One learner's enrolment in one published course.

    Learners self-enrol from the learner portal, so ``created_at`` is
    the enrolment date. Withdrawing flips ``status`` to ``WITHDRAWN``
    instead of deleting the row, keeping milestones and submissions
    intact if the learner re-enrols later.
    """

    __tablename__ = "learner_enrolments"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", name="uq_learner_enrolments_user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[EnrolmentStatus] = mapped_column(
        Enum(
            EnrolmentStatus,
            name="enrolment_status",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=EnrolmentStatus.ACTIVE,
        index=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<LearnerEnrolment id={self.id} user_id={self.user_id} "
            f"course_id={self.course_id} status={self.status.value}>"
        )
