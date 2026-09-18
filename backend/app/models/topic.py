"""Topic model: a topic or subtopic extracted from source content."""

from __future__ import annotations

import enum
import uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import ARRAY, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class SourceType(str, enum.Enum):
    """
    Classifies how an educational object relates to its source content.

    SOURCE_DERIVED content is drawn essentially verbatim from source
    material. AI_GENERATED content is synthesized/inferred by the AI
    from source material (grounded in it, but not a literal excerpt).
    AI_ENRICHED content is AI-transformed source content (e.g. a
    paraphrase or summary of an existing excerpt). Topics and Concepts
    are always AI_GENERATED — the other two values exist for content
    types not yet implemented in this pipeline.
    """

    SOURCE_DERIVED = "source_derived"
    AI_GENERATED = "ai_generated"
    AI_ENRICHED = "ai_enriched"


class Topic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A topic extracted from source content. Subtopics are Topic rows
    with parent_topic_id set — there is no separate Subtopic table.

    ``prerequisite_titles`` holds plain-text references to other
    topics' titles as extracted by the AI, NOT resolved foreign keys.
    A later batch (Dependency Graph) resolves these into real graph
    edges via the Dependency model, with cycle detection.

    ``source_chunks`` (via TopicSourceChunk) holds the actual Chunks the
    AI cited as supporting evidence for this topic — the concrete
    provenance edge back to source material.
    """

    __tablename__ = "topics"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    parent_topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)

    learning_objectives: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    prerequisite_titles: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )

    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_workload_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

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

    concepts: Mapped[list[Concept]] = relationship(
        "Concept",
        cascade="all, delete-orphan",
        order_by="Concept.order_index",
    )

    subtopics: Mapped[list[Topic]] = relationship(
        "Topic",
        cascade="all, delete-orphan",
        order_by="Topic.order_index",
        remote_side="Topic.parent_topic_id",
        overlaps="subtopics",
    )

    source_chunk_links: Mapped[list[TopicSourceChunk]] = relationship(
        "TopicSourceChunk",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<Topic id={self.id} title={self.title!r} "
            f"parent={self.parent_topic_id}>"
        )