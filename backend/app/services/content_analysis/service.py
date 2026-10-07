"""Content analysis service: orchestrates AI-assisted topic extraction."""

from __future__ import annotations

import uuid

from app.core.config import get_settings
from app.core.exceptions import DocumentNotFound
from app.core.logging import get_logger
from app.db.repositories.chunks import ChunkRepository
from app.db.repositories.documents import DocumentRepository
from app.db.repositories.structure import StructureRepository
from app.db.repositories.topics import TopicRepository
from app.models.chunks import Chunk
from app.models.concept import Concept
from app.models.topic import Topic
from app.models.topic_source_chunk import TopicSourceChunk
from app.schemas.ai_extraction import ExtractedTopic
from app.services.ai.base import LLMProvider
from app.services.content_analysis.chunk_context import (
    build_marker_annotated_context,
    resolve_markers,
)
from app.services.content_analysis.topic_extractor import (
    extract_topics_for_chapter,
)

logger = get_logger(__name__)


def _build_topic_tree_with_provenance(
    extracted_topics: list[ExtractedTopic],
    *,
    document_id: uuid.UUID,
    chapter_id: uuid.UUID | None,
    marker_map: dict[str, uuid.UUID],
) -> tuple[list[Topic], list[TopicSourceChunk]]:
    """
    Convert a recursive list of ExtractedTopic into flat Topic ORM
    instances (with correct parent_topic_id linkage and ordering,
    verified in Batch 9) plus TopicSourceChunk association rows built
    from each topic's cited markers, resolved against marker_map.

    A cited marker not present in marker_map (hallucinated) is dropped
    and logged — never persisted as a fake reference.
    """
    all_source_links: list[TopicSourceChunk] = []

    def build_level(extracted_list: list[ExtractedTopic]) -> list[Topic]:
        rows: list[Topic] = []

        for index, extracted in enumerate(extracted_list):
            topic = Topic(
                document_id=document_id,
                chapter_id=chapter_id,
                title=extracted.title,
                learning_objectives=list(extracted.learning_objectives),
                prerequisite_titles=list(extracted.prerequisites),
                difficulty=extracted.difficulty,
                estimated_workload_minutes=extracted.estimated_workload_minutes,
                order_index=index,
                concepts=[
                    Concept(
                        name=concept.name,
                        description=concept.description,
                        definition=getattr(concept, "definition", None),
                        terminology=getattr(concept, "terminology", []) or [],
                        procedures=getattr(concept, "procedures", []) or [],
                        formulas=getattr(concept, "formulas", []) or [],
                        worked_examples=getattr(concept, "worked_examples", []) or [],
                        exercises=getattr(concept, "exercises", []) or [],
                        misconceptions=getattr(concept, "misconceptions", []) or [],
                        provenance=getattr(concept, "provenance", []) or [],
                        order_index=concept_index,
                    )
                    for concept_index, concept in enumerate(extracted.concepts)
                ],
                subtopics=build_level(extracted.subtopics),
            )
            # Assign the primary key eagerly: the column default is only
            # applied at flush time, and the TopicSourceChunk rows below
            # need topic.id before any flush so they persist a real FK.
            topic.id = uuid.uuid4()
            rows.append(topic)

            resolved_chunk_ids, dropped_markers = resolve_markers(
                extracted.source_chunk_markers, marker_map
            )

            if dropped_markers:
                logger.warning(
                    "Dropped hallucinated chunk markers for topic title=%r markers=%s",
                    extracted.title,
                    dropped_markers,
                )

            for chunk_id in resolved_chunk_ids:
                all_source_links.append(
                    TopicSourceChunk(topic_id=topic.id, chunk_id=chunk_id)
                )

        return rows

    topics = build_level(extracted_topics)
    return topics, all_source_links


class ContentAnalysisService:
    """Coordinates AI-assisted topic/concept extraction for a document."""

    def __init__(
        self,
        document_repository: DocumentRepository,
        structure_repository: StructureRepository,
        topic_repository: TopicRepository,
        chunk_repository: ChunkRepository,
        llm_provider: LLMProvider,
    ) -> None:
        self._document_repository = document_repository
        self._structure_repository = structure_repository
        self._topic_repository = topic_repository
        self._chunk_repository = chunk_repository
        self._llm_provider = llm_provider

    async def analyze_document(self, document_id: uuid.UUID) -> list[Topic]:
        """
        Run AI-assisted topic extraction for every chapter of a
        document (or the whole document as one implicit chapter, if no
        structure was detected), and persist the results with real
        provenance links to the chunks that supported each topic.

        Idempotent and non-destructive: a chapter (or the un-chaptered
        document) that already has persisted topics is skipped rather
        than re-analyzed, so a job retry does not recompute successful
        AI work. Re-running only issues LLM calls for chapters with no
        topics yet.
        """
        document = await self._document_repository.get_by_id(document_id)

        if document is None:
            raise DocumentNotFound(f"Document {document_id} was not found.")

        all_chunks = await self._chunk_repository.list_by_document(document_id)

        if not all_chunks:
            raise DocumentNotFound(
                f"Document {document_id} has no chunks. Run extraction "
                f"and chunking before analysis."
            )

        chapters = await self._structure_repository.list_chapters_by_document(
            document_id
        )

        # Close the request's read transaction before any LLM call so a
        # DB connection is not held open while awaiting the provider.
        await self._chunk_repository.commit()

        all_persisted_topics: list[Topic] = []

        if not chapters:
            existing = await self._topic_repository.list_unassociated_by_document(
                document_id
            )

            if existing:
                logger.info(
                    "Skipping already-analyzed document document_id=%s "
                    "topics=%s (no chapter structure)",
                    document_id,
                    len(existing),
                )
                all_persisted_topics.extend(existing)
            else:
                chapter_chunks = [c for c in all_chunks if c.chapter_id is None]
                topics = await self._analyze_and_persist(
                    document_id=document_id,
                    chapter_id=None,
                    chapter_title=document.original_filename,
                    chunks=chapter_chunks,
                )
                all_persisted_topics.extend(topics)
        else:
            for chapter in chapters:
                chapter_chunks = [c for c in all_chunks if c.chapter_id == chapter.id]

                if not chapter_chunks:
                    logger.warning(
                        "Cleaning up stale topics for empty chapter "
                        "chapter_id=%s document_id=%s",
                        chapter.id,
                        document_id,
                    )
                    await self._topic_repository.delete_by_chapter(chapter.id)
                    await self._topic_repository.commit()
                    continue

                existing = await self._topic_repository.list_by_chapter(chapter.id)

                if existing:
                    logger.info(
                        "Skipping already-analyzed chapter chapter_id=%s "
                        "document_id=%s topics=%s",
                        chapter.id,
                        document_id,
                        len(existing),
                    )
                    all_persisted_topics.extend(existing)
                    continue

                topics = await self._analyze_and_persist(
                    document_id=document_id,
                    chapter_id=chapter.id,
                    chapter_title=chapter.title,
                    chunks=chapter_chunks,
                )
                all_persisted_topics.extend(topics)

        return all_persisted_topics

    async def _analyze_and_persist(
        self,
        *,
        document_id: uuid.UUID,
        chapter_id: uuid.UUID | None,
        chapter_title: str,
        chunks: list[Chunk],
    ) -> list[Topic]:
        settings = get_settings()
        annotated_text, marker_map = build_marker_annotated_context(
            chunks,
            max_chars=settings.ai_max_context_chars,
        )

        if len(annotated_text.strip()) < settings.ai_min_content_chars:
            logger.warning(
                "Skipping chapter with insignificant content "
                "chapter_id=%s document_id=%s chars=%s min=%s",
                chapter_id,
                document_id,
                len(annotated_text),
                settings.ai_min_content_chars,
            )
            return []

        omitted_chunks = len(chunks) - len(marker_map)
        if omitted_chunks:
            logger.warning(
                "Bounded chapter context for LLM request chapter_id=%s "
                "document_id=%s dropped_chunks=%s of %s "
                "max_chars=%s",
                chapter_id,
                document_id,
                omitted_chunks,
                len(chunks),
                settings.ai_max_context_chars,
            )

        result = await extract_topics_for_chapter(
            self._llm_provider,
            chapter_title=chapter_title,
            chapter_text=annotated_text,
        )

        topic_rows, source_links = _build_topic_tree_with_provenance(
            result.topics,
            document_id=document_id,
            chapter_id=chapter_id,
            marker_map=marker_map,
        )

        if chapter_id is not None:
            await self._topic_repository.delete_by_chapter(chapter_id)
        else:
            await self._topic_repository.delete_by_document(document_id)

        await self._topic_repository.add_many(topic_rows)
        await self._topic_repository.add_source_links(source_links)
        await self._topic_repository.commit()

        return topic_rows
