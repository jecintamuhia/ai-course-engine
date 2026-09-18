"""CurriculumUnitTopic model: association between a weekly unit and a planned topic."""

from __future__ import annotations

import uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class CurriculumUnitTopic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One topic assigned to one weekly curriculum unit, in planning order.

    ``topic_id`` references the top-level Topic row the planner decided
    to schedule; ``order_index`` records the order the topic should be
    taught within the week.
    """

    __tablename__ = "curriculum_unit_topics"
    __table_args__ = (
        UniqueConstraint(
            "curriculum_unit_id",
            "topic_id",
            name="uq_curriculum_unit_topics_unit_topic",
        ),
    )

    curriculum_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    topic: Mapped[Topic] = relationship("Topic")

    curriculum_unit: Mapped[CurriculumUnit] = relationship(
        "CurriculumUnit", back_populates="topic_links"
    )

    @property
    def title(self) -> str:
        """Alias to the linked Topic's title for ``from_attributes`` schemas."""
        return self.topic.title

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<CurriculumUnitTopic unit={self.curriculum_unit_id} "
            f"topic={self.topic_id}>"
        )