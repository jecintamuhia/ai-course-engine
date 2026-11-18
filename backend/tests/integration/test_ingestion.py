"""Integration tests for ingestion orchestration with in-memory repositories."""

from __future__ import annotations

import uuid

from app.models.chapter import Chapter
from app.models.document import Document, DocumentStatus
from app.models.page import Page
from app.services.ingestion.service import IngestionService
from app.services.ingestion.text_extractor import ExtractedPage
from app.utils.files import compute_sha256

HEADER = "SkillUp Action Africa Field Guide"


def _document(document_id: uuid.UUID) -> Document:
    return Document(
        id=document_id,
        original_filename="networking_textbook.pdf",
        storage_filename="networking_textbook.pdf",
        storage_path="/does/not/need/to/exist.pdf",
        mime_type="application/pdf",
        file_extension=".pdf",
        size_bytes=9000,
        sha256_hash="a" * 64,
        version_number=1,
        is_latest_version=True,
        status=DocumentStatus.UPLOADED,
    )


class _DocumentRepository:
    def __init__(self, document: Document) -> None:
        self.document = document
        self.requests: list[uuid.UUID] = []

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        self.requests.append(document_id)
        return self.document


class _PageRepository:
    def __init__(self) -> None:
        self.pages: list[Page] = []
        self.deletions: list[uuid.UUID] = []
        self.commits = 0

    async def delete_by_document(self, document_id: uuid.UUID) -> None:
        self.deletions.append(document_id)
        self.pages = [page for page in self.pages if page.document_id != document_id]

    async def add_many(self, pages: list[Page]) -> None:
        for page in pages:
            page.id = uuid.uuid4()
        self.pages.extend(pages)

    async def list_by_document(self, document_id: uuid.UUID) -> list[Page]:
        return [page for page in self.pages if page.document_id == document_id]

    async def commit(self) -> None:
        self.commits += 1


class _StructureRepository:
    def __init__(self) -> None:
        self.chapters: list[Chapter] = []
        self.deletions: list[uuid.UUID] = []
        self.commits = 0

    async def delete_by_document(self, document_id: uuid.UUID) -> None:
        self.deletions.append(document_id)
        self.chapters = [
            chapter for chapter in self.chapters if chapter.document_id != document_id
        ]

    async def add_chapters(self, chapters: list[Chapter]) -> None:
        for chapter in chapters:
            chapter.id = uuid.uuid4()
            for section in chapter.sections:
                section.id = uuid.uuid4()
        self.chapters.extend(chapters)

    async def list_chapters_by_document(self, document_id: uuid.UUID) -> list[Chapter]:
        return [
            chapter for chapter in self.chapters if chapter.document_id == document_id
        ]

    async def commit(self) -> None:
        self.commits += 1


class _ChunkRepository:
    def __init__(self) -> None:
        self.chunks: list = []
        self.deletions: list[uuid.UUID] = []
        self.commits = 0

    async def delete_by_document(self, document_id: uuid.UUID) -> None:
        self.deletions.append(document_id)
        self.chunks = [
            chunk for chunk in self.chunks if chunk.document_id != document_id
        ]

    async def add_many(self, chunks: list) -> None:
        for chunk in chunks:
            chunk.id = uuid.uuid4()
        self.chunks.extend(chunks)

    async def list_by_document(self, document_id: uuid.UUID) -> list:
        return [chunk for chunk in self.chunks if chunk.document_id == document_id]

    async def commit(self) -> None:
        self.commits += 1


def _fake_extraction(monkeypatch, raw_pages: list[str]) -> list[Document]:
    """Replace file loading and PDF/DOCX parsing with deterministic pages."""
    loaded: list[Document] = []

    async def load(document: Document) -> bytes:
        loaded.append(document)
        return b"deterministic-source-bytes"

    def extract(content: bytes, extension: str) -> list[ExtractedPage]:
        assert content == b"deterministic-source-bytes"
        assert extension == ".pdf"
        return [
            ExtractedPage(page_number=number, raw_text=text)
            for number, text in enumerate(raw_pages, start=1)
        ]

    monkeypatch.setattr("app.services.ingestion.service.load_document_content", load)
    monkeypatch.setattr("app.services.ingestion.service.extract_pages", extract)
    return loaded


def _service(
    document: Document,
) -> tuple[IngestionService, _PageRepository, _StructureRepository, _ChunkRepository]:
    pages = _PageRepository()
    structure = _StructureRepository()
    chunks = _ChunkRepository()
    return (
        IngestionService(_DocumentRepository(document), pages, structure, chunks),
        pages,
        structure,
        chunks,
    )


async def test_extract_clean_and_chunk_flow_with_fake_repositories(monkeypatch) -> None:
    """Extraction feeds cleaning, which feeds chunking and persistence."""
    document_id = uuid.uuid4()
    document = _document(document_id)
    long_paragraphs = "\n\n".join(
        f"Paragraph {index}: " + "resolver behaviour " * 45 for index in range(2)
    )
    raw_pages = [
        (
            f"  {HEADER}  \nChapter 1: DNS Basics\n\n"
            "The  domain  name system maps names to addresses.\nPage 1"
        ),
        f"{HEADER}\n1.1 Resolver Behaviour\n\n{long_paragraphs}\nPage 2",
        (
            f"{HEADER}\nChapter 2: Mail Routing\n\n"
            "Mail  exchanges route messages between hosts.\nPage 3"
        ),
    ]
    loaded = _fake_extraction(monkeypatch, raw_pages)
    service, pages, _, chunks = _service(document)

    extracted = await service.extract_document(document_id)

    assert loaded == [document]
    assert [page.page_number for page in extracted] == [1, 2, 3]
    assert extracted[0].raw_text == raw_pages[0]
    assert all(HEADER not in page.normalized_text for page in extracted)
    assert all("Page " not in page.normalized_text for page in extracted)
    assert "domain name system" in extracted[0].normalized_text
    assert all(page.char_count == len(page.normalized_text) for page in extracted)
    assert pages.deletions == [document_id]
    assert pages.commits == 1

    created = await service.chunk_document(document_id)

    assert len(created) == 4
    assert [(chunk.page_id, chunk.page_index) for chunk in created] == [
        (extracted[0].id, 0),
        (extracted[1].id, 0),
        (extracted[1].id, 1),
        (extracted[2].id, 0),
    ]
    assert [chunk.document_index for chunk in created] == [0, 1, 2, 3]
    for chunk in created:
        owner = next(page for page in extracted if page.id == chunk.page_id)
        assert chunk.content in owner.normalized_text
    assert all(
        chunk.char_count == len(chunk.content)
        and chunk.content_hash == compute_sha256(chunk.content.encode("utf-8"))
        for chunk in created
    )
    assert all(chunk.chapter_id is None for chunk in created)
    assert chunks.deletions == [document_id]
    assert chunks.commits == 1

    repeated = await service.chunk_document(document_id)

    assert len(repeated) == 4
    assert len(await chunks.list_by_document(document_id)) == 4


async def test_detected_structure_is_attached_to_chunks(monkeypatch) -> None:
    """Real detection and cleaning decide each chunk's chapter/section."""
    document_id = uuid.uuid4()
    raw_pages = [
        (
            "Chapter 1: Foundations\n\n1.1 Basics\n\n"
            "Foundations introduce the core ideas of the subject."
        ),
        (
            "1.2 Operations\n\n"
            "Operations build on the basics and prepare the advanced material."
        ),
        (
            "Chapter 2: Advanced\n\n2.1 Security\n\n"
            "Security protects the system from unexpected failures."
        ),
    ]
    _fake_extraction(monkeypatch, raw_pages)
    service, pages, structure, chunks = _service(_document(document_id))

    extracted = await service.extract_document(document_id)
    chapters = await service.detect_document_structure(document_id)
    created = await service.chunk_document(document_id)

    assert [
        (chapter.number, chapter.title, chapter.start_page, chapter.end_page)
        for chapter in chapters
    ] == [
        ("1", "Foundations", 1, 2),
        ("2", "Advanced", 3, 3),
    ]
    assert [section.title for section in chapters[0].sections] == [
        "Basics",
        "Operations",
    ]
    assert structure.deletions == [document_id]
    assert structure.commits == 1

    page_ids = {page.page_number: page.id for page in extracted}
    by_page = {
        page_id: [chunk for chunk in created if chunk.page_id == page_id]
        for page_id in page_ids.values()
    }
    first, second = chapters
    assert all(
        chunk.chapter_id == first.id and chunk.section_id == first.sections[0].id
        for chunk in by_page[page_ids[1]]
    )
    assert all(
        chunk.chapter_id == first.id and chunk.section_id == first.sections[1].id
        for chunk in by_page[page_ids[2]]
    )
    assert all(
        chunk.chapter_id == second.id and chunk.section_id == second.sections[0].id
        for chunk in by_page[page_ids[3]]
    )
    assert len(await chunks.list_by_document(document_id)) == len(created)
    assert len(await pages.list_by_document(document_id)) == 3
