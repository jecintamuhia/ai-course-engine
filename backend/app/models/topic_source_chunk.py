"""TopicSourceChunk: association between a Topic and its citing Chunks."""

from __future__ import annotations

import uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class TopicSourceChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Links a Topic to a Chunk the AI cited as supporting evidence for it.

    This is the concrete provenance edge: Topic -> Chunk -> Page ->
    Document is fully traceable by following topic_id here to chunk_id,
    then chunk.page_id, then page.document_id.
    """

    __tablename__ = "topic_source_chunks"
    __table_args__ = (
        UniqueConstraint(
            "topic_id", "chunk_id", name="uq_topic_source_chunks_topic_chunk"
        ),
    )

    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<TopicSourceChunk topic_id={self.topic_id} "
            f"chunk_id={self.chunk_id}>"
        ) 