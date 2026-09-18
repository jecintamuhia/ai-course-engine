"""Curriculum model: a structured, generated curriculum for a document."""

from __future__ import annotations

import enum
import uuid
from datetime import date

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class CurriculumStatus(str, enum.Enum):
    """Lifecycle status of a generated curriculum."""

    DRAFT = "draft"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


class Curriculum(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A structured curriculum generated deterministically from a
    document's extracted topics.

    ``total_weeks`` is fully configurable — 16 is only the default.
    Nothing in this model or the planning code is hardcoded to any
    particular number of weeks.

    ``version_number``/``is_latest_version`` support multiple curriculum
    drafts per document: each generation call creates a new Curriculum
    version (deliberately NOT idempotent), and callers can compare drafts
    before deciding which to review/approve/publish.

    ``status`` lifecycle is driven by ``CurriculumService`` and enforced
    in code — publishing an unapproved curriculum raises an error.
    """

    __tablename__ = "curricula"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[CurriculumStatus] = mapped_column(
        Enum(
            CurriculumStatus,
            name="curriculum_status",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=CurriculumStatus.DRAFT,
        index=True,
    )

    # ------------------------------------------------------------------
    # Planning configuration (nothing hardcoded to 16 weeks)
    # ------------------------------------------------------------------

    total_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    learning_days_per_week: Mapped[int] = mapped_column(Integer, nullable=False)
    hours_per_day: Mapped[int] = mapped_column(Integer, nullable=False)

    max_weekly_workload_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    min_topic_allocation_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    max_topic_allocation_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    # ------------------------------------------------------------------
    # Versioning
    # ------------------------------------------------------------------

    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_latest_version: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    units: Mapped[list[CurriculumUnit]] = relationship(
        "CurriculumUnit",
        cascade="all, delete-orphan",
        order_by="CurriculumUnit.week_number",
        back_populates="curriculum",
    )

    reviews: Mapped[list[CurriculumReview]] = relationship(
        "CurriculumReview",
        cascade="all, delete-orphan",
        order_by="CurriculumReview.reviewed_at",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<Curriculum id={self.id} document_id={self.document_id} "
            f"version={self.version_number} status={self.status}>"
        )
