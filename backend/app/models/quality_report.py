"""QualityReport model: persisted course content-QA inspection results."""

from __future__ import annotations

import uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


class QualityReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    An automated content-QA inspection of a curriculum.

    ``verdict`` is one of ``pass`` / ``warning`` / ``fail``. A ``fail``
    verdict means at least one severe finding exists and approval or
    publishing of the curriculum is blocked. ``areas`` holds the
    per-check-domain status (coverage, duplication, provenance, quality,
    learning_design, moodle) and ``findings`` the flattened finding list
    with rule codes, severities, messages, and locations. The lecturer
    can inspect every finding in the review UI.
    """

    __tablename__ = "quality_reports"

    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curricula.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    verdict: Mapped[str] = mapped_column(String(16), nullable=False)

    areas: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    findings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    @property
    def checked_at(self):
        """The inspection is timestamped by the created_at mixin."""
        return self.created_at

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<QualityReport id={self.id} curriculum_id={self.curriculum_id} "
            f"verdict={self.verdict}>"
        )
