"""Integration tests for AI-assisted topic analysis feeding curriculum planning."""

from __future__ import annotations

import uuid
from datetime import date

from app.models.chunks import Chunk
from app.models.curriculum import Curriculum, CurriculumStatus
from app.models.dependency import Dependency
from app.models.document import Document, DocumentStatus
from app.models.topic import Topic
from app.schemas.ai_extraction import (
    ExtractedConcept,
    ExtractedTopic,
    TopicExtractionResult,
)
from app.services.ai.base import LLMProvider
from app.services.content_analysis.service import ContentAnalysisService
from app.services.curriculum.service import CurriculumService


def _document(document_id: uuid.UUID) -> Document:
    return Document(
        id=document_id,
        original_filename="networking_textbook.pdf",
        storage_filename="networking_textbook.pdf",
        storage_path="/tmp/networking_textbook.pdf",
        mime_type="application/pdf",
        file_extension=".pdf",
        size_bytes=9000,
        sha256_hash="b" * 64,
        status=DocumentStatus.UPLOADED,
    )


def _chunks(document_id: uuid.UUID) -> list[Chunk]:
    contents = [
        "DNS resolution maps friendly names to numeric addresses. " * 8,
        "Mail routing uses MX records to deliver messages between hosts. " * 8,
    ]
    return [
        Chunk(
            id=uuid.uuid4(),
            document_id=document_id,
            page_id=uuid.uuid4(),
            document_index=index,
            page_index=0,
            content=content,
            char_count=len(content),
            content_hash=f"hash-{index}",
        )
        for index, content in enumerate(contents)
    ]


def _scripted_result() -> TopicExtractionResult:
    concept = ExtractedConcept(
        name="Recursive resolver", description="A resolver that queries other servers."
    )
    return TopicExtractionResult(
        topics=[
            ExtractedTopic(
                title="DNS resolution",
                learning_objectives=["Trace a DNS lookup"],
                concepts=[concept],
                difficulty=1,
                estimated_workload_minutes=90,
                source_chunk_markers=["C1"],
                subtopics=[
                    ExtractedTopic(
                        title="Record types",
                        learning_objectives=["Name common DNS records"],
                        concepts=[concept],
                        difficulty=2,
                        estimated_workload_minutes=30,
                        source_chunk_markers=["C2"],
                    )
                ],
            ),
            ExtractedTopic(
                title="Mail routing",
                learning_objectives=["Explain an MX lookup"],
                prerequisites=["DNS resolution"],
                concepts=[concept],
                difficulty=2,
                estimated_workload_minutes=120,
                source_chunk_markers=["C2"],
            ),
        ]
    )


class _ScriptedLLM(LLMProvider):
    """Deterministic provider: records the prompt and returns a fixed result."""

    def __init__(self, result: TopicExtractionResult) -> None:
        self.result = result
        self.calls: list[dict] = []

    async def complete_structured(
        self,
        *,
        system_prompt,
        user_prompt,
        response_model,
        temperature=0.0,
        max_output_tokens=None,
    ):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "response_model": response_model,
            }
        )
        return self.result

    async def complete_text(self, **kwargs) -> str:
        raise AssertionError("topic analysis must use structured output")


class _DocumentRepository:
    def __init__(self, document: Document) -> None:
        self.document = document

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        return self.document


class _ChunkRepository:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self.commits = 0

    async def list_by_document(self, document_id: uuid.UUID) -> list[Chunk]:
        return self.chunks

    async def commit(self) -> None:
        self.commits += 1


class _StructureRepository:
    async def list_chapters_by_document(self, document_id: uuid.UUID) -> list:
        return []


class _TopicRepository:
    def __init__(self) -> None:
        self.topics: list[Topic] = []
        self.source_links: list = []
        self.commits = 0

    async def list_unassociated_by_document(
        self, document_id: uuid.UUID
    ) -> list[Topic]:
        return [
            topic
            for topic in self.topics
            if topic.parent_topic_id is None
            and topic.chapter_id is None
            and topic.duplicate_of_id is None
        ]

    async def delete_by_document(self, document_id: uuid.UUID) -> None:
        self.topics = []
        self.source_links = []

    async def add_many(self, topics: list[Topic]) -> None:
        def link_children(parent: Topic) -> None:
            for child in parent.subtopics:
                child.parent_topic_id = parent.id
                link_children(child)

        for topic in topics:
            link_children(topic)
        self.topics.extend(topics)

    async def add_source_links(self, links: list) -> None:
        self.source_links.extend(links)

    async def list_flat_by_document(
        self, document_id: uuid.UUID, *, exclude_duplicates: bool = False
    ) -> list[Topic]:
        def flatten(topics: list[Topic]) -> list[Topic]:
            result: list[Topic] = []
            for topic in topics:
                if exclude_duplicates and topic.duplicate_of_id is not None:
                    continue
                result.append(topic)
                result.extend(flatten(topic.subtopics))
            return result

        return flatten(self.topics)

    async def commit(self) -> None:
        self.commits += 1


class _DependencyRepository:
    def __init__(self, dependencies: list[Dependency]) -> None:
        self.dependencies = dependencies
        self.requests: list[uuid.UUID] = []

    async def list_by_document(self, document_id: uuid.UUID) -> list[Dependency]:
        self.requests.append(document_id)
        return self.dependencies


class _CurriculumRepository:
    def __init__(self) -> None:
        self.curricula: list[Curriculum] = []
        self.latest: list[Curriculum] = []
        self.superseded: list[Curriculum] = []
        self.commits = 0

    async def latest_version_number(self, document_id: uuid.UUID) -> int:
        return len(
            [
                curriculum
                for curriculum in self.curricula
                if curriculum.document_id == document_id
            ]
        )

    async def list_latest_by_document(self, document_id: uuid.UUID) -> list[Curriculum]:
        return list(self.latest)

    async def mark_superseded(self, curriculum: Curriculum) -> None:
        self.superseded.append(curriculum)

    async def add(self, curriculum: Curriculum) -> None:
        curriculum.id = uuid.uuid4()
        for unit in curriculum.units:
            unit.id = uuid.uuid4()
            for link in unit.topic_links:
                link.id = uuid.uuid4()
                if link.topic is not None:
                    link.topic_id = link.topic.id
        self.curricula.append(curriculum)

    async def commit(self) -> None:
        self.commits += 1


async def test_scripted_llm_topics_are_planned_into_a_curriculum() -> None:
    """Analysis, provenance, canonicalization and planning run as one flow."""
    document_id = uuid.uuid4()
    document = _document(document_id)
    chunks = _chunks(document_id)
    llm = _ScriptedLLM(_scripted_result())
    topics = _TopicRepository()
    dependencies = _DependencyRepository([])
    curricula = _CurriculumRepository()

    analysis = ContentAnalysisService(
        _DocumentRepository(document),
        _StructureRepository(),
        topics,
        _ChunkRepository(chunks),
        llm,
    )
    persisted = await analysis.analyze_document(document_id)
    await analysis.analyze_document(document_id)

    assert len(persisted) == 2
    assert len(llm.calls) == 1  # retry skips already-analyzed chapters
    assert "C1" in llm.calls[0]["user_prompt"]
    assert "networking_textbook.pdf" in llm.calls[0]["user_prompt"]
    assert llm.calls[0]["response_model"] is TopicExtractionResult
    assert {link.chunk_id for link in topics.source_links} == {
        chunk.id for chunk in chunks
    }

    by_title = {topic.title: topic for topic in persisted}
    dependencies.dependencies = [
        Dependency(
            id=uuid.uuid4(),
            topic_id=by_title["Mail routing"].id,
            depends_on_topic_id=by_title["DNS resolution"].id,
        )
    ]
    service = CurriculumService(
        _DocumentRepository(document), topics, dependencies, curricula
    )

    curriculum = await service.generate_curriculum(
        document_id,
        title="Networking Foundations",
        start_date=date(2026, 1, 5),
    )

    assert dependencies.requests == [document_id]
    assert all(topic.canonical_key for topic in persisted)
    assert curriculum.status is CurriculumStatus.DRAFT
    assert curriculum.title == "Networking Foundations"
    assert curriculum.start_date == date(2026, 1, 5)
    assert curriculum.version_number == 1
    assert [unit.week_number for unit in curriculum.units] == list(range(1, 17))
    assert all(
        unit.estimated_workload_minutes <= curriculum.max_weekly_workload_minutes
        for unit in curriculum.units
    )
    scheduled = [
        link.topic_id for unit in curriculum.units for link in unit.topic_links
    ]
    assert set(scheduled) == {
        by_title["DNS resolution"].id,
        by_title["Mail routing"].id,
    }
    assert scheduled.index(by_title["DNS resolution"].id) < scheduled.index(
        by_title["Mail routing"].id
    )
    assert curricula.curricula == [curriculum]
    assert curricula.commits == 1


async def test_regeneration_supersedes_the_previous_curriculum_version() -> None:
    """A new generation is a new version, not a mutation of the old draft."""
    document_id = uuid.uuid4()
    topics = _TopicRepository()
    topics.topics = [
        Topic(
            id=uuid.uuid4(),
            document_id=document_id,
            title=title,
            learning_objectives=[f"Learn {title}"],
            difficulty=2,
            estimated_workload_minutes=minutes,
            order_index=index,
        )
        for index, (title, minutes) in enumerate(
            [("DNS resolution", 120), ("Mail routing", 90)]
        )
    ]
    previous = Curriculum(
        id=uuid.uuid4(),
        document_id=document_id,
        title="Old draft",
        total_weeks=16,
        learning_days_per_week=5,
        hours_per_day=4,
        max_weekly_workload_minutes=1200,
        min_topic_allocation_minutes=60,
        max_topic_allocation_minutes=1200,
        version_number=1,
    )
    curricula = _CurriculumRepository()
    curricula.curricula = [previous]
    curricula.latest = [previous]
    service = CurriculumService(
        _DocumentRepository(_document(document_id)),
        topics,
        _DependencyRepository([]),
        curricula,
    )

    generated = await service.generate_curriculum(document_id)

    assert generated.version_number == 2
    assert curricula.superseded == [previous]
    assert curricula.curricula == [previous, generated]
    assert generated.is_latest_version is True
