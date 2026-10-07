"""Pydantic schemas for topic resources."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.models.topic import SourceType
from pydantic import BaseModel, ConfigDict


class ConceptRead(BaseModel):
    """Public representation of a concept."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    order_index: int
    source_type: SourceType


class TopicRead(BaseModel):
    """Public representation of a topic, with nested subtopics and concepts."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    chapter_id: uuid.UUID | None
    parent_topic_id: uuid.UUID | None
    title: str
    learning_objectives: list[str]
    prerequisite_titles: list[str]
    difficulty: int
    estimated_workload_minutes: int
    order_index: int
    source_type: SourceType
    concepts: list[ConceptRead] = []
    subtopics: list[TopicRead] = []
    created_at: datetime


class TopicAnalysisResponse(BaseModel):
    """Response returned after running document analysis."""

    document_id: uuid.UUID
    topic_count: int
    topics: list[TopicRead]


class ProvenanceChunkRead(BaseModel):
    """One chunk in a topic's provenance chain, with its page context."""

    chunk_id: uuid.UUID
    chunk_content: str
    page_id: uuid.UUID
    page_number: int


class TopicProvenanceResponse(BaseModel):
    """Full provenance chain for a topic: the chunks/pages that support it."""

    topic_id: uuid.UUID
    topic_title: str
    source_type: SourceType
    source_chunks: list[ProvenanceChunkRead]


class DuplicateTopicRead(BaseModel):
    """A topic merged into a canonical counterpart during canonicalization."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    duplicate_of_id: uuid.UUID


class CanonicalTopicRead(BaseModel):
    """
    A canonical (deduplicated) topic row after canonicalization.

    Deliberately relationship-free so it can be computed from the flat
    topic list without triggering ORM lazy loads.
    """

    id: uuid.UUID
    chapter_id: uuid.UUID | None = None
    title: str
    canonical_key: str
    aliases: list[str] = []
    importance: str | None = None
    order_index: int
    parent_topic_id: uuid.UUID | None = None


class CanonicalizationResponse(BaseModel):
    """Outcome of running topic canonicalization over a document."""

    document_id: uuid.UUID
    topics_seen: int
    clusters: int
    duplicates_flagged: int
    aliases_created: int
    canonical: list[CanonicalTopicRead]
    duplicates: list[DuplicateTopicRead]
    near_duplicates: list[dict]
    canonicalized_at: datetime
