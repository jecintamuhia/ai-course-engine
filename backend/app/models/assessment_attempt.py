"""AssessmentAttempt model: one learner's submitted answer sheet."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


class AssessmentAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One submitted attempt at an assessment.

    Attempts are append-only: a retry creates a new row with the next
    ``attempt_number`` instead of mutating an earlier result, so the
    learner's history and the certificate decision stay auditable. The
    unique constraint prevents two concurrent submissions from claiming
    the same attempt number.
    """

    __tablename__ = "assessment_attempts"
    __table_args__ = (
        UniqueConstraint(
            "assessment_id",
            "enrolment_id",
            "attempt_number",
            name="uq_assessment_attempts_assessment_id",
        ),
        CheckConstraint(
            "score_percent >= 0 AND score_percent <= 100",
            name="score_range",
        ),
    )

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    enrolment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learner_enrolments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)

    answers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    results: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    correct_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    auto_gradable_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    score_percent: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    passed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<AssessmentAttempt id={self.id} assessment_id={self.assessment_id} "
            f"attempt={self.attempt_number} score={self.score_percent}>"
        )
