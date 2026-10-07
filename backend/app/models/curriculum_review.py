"""CurriculumReview model: a lecturer's review decision on a generated curriculum."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class ReviewDecision(str, enum.Enum):
    """Review decisions a lecturer can make on a curriculum."""

    APPROVED = "approved"
    REJECTED = "rejected"


class CurriculumReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A single lecturer review of a generated curriculum.

    Created when a curriculum transition between AWAITING_REVIEW and
    APPROVED/REJECTED, preserving the reviewer's name, decision, and
    optional comments for accountability.
    """

    __tablename__ = "curriculum_reviews"

    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curricula.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    reviewer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    decision: Mapped[ReviewDecision] = mapped_column(
        Enum(
            ReviewDecision,
            name="review_decision",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<CurriculumReview id={self.id} curriculum_id={self.curriculum_id} "
            f"decision={self.decision}>"
        )
