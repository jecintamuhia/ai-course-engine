"""Unit tests for database-transaction separation around LLM calls."""

from __future__ import annotations

import uuid
from unittest.mock import Mock

from app.schemas.ai_extraction import (
    ExtractedConcept,
    ExtractedTopic,
    TopicExtractionResult,
)
from app.services.content_analysis.service import ContentAnalysisService


class _FakeChunk:
    def __init__(self, chunk_id: uuid.UUID) -> None:
        self.id = chunk_id
        self.chapter_id = None
        self.content = "Example chunk content. " * 60


class _RecordingDocRepository:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    async def get_by_id(self, document_id: uuid.UUID):
        self._calls.append("get_document")
        document = Mock()
        document.original_filename = "sample.pdf"
        return document


class _RecordingStructureRepository:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    async def list_chapters_by_document(self, document_id: uuid.UUID):
        self._calls.append("list_chapters")
        return []


class _RecordingTopicRepository:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    async def list_unassociated_by_document(self, document_id: uuid.UUID):
        self._calls.append("list_unassociated")
        return []

    async def list_by_chapter(self, chapter_id: uuid.UUID):
        self._calls.append("list_by_chapter")
        return []

    async def delete_by_document(self, document_id: uuid.UUID) -> None:
        self._calls.append("delete_topics")

    async def add_many(self, topics):
        self._calls.append("add_topics")
        return topics

    async def add_source_links(self, links):
        self._calls.append("add_links")
        return links

    async def commit(self) -> None:
        self._calls.append("commit")


class _RecordingChunkRepository:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    async def list_by_document(self, document_id: uuid.UUID):
        self._calls.append("list_chunks")
        return [_FakeChunk(chunk_id=uuid.uuid4())]

    async def commit(self) -> None:
        self._calls.append("commit")


class _RecordingLLM:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    async def complete_structured(self, **kwargs):
        self._calls.append("llm_call")
        return TopicExtractionResult(
            topics=[
                ExtractedTopic(
                    title="Sample Topic",
                    learning_objectives=["Students will be able to explain X."],
                    concepts=[ExtractedConcept(name="X", description="About X.")],
                    difficulty=2,
                    estimated_workload_minutes=30,
                )
            ]
        )

    async def complete_text(self, **kwargs) -> str:
        return ""


async def test_no_db_write_precedes_llm_call() -> None:
    calls: list[str] = []

    service = ContentAnalysisService(
        _RecordingDocRepository(calls),
        _RecordingStructureRepository(calls),
        _RecordingTopicRepository(calls),
        _RecordingChunkRepository(calls),
        _RecordingLLM(calls),
    )

    await service.analyze_document(uuid.uuid4())

    assert calls.index("llm_call") > calls.index("commit")
    assert calls.index("delete_topics") > calls.index("llm_call")
    assert calls.index("add_topics") > calls.index("llm_call")
