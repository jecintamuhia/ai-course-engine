"""Unit tests for PDF/DOCX text extraction."""

from __future__ import annotations

from io import BytesIO

import pytest
from app.core.exceptions import DocumentProcessingError
from app.services.ingestion.text_extractor import (
    extract_docx_pages,
    extract_pages,
    extract_pdf_pages,
    sanitize_extracted_text,
)
from docx import Document as DocxDocument
from docx.enum.text import WD_BREAK
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def test_sanitize_extracted_text_removes_lone_surrogates() -> None:
    value = "shopping list\ud83c bullet\ud83d"

    sanitized = sanitize_extracted_text(value)

    assert "\ud83c" not in sanitized
    assert "\ud83d" not in sanitized
    assert sanitized == "shopping list\ufffd bullet\ufffd"
    sanitized.encode("utf-8")


def test_sanitize_extracted_text_preserves_valid_pairs() -> None:
    value = "emoji \ud83d\ude00 heart \ud83d\udc9b fine"

    sanitized = sanitize_extracted_text(value)

    assert sanitized == "emoji \U0001f600 heart \U0001f49b fine"
    sanitized.encode("utf-8")


def test_sanitize_extracted_text_trailing_high_surrogate() -> None:
    sanitized = sanitize_extracted_text("plain text \ud83d")

    assert sanitized == "plain text \ufffd"
    sanitized.encode("utf-8")


def _build_sample_pdf() -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    c.drawString(72, 750, "AI Course Engine Textbook")
    c.drawString(72, 700, "Chapter 1: Introduction to Systems")
    c.drawString(72, 50, "Page 1")
    c.showPage()

    c.drawString(72, 750, "AI Course Engine Textbook")
    c.drawString(72, 700, "Continuing the discussion.")
    c.drawString(72, 50, "Page 2")
    c.showPage()

    c.save()
    return buffer.getvalue()


def _build_sample_docx_with_page_break() -> bytes:
    document = DocxDocument()
    document.add_paragraph("First page heading")
    document.add_paragraph("First page content")

    paragraph = document.add_paragraph()
    run = paragraph.add_run()
    run.add_break(WD_BREAK.PAGE)

    document.add_paragraph("Second page content")

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_extract_pdf_pages_returns_one_entry_per_page() -> None:
    content = _build_sample_pdf()
    pages = extract_pdf_pages(content)

    assert len(pages) == 2
    assert pages[0].page_number == 1
    assert "Chapter 1" in pages[0].raw_text
    assert pages[1].page_number == 2
    assert "Continuing the discussion" in pages[1].raw_text


def test_pdf_extraction_prefers_layout_mode(monkeypatch) -> None:
    """Layout mode must be attempted first for word spacing.

    Regression: pypdf's default mode returned
    "TheDomainNameSystemistheinternet'sphonebook" for a real textbook,
    destroying headings, topic titles and LLM input quality.
    """
    calls: list[str] = []

    class _FakePage:
        def extract_text(self, extraction_mode=None):
            calls.append(extraction_mode or "default")
            if extraction_mode == "layout":
                return "1.3 DNS — The Domain Name System, Explained in Full"
            return "1.3 DNS—TheDomainNameSystem,ExplainedinFull"

    class _FakeReader:
        pages = [_FakePage()]

    monkeypatch.setattr(
        "app.services.ingestion.text_extractor.PdfReader",
        lambda _buffer: _FakeReader(),
    )

    pages = extract_pdf_pages(b"%PDF-1.4 fake")

    assert calls[0] == "layout"
    assert "The Domain Name System" in pages[0].raw_text


def test_pdf_extraction_falls_back_when_layout_yields_nothing(
    monkeypatch,
) -> None:
    """A page where layout mode returns nothing must still yield text."""

    class _FakePage:
        def extract_text(self, extraction_mode=None):
            if extraction_mode == "layout":
                return ""
            return "Plain default mode text"

    class _FakeReader:
        pages = [_FakePage()]

    monkeypatch.setattr(
        "app.services.ingestion.text_extractor.PdfReader",
        lambda _buffer: _FakeReader(),
    )

    pages = extract_pdf_pages(b"%PDF-1.4 fake")

    assert "Plain default mode text" in pages[0].raw_text


def test_pdf_extraction_falls_back_when_layout_raises(monkeypatch) -> None:
    """Layout mode failing on one page must not drop the page's content."""

    class _FakePage:
        def extract_text(self, extraction_mode=None):
            if extraction_mode == "layout":
                raise ValueError("layout mode unsupported for this page")
            return "Recovered default text"

    class _FakeReader:
        pages = [_FakePage()]

    monkeypatch.setattr(
        "app.services.ingestion.text_extractor.PdfReader",
        lambda _buffer: _FakeReader(),
    )

    pages = extract_pdf_pages(b"%PDF-1.4 fake")

    assert "Recovered default text" in pages[0].raw_text


def test_extract_pdf_pages_rejects_invalid_content() -> None:
    with pytest.raises(DocumentProcessingError):
        extract_pdf_pages(b"not a real pdf")


def test_extract_docx_pages_splits_on_explicit_page_break() -> None:
    content = _build_sample_docx_with_page_break()
    pages = extract_docx_pages(content)

    assert len(pages) == 2
    assert "First page heading" in pages[0].raw_text
    assert "First page content" in pages[0].raw_text
    assert "Second page content" in pages[1].raw_text
    assert "Second page content" not in pages[0].raw_text


def test_extract_docx_pages_without_break_returns_single_page() -> None:
    document = DocxDocument()
    document.add_paragraph("Only page content")
    buffer = BytesIO()
    document.save(buffer)

    pages = extract_docx_pages(buffer.getvalue())

    assert len(pages) == 1
    assert "Only page content" in pages[0].raw_text


def test_extract_docx_pages_rejects_invalid_content() -> None:
    with pytest.raises(DocumentProcessingError):
        extract_docx_pages(b"not a real docx")


def test_extract_pages_dispatches_by_extension() -> None:
    pdf_content = _build_sample_pdf()
    pages = extract_pages(pdf_content, ".pdf")
    assert len(pages) == 2


def test_extract_pages_rejects_unsupported_extension() -> None:
    with pytest.raises(DocumentProcessingError):
        extract_pages(b"irrelevant", ".txt")
