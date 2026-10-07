"""Page model: one extracted page of a document."""

from __future__ import annotations

import uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class Page(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A single extracted page belonging to a document.

    ``raw_text`` preserves exactly what the extractor produced.
    ``normalized_text`` holds the cleaned version (whitespace normalized,
    repeated headers/footers stripped) used by downstream processing.
    Both are retained so normalization can be re-run without re-extracting
    from the source file.
    """

    __tablename__ = "pages"
    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_pages_document_page"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    page_number: Mapped[int] = mapped_column(Integer, nullable=False)

    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)

    char_count: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<Page id={self.id} document_id={self.document_id} "
            f"page_number={self.page_number}>"
        )
