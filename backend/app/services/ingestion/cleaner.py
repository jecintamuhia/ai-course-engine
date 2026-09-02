"""Text normalization and header/footer cleanup for extracted pages."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

_WHITESPACE_RUN = re.compile(r"[ \t]+")
_BLANK_LINE_RUN = re.compile(r"\n{3,}")
_PAGE_NUMBER_FOOTER = re.compile(
    r"^(page\s+\d+(\s+of\s+\d+)?|\d+)$", re.IGNORECASE
)


def normalize_text(raw_text: str) -> str:
    """
    Normalize raw extracted text.

    Applies Unicode NFKC normalization, collapses runs of horizontal
    whitespace, trims each line, and collapses 3+ consecutive blank
    lines down to a single blank line.
    """
    text = unicodedata.normalize("NFKC", raw_text)

    lines = [
        _WHITESPACE_RUN.sub(" ", line).strip() for line in text.splitlines()
    ]
    text = "\n".join(lines)
    text = _BLANK_LINE_RUN.sub("\n\n", text)

    return text.strip()


def detect_repeated_lines(
    pages_text: list[str],
    *,
    min_page_count: int = 3,
    threshold: float = 0.6,
) -> set[str]:
    """
    Detect lines that repeat across a majority of a document's pages
    (e.g. running headers, titles, watermarks).

    Requires at least min_page_count pages before attempting detection,
    since repetition across 1-2 pages is not a reliable signal. A line
    must appear on at least ``threshold`` fraction of pages to qualify.
    """
    if len(pages_text) < min_page_count:
        return set()

    line_page_counts: Counter[str] = Counter()

    for text in pages_text:
        lines_on_page = {
            line.strip() for line in text.splitlines() if line.strip()
        }
        for line in lines_on_page:
            line_page_counts[line] += 1

    required = max(2, int(len(pages_text) * threshold))

    return {
        line for line, count in line_page_counts.items() if count >= required
    }


def strip_repeated_lines(text: str, repeated_lines: set[str]) -> str:
    """Remove lines matching a previously detected repeated-line set."""
    if not repeated_lines:
        return text

    kept = [
        line
        for line in text.splitlines()
        if line.strip() not in repeated_lines
    ]

    return "\n".join(kept).strip()


def strip_page_number_footers(text: str) -> str:
    """
    Remove standalone page-number-style footer lines (e.g. "Page 3",
    "Page 3 of 16", or a bare "3") that a repeated-line check would miss
    because the number differs on every page.
    """
    lines = text.splitlines()

    kept = [
        line for line in lines if not _PAGE_NUMBER_FOOTER.match(line.strip())
    ]

    return "\n".join(kept).strip()


def clean_pages(pages_text: list[str]) -> list[str]:
    """
    Apply the full cleaning pipeline to a document's pages: normalize,
    detect and strip document-wide repeated lines, then strip
    page-number-style footers.
    """
    normalized = [normalize_text(text) for text in pages_text]
    repeated = detect_repeated_lines(normalized)

    cleaned = []
    for text in normalized:
        text = strip_repeated_lines(text, repeated)
        text = strip_page_number_footers(text)
        cleaned.append(text)

    return cleaned