"""Detect and split oversized topics safely."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.concept import Concept
from app.models.topic import Topic
from app.models.topic_source_chunk import TopicSourceChunk
from sqlalchemy import func, select
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class SplitCandidate:
    topic_id: str
    reason: str
    score: float


class TopicSplitter:
    """Topic splitting service."""

    def __init__(self, max_concepts: int = 12, max_chunks: int = 8) -> None:
        self.max_concepts = max_concepts
        self.max_chunks = max_chunks

    def find_candidates(self, db: Session, document_id: str) -> list[SplitCandidate]:
        """Find topics that should be split."""
        stmt = (
            select(
                Topic.id,
                func.count(Concept.id).label("concept_count"),
                func.count(TopicSourceChunk.id).label("chunk_count"),
            )
            .outerjoin(Concept, Concept.topic_id == Topic.id)
            .outerjoin(
                TopicSourceChunk, TopicSourceChunk.topic_id == Topic.id
            )
            .where(Topic.document_id == document_id)
            .group_by(Topic.id)
            .having(
                (func.count(Concept.id) > self.max_concepts)
                | (func.count(TopicSourceChunk.id) > self.max_chunks)
            )
        )

        candidates: list[SplitCandidate] = []
        for row in db.execute(stmt).all():
            reasons = []
            if row.concept_count and row.concept_count > self.max_concepts:
                reasons.append(f"{row.concept_count} concepts")
            if row.chunk_count and row.chunk_count > self.max_chunks:
                reasons.append(f"{row.chunk_count} chunks")
            score = float((row.concept_count or 0) + (row.chunk_count or 0))
            candidates.append(
                SplitCandidate(
                    topic_id=str(row.id),
                    reason="; ".join(reasons) or "oversized",
                    score=score,
                )
            )
        return sorted(candidates, key=lambda c: c.score, reverse=True)

    def split_topic(self, db: Session, topic_id: str) -> dict[str, Any]:
        """Split a topic into multiple topics."""
        raise NotImplementedError(
            "Split logic requires careful graph rewiring; "
            "implement conservatively with tests"
        )
