"""Ingestion service: orchestrates document extraction, structuring, and chunking."""

from __future__ import annotations

import asyncio
import uuid

from app.core.exceptions import DocumentNotFound
from app.db.repositories.chunks import ChunkRepository
from app.db.repositories.documents import DocumentRepository
from app.db.repositories.pages import PageRepository
from app.db.repositories.structure import StructureRepository
from app.models.chapter import Chapter
from app.models.chunks import Chunk
from app.models.page import Page
from app.models.section import Section
from app.services.ingestion.chunker import chunk_text
from app.services.ingestion.cleaner import clean_pages
from app.services.ingestion.document_loader import load_document_content
from app.services.ingestion.structure_detector import detect_structure
from app.services.ingestion.text_extractor import extract_pages
from app.utils.files import compute_sha256


class IngestionService:
    """Coordinates loading, extracting, structuring, and chunking documents."""

    def __init__(
        self,
        document_repository: DocumentRepository,
        page_repository: PageRepository,
        structure_repository: StructureRepository | None = None,
        chunk_repository: ChunkRepository | None = None,
    ) -> None:
        self._document_repository = document_repository
        self._page_repository = page_repository
        self._structure_repository = structure_repository
        self._chunk_repository = chunk_repository

    async def extract_document(self, document_id: uuid.UUID) -> list[Page]:
        """
        Extract and persist all pages for a document.

        Idempotent: re-running this for the same document replaces any
        previously extracted pages rather than duplicating them.
        """
        document = await self._document_repository.get_by_id(document_id)

        if document is None:
            raise DocumentNotFound(f"Document {document_id} was not found.")

        content = await load_document_content(document)

        extracted = await asyncio.to_thread(
            extract_pages, content, document.file_extension
        )
        raw_texts = [page.raw_text for page in extracted]
        cleaned_texts = clean_pages(raw_texts)

        await self._page_repository.delete_by_document(document_id)

        pages = [
            Page(
                document_id=document_id,
                page_number=extracted_page.page_number,
                raw_text=extracted_page.raw_text,
                normalized_text=cleaned_text,
                char_count=len(cleaned_text),
            )
            for extracted_page, cleaned_text in zip(
                extracted, cleaned_texts, strict=True
            )
        ]

        await self._page_repository.add_many(pages)
        await self._page_repository.commit()

        return pages

    async def detect_document_structure(
        self, document_id: uuid.UUID
    ) -> list[Chapter]:
        """
        Detect and persist chapter/section structure for a document.

        Requires pages to already be extracted (via extract_document).
        Idempotent: re-running this replaces any previously detected
        structure rather than duplicating it.
        """
        if self._structure_repository is None:
            raise RuntimeError(
                "IngestionService was constructed without a "
                "StructureRepository; cannot detect structure."
            )

        document = await self._document_repository.get_by_id(document_id)

        if document is None:
            raise DocumentNotFound(f"Document {document_id} was not found.")

        pages = await self._page_repository.list_by_document(document_id)

        if not pages:
            raise DocumentNotFound(
                f"Document {document_id} has no extracted pages. "
                f"Run extraction before detecting structure."
            )

        page_tuples = [(page.page_number, page.normalized_text) for page in pages]
        detected_chapters = detect_structure(page_tuples)

        await self._structure_repository.delete_by_document(document_id)

        chapters = [
            Chapter(
                document_id=document_id,
                number=detected.number,
                title=detected.title,
                start_page=detected.start_page,
                end_page=detected.end_page,
                order_index=detected.order_index,
                sections=[
                    Section(
                        number=section.number,
                        title=section.title,
                        start_page=section.start_page,
                        end_page=section.end_page,
                        order_index=section.order_index,
                    )
                    for section in detected.sections
                ],
            )
            for detected in detected_chapters
        ]

        await self._structure_repository.add_chapters(chapters)
        await self._structure_repository.commit()

        return chapters

    async def chunk_document(self, document_id: uuid.UUID) -> list[Chunk]:
        """
        Chunk all pages of a document and persist the resulting chunks.

        Requires pages to already be extracted (via extract_document).
        Chapter/section structure is optional: if not yet detected, chunks
        are persisted with chapter_id and section_id left null. Chunks
        never span page boundaries. Idempotent: re-running this replaces
        any previously created chunks rather than duplicating them.
        """
        if self._chunk_repository is None:
            raise RuntimeError(
                "IngestionService was constructed without a "
                "ChunkRepository; cannot chunk document."
            )

        document = await self._document_repository.get_by_id(document_id)

        if document is None:
            raise DocumentNotFound(f"Document {document_id} was not found.")

        pages = await self._page_repository.list_by_document(document_id)

        if not pages:
            raise DocumentNotFound(
                f"Document {document_id} has no extracted pages. "
                f"Run extraction before chunking."
            )

        chapters: list[Chapter] = []
        if self._structure_repository is not None:
            chapters = await self._structure_repository.list_chapters_by_document(
                document_id
            )

        await self._chunk_repository.delete_by_document(document_id)

        all_chunks: list[Chunk] = []
        document_index = 0

        for page in pages:
            chapter_id, section_id = self._resolve_structure_for_page(
                page.page_number, chapters
            )

            text_chunks = chunk_text(page.normalized_text)

            for page_index, text_chunk in enumerate(text_chunks):
                all_chunks.append(
                    Chunk(
                        document_id=document_id,
                        page_id=page.id,
                        chapter_id=chapter_id,
                        section_id=section_id,
                        document_index=document_index,
                        page_index=page_index,
                        content=text_chunk.content,
                        char_count=text_chunk.char_count,
                        content_hash=compute_sha256(
                            text_chunk.content.encode("utf-8")
                        ),
                    )
                )
                document_index += 1

        await self._chunk_repository.add_many(all_chunks)
        await self._chunk_repository.commit()

        return all_chunks

    @staticmethod
    def _resolve_structure_for_page(
        page_number: int, chapters: list[Chapter]
    ) -> tuple[uuid.UUID | None, uuid.UUID | None]:
        """Resolve which chapter/section (if any) a page number falls within."""
        for chapter in chapters:
            if chapter.start_page <= page_number <= chapter.end_page:
                for section in chapter.sections:
                    if section.start_page <= page_number <= section.end_page:
                        return chapter.id, section.id
                return chapter.id, None

        return None, None