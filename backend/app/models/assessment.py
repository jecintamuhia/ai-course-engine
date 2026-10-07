"""Assessment model: larger learning assessments that map to objectives."""

from __future__ import annotations

import enum
import uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import ARRAY, Enum, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


class AssessmentType(str, enum.Enum):
    """The kinds of larger assessment the pipeline can generate."""

    WEEKLY_QUIZ = "weekly_quiz"
    PRACTICAL_ASSIGNMENT = "practical_assignment"
    CODING_TASK = "coding_task"
    CASE_STUDY = "case_study"
    MINI_PROJECT = "mini_project"
    FINAL = "final"


class AssessmentStatus(str, enum.Enum):
    """Lifecycle of a generated assessment."""

    DRAFT = "draft"
    GENERATING = "generating"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class Assessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A larger assessment generated from a weekly unit's learning
    objectives (or from course-level objectives for a final assessment).

    ``items`` is a JSONB list of assessment items whose shape is
    validated by ``app.schemas.assessment``. ``alignment`` records the
    explicit learning-objective → lesson → evidence (activity /
    knowledge check) mapping so QA can prove the course teaches what it
    assesses. ``source_chunk_markers`` carries the textbook provenance
    of individual items (UUID strings of cited Chunks).
    """

    __tablename__ = "assessments"

    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curricula.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    curriculum_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_units.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    week_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    assessment_type: Mapped[AssessmentType] = mapped_column(
        Enum(
            AssessmentType,
            name="assessment_type",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    learning_objectives: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
        server_default=text("'{}'::varchar[]"),
    )

    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)

    items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    alignment: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    status: Mapped[AssessmentStatus] = mapped_column(
        Enum(
            AssessmentStatus,
            name="assessment_status",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=AssessmentStatus.DRAFT,
        index=True,
    )

    generation_errors: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    source_chunk_markers: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
        server_default=text("'{}'::varchar[]"),
    )

    reviewer_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    review_comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<Assessment id={self.id} type={self.assessment_type.value} "
            f"status={self.status.value}>"
        )
