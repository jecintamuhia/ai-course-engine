"""Pydantic schemas for dependency graph resources."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class RejectedCycleEdge(BaseModel):
    """A dependency edge removed because it would have closed a cycle."""

    topic_id: uuid.UUID
    depends_on_topic_id: uuid.UUID


class UnresolvedPrerequisiteRead(BaseModel):
    """A prerequisite title that could not be resolved to exactly one topic."""

    topic_id: uuid.UUID
    topic_title: str
    prerequisite_title: str
    reason: str


class DependencyGraphResponse(BaseModel):
    """Result of building a document's topic dependency graph."""

    document_id: uuid.UUID
    topological_order: list[uuid.UUID]
    rejected_cycle_edges: list[RejectedCycleEdge]
    unresolved_prerequisites: list[UnresolvedPrerequisiteRead]
