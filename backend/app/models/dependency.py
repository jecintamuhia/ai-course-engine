"""Dependency model: a resolved prerequisite edge between two topics."""

from __future__ import annotations

import uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class Dependency(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A resolved prerequisite edge: topic_id depends on
    depends_on_topic_id (the latter must be learned first).

    Resolved from Topic.prerequisite_titles (plain text, from AI
    extraction) via app.services.dependency.resolver — this table only
    ever holds edges that were successfully matched and confirmed
    acyclic; ambiguous, not-found, or cycle-causing edges are never
    persisted here.
    """

    __tablename__ = "dependencies"
    __table_args__ = (
        UniqueConstraint(
            "topic_id",
            "depends_on_topic_id",
            name="uq_dependencies_topic_depends_on",
        ),
    )

    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    depends_on_topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<Dependency topic_id={self.topic_id} "
            f"depends_on={self.depends_on_topic_id}>"
        )
