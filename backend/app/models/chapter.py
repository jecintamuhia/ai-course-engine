"""Chapter model: a detected top-level structural unit of a document."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Chapter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A detected chapter within a document, spanning a range of pages.

    ``number`` holds the detected label as text (e.g. "1", "IV") since
    numbering schemes vary; it is nullable because some detection paths
    (formatting-based fallback) do not yield a number at all.
    """

    __tablename__ = "chapters"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)

    start_page: Mapped[int] = mapped_column(Integer, nullable=False)
    end_page: Mapped[int] = mapped_column(Integer, nullable=False)

    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    sections: Mapped[list["Section"]] = relationship(
        "Section",
        cascade="all, delete-orphan",
        order_by="Section.order_index",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<Chapter id={self.id} number={self.number!r} "
            f"title={self.title!r} pages={self.start_page}-{self.end_page}>"
        )