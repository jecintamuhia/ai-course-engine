"""Certificate model: proof that a learner completed and passed a course."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class Certificate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A verifiable certificate issued once per learner per course.

    The learner's name and course title are snapshotted so verification
    keeps reporting what was true when the certificate was issued, even
    if the course is later renamed. ``reference`` is the public lookup
    code; the unique ``(user_id, course_id)`` constraint makes issuance
    idempotent and blocks duplicate certificates.
    """

    __tablename__ = "certificates"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "course_id",
            name="uq_certificates_user_id",
        ),
        CheckConstraint(
            "score_percent >= 0 AND score_percent <= 100",
            name="score_range",
        ),
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

    enrolment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learner_enrolments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
    )

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_attempts.id", ondelete="CASCADE"),
        nullable=False,
    )

    reference: Mapped[str] = mapped_column(
        String(40), nullable=False, unique=True
    )

    learner_name: Mapped[str] = mapped_column(String(300), nullable=False)
    course_title: Mapped[str] = mapped_column(String(500), nullable=False)

    score_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_lessons: Mapped[int] = mapped_column(Integer, nullable=False)
    total_lessons: Mapped[int] = mapped_column(Integer, nullable=False)

    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Certificate id={self.id} reference={self.reference}>"
