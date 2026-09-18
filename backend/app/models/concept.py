"""Concept model: a discrete idea introduced within a topic."""

from __future__ import annotations

import uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.topic import SourceType
from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class Concept(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single concept identified within a topic."""

    __tablename__ = "concepts"

    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    source_type: Mapped[SourceType] = mapped_column(
        Enum(
            SourceType,
            name="source_type",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=SourceType.AI_GENERATED,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Concept id={self.id} name={self.name!r}>"