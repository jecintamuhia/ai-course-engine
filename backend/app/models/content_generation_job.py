"""ContentGenerationJob model: tracks bulk lesson generation across a curriculum."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class ContentGenerationState(str, enum.Enum):
    """Lifecycle of a bulk lesson-generation run over a curriculum."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ContentGenerationJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A background job that generates lessons for every weekly unit of an
    approved curriculum.

    Generating a full 16-week course is thousands of LLM calls and takes
    far longer than a single request can hold open, so it runs on the
    content worker. ``completed_weeks`` / ``lessons_generated`` are
    committed after each week so the review UI can show live progress and
    so a restarted worker resumes from where it stopped rather than
    regenerating everything.

    ``error_message`` records the first fatal error; per-week and
    per-topic failures are recorded on the lessons themselves
    (``generation_errors``) and never invented over.

    By default the worker only fills in units that have no lessons yet, so
    re-running an interrupted job is cheap and never re-spends LLM budget
    on weeks that already generated. ``rebuild_existing`` opts a run into
    regenerating units that already have lessons.
    """

    __tablename__ = "content_generation_jobs"

    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curricula.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[ContentGenerationState] = mapped_column(
        Enum(
            ContentGenerationState,
            name="content_generation_state",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=ContentGenerationState.PENDING,
        index=True,
    )

    correlation_id: Mapped[str] = mapped_column(
        String(36), nullable=False, default=lambda: str(uuid.uuid4())
    )

    total_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    completed_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    lessons_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    skipped_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Weeks that had planned topics but produced no lessons, usually a
    # provider-wide failure such as an exhausted LLM balance. These are
    # deliberately kept out of ``completed_weeks`` so the job cannot report
    # success for a curriculum that is only partly written.
    #
    # ``server_default`` mirrors the migration so the declared schema matches
    # the database and Alembic does not report drift.
    failed_weeks: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    rebuild_existing: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            ContentGenerationState.COMPLETED,
            ContentGenerationState.FAILED,
            ContentGenerationState.CANCELLED,
        }

    @property
    def is_partial(self) -> bool:
        """True when some weeks succeeded and others produced nothing."""
        return self.failed_weeks > 0 and self.lessons_generated > 0

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<ContentGenerationJob id={self.id} "
            f"curriculum_id={self.curriculum_id} status={self.status} "
            f"completed_weeks={self.completed_weeks}/{self.total_weeks}>"
        )
