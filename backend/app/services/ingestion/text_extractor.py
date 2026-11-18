"""Per-page text extraction for PDF and DOCX documents."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from app.core.exceptions import DocumentProcessingError
from docx import Document as DocxDocument
from pypdf import PdfReader
from pypdf.errors import PdfReadError

_PAGE_BREAK_XML_MARKER = 'type="page"'


@dataclass(frozen=True)
class ExtractedPage:
    """A single extracted page: its 1-based page number and raw text."""

    page_number: int
    raw_text: str


def sanitize_extracted_text(value: str) -> str:
    """
    Make extracted text safe to persist as UTF-8.

    PDF/DOCX extractors can emit Unicode surrogate code units for glyphs
    whose font maps to the private-use/surrogate range (decorative
    bullets and emoji in real textbooks are common culprits).
    PostgreSQL (via asyncpg) rejects such text as "surrogates not
    allowed", which failed real ingestion runs.

    Adjacent high+low surrogates are recombined into the astral scalar
    they stand for, preserving genuine emoji. Any other surrogate
    (an unpaired half) is replaced with U+FFFD so the fact that a glyph
    was present is never fabricated away: unknown glyphs become an
    explicit replacement character, and known characters survive.
    """
    result: list[str] = []
    index = 0

    while index < len(value):
        code_point = ord(value[index])
        if 0xD800 <= code_point <= 0xDBFF:
            if index + 1 < len(value):
                next_code_point = ord(value[index + 1])
                if 0xDC00 <= next_code_point <= 0xDFFF:
                    scalar = (
                        0x10000
                        + ((code_point - 0xD800) << 10)
                        + (next_code_point - 0xDC00)
                    )
                    result.append(chr(scalar))
                    index += 2
                    continue
            result.append("\ufffd")
            index += 1
            continue
        if 0xDC00 <= code_point <= 0xDFFF:
            result.append("\ufffd")
            index += 1
            continue
        result.append(value[index])
        index += 1

    return "".join(result)


def _extract_page_text(page) -> str:
    """
    Extract one PDF page's text, preferring layout-aware extraction.

    Layout mode reconstructs word spacing from glyph positions. When it
    fails (or yields nothing on a page that has text), the default mode is
    used so a single malformed page cannot drop content.
    """
    try:
        layout_text = page.extract_text(extraction_mode="layout")
    except Exception:
        layout_text = None

    if layout_text and layout_text.strip():
        return layout_text

    return page.extract_text() or ""


def extract_pdf_pages(content: bytes) -> list[ExtractedPage]:
    """
    Extract text per page from PDF content.

    Uses pypdf's ``layout`` extraction mode. The default mode concatenates
    positioned glyphs without honouring the PDF's inter-word spacing, which
    on real textbooks produced word-salad such as
    ``TheDomainNameSystemistheinternet'sphonebook`` and destroyed heading
    detection, topic titles, and LLM input quality. Layout mode recovers
    the spacing (verified on a 101-page server-administration textbook:
    12,376 real words and 130 numbered headings recovered, versus 0 in
    default mode).

    Falls back to the default mode per page if layout extraction fails,
    so an unusual PDF degrades to the previous behaviour rather than to no
    text at all.

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
            text = _extract_page_text(page)
        except Exception as exc:
            raise DocumentProcessingError(
                f"Failed to extract text from PDF page {index}: {exc}"
            ) from exc

        pages.append(
            ExtractedPage(
                page_number=index,
                raw_text=sanitize_extracted_text(text),
            )
        )

    if not pages:
        raise DocumentProcessingError("PDF contains no pages.")

    if all(not page.raw_text.strip() for page in pages):
        raise DocumentProcessingError(
            "PDF contains no extractable text. Scanned or image-only PDFs "
            "require OCR, which is not configured."
        )

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
                    raw_text=sanitize_extracted_text("\n".join(current_lines)),
                )
            )
            page_number += 1
            current_lines = []

        if paragraph.text:
            current_lines.append(paragraph.text)

    pages.append(
        ExtractedPage(
            page_number=page_number,
            raw_text=sanitize_extracted_text("\n".join(current_lines)),
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
