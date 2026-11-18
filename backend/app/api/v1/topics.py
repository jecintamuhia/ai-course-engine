"""Topic analysis, provenance, and dependency graph endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.core.dependencies import get_database_session, get_llm_provider
from app.core.exceptions import TopicNotFound
from app.db.repositories.chunks import ChunkRepository
from app.db.repositories.dependencies import DependencyRepository
from app.db.repositories.documents import DocumentRepository
from app.db.repositories.structure import StructureRepository
from app.db.repositories.topics import TopicRepository
from app.schemas.dependency import (
    DependencyGraphResponse,
    RejectedCycleEdge,
    UnresolvedPrerequisiteRead,
)
from app.schemas.topic import (
    AnalysisWarningRead,
    CanonicalizationResponse,
    CanonicalTopicRead,
    DuplicateTopicRead,
    ProvenanceChunkRead,
    TopicAnalysisResponse,
    TopicProvenanceResponse,
    TopicRead,
)
from app.services.ai.base import LLMProvider
from app.services.content_analysis.service import ContentAnalysisService
from app.services.dependency.service import DependencyGraphService
from app.services.topics.canonicalization import apply_canonicalization
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/documents", tags=["topics"])

topic_router = APIRouter(prefix="/topics", tags=["topics"])


def get_content_analysis_service(
    session: AsyncSession = Depends(get_database_session),
    llm_provider: LLMProvider = Depends(get_llm_provider),
) -> ContentAnalysisService:
    """Construct a request-scoped content analysis service."""
    return ContentAnalysisService(
        DocumentRepository(session),
        StructureRepository(session),
        TopicRepository(session),
        ChunkRepository(session),
        llm_provider,
    )


def get_dependency_graph_service(
    session: AsyncSession = Depends(get_database_session),
) -> DependencyGraphService:
    """Construct a request-scoped dependency graph service."""
    return DependencyGraphService(
        DocumentRepository(session),
        TopicRepository(session),
        DependencyRepository(session),
    )


@router.post("/{document_id}/analyze", response_model=TopicAnalysisResponse)
async def analyze_document(
    document_id: uuid.UUID,
    service: ContentAnalysisService = Depends(get_content_analysis_service),
) -> TopicAnalysisResponse:
    """
    Run AI-assisted topic/concept extraction for a document.

    Requires pages to already be extracted, structured, and chunked.
    Runs synchronously for now. Re-running this replaces each chapter's
    previously extracted topics rather than duplicating them.
    """
    topics, warnings = await service.analyze_document_with_report(document_id)

    return TopicAnalysisResponse(
        document_id=document_id,
        topic_count=len(topics),
        topics=[TopicRead.model_validate(topic) for topic in topics],
        warnings=[AnalysisWarningRead.model_validate(w) for w in warnings],
    )


@router.get("/{document_id}/topics", response_model=list[TopicRead])
async def list_document_topics(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_database_session),
) -> list[TopicRead]:
    """List previously extracted top-level topics for a document."""
    topic_repository = TopicRepository(session)
    topics = await topic_repository.list_by_document(document_id)

    return [TopicRead.model_validate(topic) for topic in topics]


@router.post("/{document_id}/dependencies", response_model=DependencyGraphResponse)
async def build_document_dependencies(
    document_id: uuid.UUID,
    service: DependencyGraphService = Depends(get_dependency_graph_service),
) -> DependencyGraphResponse:
    """
    Resolve and persist the dependency graph for a document's topics.

    Requires topics to already be extracted via
    POST /{document_id}/analyze. Cycle-causing edges are rejected (not
    persisted) and reported in the response, not silently dropped;
    likewise for prerequisite titles that could not be resolved to
    exactly one topic. Idempotent: replaces any previously persisted
    dependency edges for this document.
    """
    result = await service.build_document_dependencies(document_id)

    return DependencyGraphResponse(
        document_id=document_id,
        topological_order=result.topological_order,
        rejected_cycle_edges=[
            RejectedCycleEdge(topic_id=a, depends_on_topic_id=b)
            for a, b in result.rejected_cycle_edges
        ],
        unresolved_prerequisites=[
            UnresolvedPrerequisiteRead(
                topic_id=u.topic_id,
                topic_title=u.topic_title,
                prerequisite_title=u.prerequisite_title,
                reason=u.reason,
            )
            for u in result.unresolved_prerequisites
        ],
    )


@topic_router.get("/{topic_id}/provenance", response_model=TopicProvenanceResponse)
async def get_topic_provenance(
    topic_id: uuid.UUID,
    session: AsyncSession = Depends(get_database_session),
) -> TopicProvenanceResponse:
    """
    Fetch a topic's provenance chain: the exact chunks (and their
    pages) the AI cited as supporting evidence for it.
    """
    topic_repository = TopicRepository(session)
    topic = await topic_repository.get_by_id(topic_id)

    if topic is None:
        raise TopicNotFound(f"Topic {topic_id} was not found.")

    provenance = await topic_repository.get_provenance_chain(topic_id)

    return TopicProvenanceResponse(
        topic_id=topic.id,
        topic_title=topic.title,
        source_type=topic.source_type,
        source_chunks=[
            ProvenanceChunkRead(
                chunk_id=chunk.id,
                chunk_content=chunk.content,
                page_id=page.id,
                page_number=page.page_number,
            )
            for chunk, page in provenance
        ],
    )


@router.post("/{document_id}/canonicalize", response_model=CanonicalizationResponse)
async def canonicalize_document_topics(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_database_session),
) -> CanonicalizationResponse:
    """
    Canonicalize a document's topics: compute canonical keys, classify
    importance, and merge safe exact-normalized-title duplicates into a
    canonical topic with aliases. Nothing is deleted and genuinely
    different concepts are never merged; near-duplicate candidates are
    reported for lecturer review (QA surfaces them as findings, too).
    """
    topic_repository = TopicRepository(session)
    topics = await topic_repository.list_flat_by_document(document_id)
    result = apply_canonicalization(topics)
    await topic_repository.commit()

    canonical = [
        CanonicalTopicRead(
            id=topic.id,
            chapter_id=topic.chapter_id,
            title=topic.title,
            canonical_key=topic.canonical_key or "",
            aliases=list(topic.aliases or []),
            importance=topic.importance,
            order_index=topic.order_index,
            parent_topic_id=topic.parent_topic_id,
        )
        for topic in topics
        if topic.duplicate_of_id is None
    ]
    duplicates = [
        DuplicateTopicRead(
            id=topic.id,
            title=topic.title,
            duplicate_of_id=topic.duplicate_of_id,
        )
        for topic in topics
        if topic.duplicate_of_id is not None
    ]

    return CanonicalizationResponse(
        document_id=document_id,
        topics_seen=result.topics_seen,
        clusters=result.clusters,
        duplicates_flagged=result.duplicates_flagged,
        aliases_created=result.aliases_created,
        canonical=canonical,
        duplicates=duplicates,
        near_duplicates=[
            {"left": left, "right": right, "similarity": similarity}
            for left, right, similarity in result.near_duplicates
        ],
        canonicalized_at=datetime.now(UTC),
    )
