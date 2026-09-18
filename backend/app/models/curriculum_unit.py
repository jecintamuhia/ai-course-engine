"""CurriculumUnit model: one week of a generated curriculum plan."""

from __future__ import annotations

import uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import ARRAY, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class CurriculumUnit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A single weekly unit within a generated curriculum.

    One CurriculumUnit represents one week of the course. The topics
    covered in the unit are linked through CurriculumUnitTopic
    association rows (in planning order); ``learning_objectives``
    aggregates the learning objectives of those topics so the week has
    an explicit, source-grounded goal statement.
    """

    __tablename__ = "curriculum_units"

    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curricula.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    learning_objectives: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )

    estimated_workload_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    topic_links: Mapped[list[CurriculumUnitTopic]] = relationship(
        "CurriculumUnitTopic",
        cascade="all, delete-orphan",
        order_by="CurriculumUnitTopic.order_index",
        back_populates="curriculum_unit",
    )

    curriculum: Mapped[Curriculum] = relationship(
        "Curriculum", back_populates="units"
    )

    @property
    def topics(self) -> list[CurriculumUnitTopic]:
        """
        Alias for ``topic_links`` so the ``from_attributes`` response
        schema ``units[].topics`` maps to the planning-order topic links.
        """
        return self.topic_links

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<CurriculumUnit id={self.id} week={self.week_number} "
            f"title={self.title!r}>"
        )