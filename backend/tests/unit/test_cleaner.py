"""Unit tests for text normalization and header/footer cleanup."""

from __future__ import annotations

from app.services.ingestion.cleaner import (
    clean_pages,
    detect_repeated_lines,
    normalize_text,
    strip_page_number_footers,
    strip_repeated_lines,
)


def test_normalize_text_collapses_horizontal_whitespace() -> None:
    result = normalize_text("Multiple   lines   with    spacing")
    assert result == "Multiple lines with spacing"


def test_normalize_text_collapses_excess_blank_lines() -> None:
    result = normalize_text("Line one\n\n\n\n\nLine two")
    assert result == "Line one\n\nLine two"


def test_normalize_text_strips_leading_trailing_whitespace() -> None:
    result = normalize_text("  \n  content  \n  ")
    assert result == "content"


def test_detect_repeated_lines_requires_minimum_pages() -> None:
    pages = ["Header\nContent A", "Header\nContent B"]
    assert detect_repeated_lines(pages, min_page_count=3) == set()


def test_detect_repeated_lines_finds_majority_repeated_line() -> None:
    pages = [
        "AI Course Engine Textbook\nChapter 1 content",
        "AI Course Engine Textbook\nChapter 1 continued",
        "AI Course Engine Textbook\nChapter 1 wraps up",
    ]
    repeated = detect_repeated_lines(pages)
    assert "AI Course Engine Textbook" in repeated
    assert "Chapter 1 content" not in repeated


def test_strip_repeated_lines_removes_only_matched_lines() -> None:
    text = "Header\nReal content\nHeader"
    result = strip_repeated_lines(text, {"Header"})
    assert result == "Real content"


def test_strip_page_number_footers_removes_page_n_pattern() -> None:
    text = "Real content\nPage 3"
    assert strip_page_number_footers(text) == "Real content"


def test_strip_page_number_footers_removes_page_n_of_m_pattern() -> None:
    text = "Real content\nPage 3 of 16"
    assert strip_page_number_footers(text) == "Real content"


def test_strip_page_number_footers_preserves_content_lines() -> None:
    text = "This page has 3 sections\nPage 3"
    result = strip_page_number_footers(text)
    assert "This page has 3 sections" in result
    assert "Page 3" not in result.splitlines()


def test_clean_pages_full_pipeline_matches_verified_behavior() -> None:
    pages_text = [
        "AI Course Engine Textbook\nChapter 1: Introduction to Systems\n"
        "This is the first page of content discussing systems theory.\n"
        "Page 1",
        "AI Course Engine Textbook\n"
        "Continuing the discussion of systems theory in more depth.\n"
        "Multiple lines   with   irregular   spacing.\nPage 2",
        "AI Course Engine Textbook\nFinal page wraps up chapter one.\n"
        "Page 3",
    ]

    cleaned = clean_pages(pages_text)

    assert len(cleaned) == 3
    for page in cleaned:
        assert "AI Course Engine Textbook" not in page

    assert "Chapter 1: Introduction to Systems" in cleaned[0]
    assert "Multiple lines with irregular spacing." in cleaned[1]
    assert "Final page wraps up chapter one." in cleaned[2]