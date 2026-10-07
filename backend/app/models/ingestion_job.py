"""IngestionJob model: tracks background document processing state."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class IngestionState(str, enum.Enum):
    """Full ingestion pipeline state machine."""

    PENDING = "pending"
    VALIDATING = "validating"
    EXTRACTING = "extracting"
    NORMALIZING = "normalizing"
    STRUCTURING = "structuring"
    CHUNKING = "chunking"
    ANALYZING = "analyzing"
    KNOWLEDGE_BUILDING = "knowledge_building"
    PLANNING = "planning"
    VALIDATING_OUTPUT = "validating_output"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IngestionJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A background job to process a document through the full ingestion
    pipeline.

    ``correlation_id`` is a stable identifier for tracing this job's
    processing across logs, independent of retries. ``attempt_count``
    increments each time the job restarts the pipeline from PENDING; the
    job is marked FAILED only once it reaches ``max_attempts``.
    """

    __tablename__ = "ingestion_jobs"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[IngestionState] = mapped_column(
        Enum(
            IngestionState,
            name="ingestion_state",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=IngestionState.PENDING,
        index=True,
    )

    correlation_id: Mapped[str] = mapped_column(
        String(36), nullable=False, default=lambda: str(uuid.uuid4())
    )

    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<IngestionJob id={self.id} document_id={self.document_id} "
            f"status={self.status} attempt={self.attempt_count}>"
        )
