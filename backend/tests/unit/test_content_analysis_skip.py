"""Unit tests for Phase 7: skip re-analysis of already-analyzed content."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import Mock

from app.models.topic import Topic
from app.schemas.ai_extraction import (
    ExtractedConcept,
    ExtractedTopic,
    TopicExtractionResult,
)
from app.services.content_analysis.service import ContentAnalysisService


class _FakeChunk:
    def __init__(
        self,
        chunk_id: uuid.UUID,
        chapter_id: uuid.UUID | None,
        content: str | None = None,
    ) -> None:
        self.id = chunk_id
        self.chapter_id = chapter_id
        self.content = content or ("Example chunk content. " * 60)


class _FakeChapter:
    """Mirrors the fields of the real Chapter model that the analysis
    service reads (including outline rendering)."""

    def __init__(
        self,
        chapter_id: uuid.UUID,
        title: str,
        order_index: int = 0,
        sections: list | None = None,
    ) -> None:
        self.id = chapter_id
        self.title = title
        self.number = None
        self.order_index = order_index
        self.sections = sections or []


def _existing_topic(title: str) -> Topic:
    return Topic(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        title=title,
        difficulty=2,
        estimated_workload_minutes=30,
        order_index=0,
    )


class _DocRepo:
    async def get_by_id(self, document_id: uuid.UUID):
        document = Mock()
        document.original_filename = "sample.pdf"
        return document


class _ChunkRepo:
    def __init__(self, chunks: list[_FakeChunk]) -> None:
        self._chunks = chunks

    async def list_by_document(self, document_id: uuid.UUID):
        return self._chunks

    async def commit(self) -> None:
        return None


class _StructureRepo:
    def __init__(self, chapters: list[_FakeChapter]) -> None:
        self._chapters = chapters

    async def list_chapters_by_document(self, document_id: uuid.UUID):
        return self._chapters


class _TopicRepo:
    def __init__(self, *, unassociated=None, by_chapter=None) -> None:
        self._unassociated = unassociated or []
        self._by_chapter = by_chapter or {}
        self.llm_called = False

    async def list_unassociated_by_document(self, document_id: uuid.UUID):
        return self._unassociated

    async def list_by_chapter(self, chapter_id: uuid.UUID):
        return self._by_chapter.get(chapter_id, [])

    async def delete_by_chapter(self, chapter_id: uuid.UUID) -> None:
        return None

    async def delete_by_document(self, document_id: uuid.UUID) -> None:
        return None

    async def add_many(self, topics):
        return topics

    async def add_source_links(self, links):
        return links

    async def commit(self) -> None:
        return None


class _LLM:
    def __init__(self) -> None:
        self.llm_called = False
        self.user_prompts: list[str] = []

    async def complete_structured(self, **kwargs):
        self.llm_called = True
        self.user_prompts.append(kwargs.get("user_prompt", ""))
        return TopicExtractionResult(
            topics=[
                ExtractedTopic(
                    title="Fresh Topic",
                    learning_objectives=["Students will be able to explain X."],
                    concepts=[ExtractedConcept(name="X", description="About X.")],
                    difficulty=2,
                    estimated_workload_minutes=30,
                )
            ]
        )

    async def complete_text(self, **kwargs) -> str:
        return ""


def _make_service(*, chapters, chunks, topics, llm):
    return ContentAnalysisService(
        _DocRepo(),
        _StructureRepo(chapters),
        topics,
        _ChunkRepo(chunks),
        llm,
    )


async def test_does_not_reanalyze_chapter_with_existing_topics() -> None:
    chapter = _FakeChapter(uuid.uuid4(), "Chapter 1")
    chunk = _FakeChunk(uuid.uuid4(), chapter.id)
    existing = _existing_topic("Existing Topic")
    llm = _LLM()

    service = _make_service(
        chapters=[chapter],
        chunks=[chunk],
        topics=_TopicRepo(by_chapter={chapter.id: [existing]}),
        llm=llm,
    )

    result = await service.analyze_document(uuid.uuid4())

    assert not llm.llm_called
    assert result == [existing]


async def test_does_not_reanalyze_whole_document_with_existing_topics() -> None:
    existing = _existing_topic("Existing Topic")
    llm = _LLM()

    service = _make_service(
        chapters=[],
        chunks=[_FakeChunk(uuid.uuid4(), None)],
        topics=_TopicRepo(unassociated=[existing]),
        llm=llm,
    )

    result = await service.analyze_document(uuid.uuid4())

    assert not llm.llm_called
    assert result == [existing]


async def test_analyzes_only_chapters_without_topics() -> None:
    chapter = _FakeChapter(uuid.uuid4(), "Chapter 1")
    chunk = _FakeChunk(uuid.uuid4(), chapter.id)
    llm = _LLM()

    service = _make_service(
        chapters=[chapter],
        chunks=[chunk],
        topics=_TopicRepo(by_chapter={}),
        llm=llm,
    )

    await service.analyze_document(uuid.uuid4())

    assert llm.llm_called


async def test_skips_chapter_with_insufficient_content_without_llm_call() -> None:
    chapter = _FakeChapter(uuid.uuid4(), "Chapter 1")
    short_content = (
        "Contents\n"
        "Chapter 1: Introduction\n"
        "Chapter 2: Foundations\n"
        "Chapter 3: Regression\n"
    )
    chunk = _FakeChunk(uuid.uuid4(), chapter.id, content=short_content)
    llm = _LLM()

    service = _make_service(
        chapters=[chapter],
        chunks=[chunk],
        topics=_TopicRepo(by_chapter={}),
        llm=llm,
    )

    result = await service.analyze_document(uuid.uuid4())

    assert not llm.llm_called
    assert result == []


async def test_skips_reanalysis_when_some_chapters_still_unanalyzed() -> None:
    analyzed_chapter = _FakeChapter(uuid.uuid4(), "Analyzed")
    pending_chapter = _FakeChapter(uuid.uuid4(), "Pending")
    chunks = [
        _FakeChunk(uuid.uuid4(), analyzed_chapter.id),
        _FakeChunk(uuid.uuid4(), pending_chapter.id),
    ]
    existing = _existing_topic("Existing Topic")
    llm = _LLM()

    service = _make_service(
        chapters=[analyzed_chapter, pending_chapter],
        chunks=chunks,
        topics=_TopicRepo(by_chapter={analyzed_chapter.id: [existing]}),
        llm=llm,
    )

    await service.analyze_document(uuid.uuid4())

    assert llm.llm_called


async def test_reports_context_truncation_warning(monkeypatch) -> None:
    chapter = _FakeChapter(uuid.uuid4(), "Chapter 1")
    chunks = [_FakeChunk(uuid.uuid4(), chapter.id) for _ in range(3)]
    monkeypatch.setattr(
        "app.services.content_analysis.service.get_settings",
        lambda: SimpleNamespace(ai_max_context_chars=120, ai_min_content_chars=1),
    )

    service = _make_service(
        chapters=[chapter],
        chunks=chunks,
        topics=_TopicRepo(by_chapter={}),
        llm=_LLM(),
    )

    _, warnings = await service.analyze_document_with_report(uuid.uuid4())

    assert len(warnings) == 1
    assert warnings[0]["kind"] == "context_truncated"
    assert warnings[0]["omitted_chunks"] == 2
    assert warnings[0]["total_chunks"] == 3
    assert "results may be incomplete" in warnings[0]["message"]


async def test_extraction_prompt_never_offers_other_chapter_titles() -> None:
    """Cross-chapter linking is a separate pass, not an extraction concern.

    Handing each chapter the document outline made the model cite chapter
    titles ("Chapter 1.2: Linux Fundamentals"), which the topic resolver
    cannot match, so two thirds of those references were discarded. The
    linking pass now sees every real topic title at once instead, so the
    extraction prompt must not invite cross-chapter names at all.
    """
    earlier = _FakeChapter(uuid.uuid4(), "The Web Hosting Ecosystem", 0)
    later = _FakeChapter(uuid.uuid4(), "SSL Certificates", 1)
    llm = _LLM()

    service = _make_service(
        chapters=[earlier, later],
        chunks=[
            _FakeChunk(uuid.uuid4(), earlier.id),
            _FakeChunk(uuid.uuid4(), later.id),
        ],
        topics=_TopicRepo(by_chapter={}),
        llm=llm,
    )

    await service.analyze_document(uuid.uuid4())

    assert len(llm.user_prompts) == 2

    # Each prompt names only its own chapter; no sibling chapter title is
    # offered as a citable prerequisite.
    assert "Chapter: The Web Hosting Ecosystem" in llm.user_prompts[0]
    assert "SSL Certificates" not in llm.user_prompts[0]

    assert "Chapter: SSL Certificates" in llm.user_prompts[1]
    assert "The Web Hosting Ecosystem" not in llm.user_prompts[1]

    for prompt in llm.user_prompts:
        assert "Document outline" not in prompt
        assert "(this chapter)" not in prompt
