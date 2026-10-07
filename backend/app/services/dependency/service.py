"""Dependency graph service: orchestrates prerequisite resolution and persistence."""

from __future__ import annotations

import uuid

from app.core.exceptions import DocumentNotFound
from app.core.logging import get_logger
from app.db.repositories.dependencies import DependencyRepository
from app.db.repositories.documents import DocumentRepository
from app.db.repositories.topics import TopicRepository
from app.models.dependency import Dependency
from app.services.dependency.graph import Edges, break_all_cycles, topological_sort
from app.services.dependency.resolver import (
    UnresolvedPrerequisite,
    resolve_prerequisites,
)

logger = get_logger(__name__)


class DependencyGraphResult:
    """Result of building a document's dependency graph."""

    def __init__(
        self,
        *,
        topological_order: list[uuid.UUID],
        rejected_cycle_edges: list[tuple[uuid.UUID, uuid.UUID]],
        unresolved_prerequisites: list[UnresolvedPrerequisite],
    ) -> None:
        self.topological_order = topological_order
        self.rejected_cycle_edges = rejected_cycle_edges
        self.unresolved_prerequisites = unresolved_prerequisites


class DependencyGraphService:
    """Builds and persists a document's topic dependency graph."""

    def __init__(
        self,
        document_repository: DocumentRepository,
        topic_repository: TopicRepository,
        dependency_repository: DependencyRepository,
    ) -> None:
        self._document_repository = document_repository
        self._topic_repository = topic_repository
        self._dependency_repository = dependency_repository

    async def build_document_dependencies(
        self,
        document_id: uuid.UUID,
        *,
        additional_edges: Edges | None = None,
    ) -> DependencyGraphResult:
        """
        Resolve, validate, and persist the dependency graph for a
        document's topics.

        Two independent sources feed the graph. Each topic's own
        ``prerequisite_titles`` (the within-chapter links named during
        extraction) are resolved by title. ``additional_edges`` carries
        the cross-chapter links from the document-wide linking pass, which
        can only run once every title exists. Both are merged here so
        cycle detection and topological ordering see the whole graph.

        Idempotent: re-running this replaces the document's previously
        persisted dependency edges. Cycle-causing edges are detected,
        removed, and reported (never persisted) rather than blocking
        the whole document over one bad AI-inferred prerequisite loop.
        """
        document = await self._document_repository.get_by_id(document_id)

        if document is None:
            raise DocumentNotFound(f"Document {document_id} was not found.")

        top_level_topics = await self._topic_repository.list_by_document(document_id)

        edges, unresolved = resolve_prerequisites(top_level_topics)

        if additional_edges:
            for topic_id, depends_on_ids in additional_edges.items():
                if not depends_on_ids:
                    continue
                target = edges.setdefault(topic_id, set())
                target.update(depends_on_ids)

        if unresolved:
            logger.warning(
                "Unresolved prerequisites for document_id=%s count=%s",
                document_id,
                len(unresolved),
            )

        acyclic_edges, rejected_edges = break_all_cycles(edges)

        if rejected_edges:
            logger.warning(
                "Rejected cycle-causing dependency edges for document_id=%s count=%s",
                document_id,
                len(rejected_edges),
            )

        order = topological_sort(acyclic_edges)

        dependency_rows = [
            Dependency(topic_id=topic_id, depends_on_topic_id=depends_on_id)
            for topic_id, depends_on_ids in acyclic_edges.items()
            for depends_on_id in depends_on_ids
        ]

        await self._dependency_repository.delete_by_document(document_id)
        await self._dependency_repository.add_many(dependency_rows)
        await self._dependency_repository.commit()

        return DependencyGraphResult(
            topological_order=order,
            rejected_cycle_edges=rejected_edges,
            unresolved_prerequisites=unresolved,
        )
