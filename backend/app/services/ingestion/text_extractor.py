"""Per-page text extraction for PDF and DOCX documents."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from docx import Document as DocxDocument
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core.exceptions import DocumentProcessingError

_PAGE_BREAK_XML_MARKER = 'type="page"'


@dataclass(frozen=True)
class ExtractedPage:
    """A single extracted page: its 1-based page number and raw text."""

    page_number: int
    raw_text: str


def extract_pdf_pages(content: bytes) -> list[ExtractedPage]:
    """
    Extract text per page from PDF content.

    Raises DocumentProcessingError if the file cannot be read as a PDF,
    if a specific page fails extraction, or if the PDF has no pages.
    """
    try:
        reader = PdfReader(BytesIO(content))
    except PdfReadError as exc:
        raise DocumentProcessingError(f"Failed to read PDF: {exc}") from exc

    pages: list[ExtractedPage] = []

    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            raise DocumentProcessingError(
                f"Failed to extract text from PDF page {index}: {exc}"
            ) from exc

        pages.append(ExtractedPage(page_number=index, raw_text=text))

    if not pages:
        raise DocumentProcessingError("PDF contains no pages.")

    return pages


def extract_docx_pages(content: bytes) -> list[ExtractedPage]:
    """
    Extract text per page from DOCX content.

    DOCX has no fixed page geometry at the file-format level, so pages
    are delimited by explicit page-break runs (Ctrl+Enter in Word,
    exposed as a <w:br w:type="page"/> element). A document with no
    explicit page breaks is treated as a single page.

    Raises DocumentProcessingError if the file cannot be read as a DOCX
    or contains no content at all.
    """
    try:
        document = DocxDocument(BytesIO(content))
    except Exception as exc:
        raise DocumentProcessingError(f"Failed to read DOCX: {exc}") from exc

    pages: list[ExtractedPage] = []
    current_lines: list[str] = []
    page_number = 1

    for paragraph in document.paragraphs:
        if _PAGE_BREAK_XML_MARKER in paragraph._p.xml:
            pages.append(
                ExtractedPage(
                    page_number=page_number,
                    raw_text="\n".join(current_lines),
                )
            )
            page_number += 1
            current_lines = []

        if paragraph.text:
            current_lines.append(paragraph.text)

    pages.append(
        ExtractedPage(
            page_number=page_number, raw_text="\n".join(current_lines)
        )
    )

    if not pages or all(not p.raw_text.strip() for p in pages):
        raise DocumentProcessingError("DOCX contains no extractable text.")

    return pages


def extract_pages(content: bytes, file_extension: str) -> list[ExtractedPage]:
    """Dispatch extraction to the correct handler based on file extension."""
    if file_extension == ".pdf":
        return extract_pdf_pages(content)

    if file_extension == ".docx":
        return extract_docx_pages(content)

    raise DocumentProcessingError(
        f"No text extractor available for extension {file_extension!r}."
    )