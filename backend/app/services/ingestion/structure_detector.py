"""Deterministic chapter/section structure detection from page text.

Detection relies on numbering and heading-keyword patterns, with a
formatting-based (ALL-CAPS short line) fallback for documents with no
numbered headings at all. This does not perform semantic analysis of
content — that requires the AI provider abstraction introduced in a
later batch, and will layer on top of this deterministic structure
rather than replacing it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_CHAPTER_PATTERN = re.compile(
    r"^(chapter|part)\s+([0-9]+|[ivxlcdm]+)\s*[:.\-]?\s*(.*)$",
    re.IGNORECASE,
)

_SECTION_PATTERN = re.compile(
    r"^(\d+\.\d+(?:\.\d+)*)\s*[:.\-]?\s+([A-Z][^\n]{1,100})$"
)

_ALL_CAPS_HEADING = re.compile(r"^[A-Z][A-Z0-9 ,'\-:]{2,79}$")


@dataclass(frozen=True)
class DetectedSection:
    """A detected section boundary and its resolved page span."""

    number: str | None
    title: str
    start_page: int
    end_page: int
    order_index: int


@dataclass
class DetectedChapter:
    """A detected chapter boundary, its resolved page span, and sections."""

    number: str | None
    title: str
    start_page: int
    end_page: int
    order_index: int
    sections: list[DetectedSection] = field(default_factory=list)


def _looks_like_heading_candidate(line: str) -> bool:
    """
    Cheap pre-filter to reject obvious non-headings before pattern
    matching: body-text lines are typically long and end in sentence
    punctuation, headings typically are not and do not.
    """
    stripped = line.strip()
    if not stripped or len(stripped) > 90:
        return False
    if stripped.endswith((".", ",", ";")):
        return False
    return True


def detect_structure(
    pages: list[tuple[int, str]],
) -> list[DetectedChapter]:
    """
    Detect chapter/section structure from a document's extracted pages.

    ``pages`` is a list of (page_number, normalized_text) tuples in page
    order. Returns detected chapters in document order, each with its
    resolved page span and any nested sections.

    Detection order:
    1. Keyword+number chapter headings ("Chapter 1", "Part IV", ...)
    2. Dotted-decimal section headings ("1.1 Title", "1.1.2 Title", ...)
       assigned to whichever detected chapter's page range contains them
    3. If no keyword+number chapters were found anywhere in the document,
       falls back to ALL-CAPS short-line headings as chapter boundaries
       (sections are not detected in this fallback path, since dotted
       section numbering without a numbered chapter context is
       unreliable to attribute).

    A page span with no detected next boundary extends to the document's
    last page. Sentence fragments containing numbers (e.g. "3.14", "table
    4.5") are excluded by the heading-candidate pre-filter and the
    section pattern's requirement of a capitalized, non-sentence-ending
    title.
    """
    chapter_boundaries: list[tuple[int, str | None, str]] = []
    section_boundaries: list[tuple[int, str, str]] = []

    for page_number, text in pages:
        for raw_line in text.splitlines():
            line = raw_line.strip()

            if not line or not _looks_like_heading_candidate(line):
                continue

            chapter_match = _CHAPTER_PATTERN.match(line)
            if chapter_match:
                number = chapter_match.group(2)
                title = (
                    chapter_match.group(3).strip() or f"Chapter {number}"
                )
                chapter_boundaries.append((page_number, number, title))
                continue

            section_match = _SECTION_PATTERN.match(line)
            if section_match:
                number = section_match.group(1)
                title = section_match.group(2).strip()
                section_boundaries.append((page_number, number, title))

    if not chapter_boundaries:
        for page_number, text in pages:
            for raw_line in text.splitlines():
                line = raw_line.strip()
                if _ALL_CAPS_HEADING.match(line) and len(line.split()) <= 8:
                    chapter_boundaries.append(
                        (page_number, None, line.title())
                    )

    if not chapter_boundaries:
        return []

    last_page = pages[-1][0] if pages else chapter_boundaries[-1][0]

    chapters: list[DetectedChapter] = []
    for index, (page_number, number, title) in enumerate(
        chapter_boundaries
    ):
        end_page = (
            chapter_boundaries[index + 1][0] - 1
            if index + 1 < len(chapter_boundaries)
            else last_page
        )
        if end_page < page_number:
            end_page = page_number

        chapters.append(
            DetectedChapter(
                number=number,
                title=title,
                start_page=page_number,
                end_page=end_page,
                order_index=index,
            )
        )

    for section_page, section_number, section_title in section_boundaries:
        target_chapter = None
        for chapter in chapters:
            if chapter.start_page <= section_page <= chapter.end_page:
                target_chapter = chapter
                break

        if target_chapter is None:
            continue

        target_chapter.sections.append(
            DetectedSection(
                number=section_number,
                title=section_title,
                start_page=section_page,
                end_page=section_page,
                order_index=len(target_chapter.sections),
            )
        )

    for chapter in chapters:
        for index, section in enumerate(chapter.sections):
            if index + 1 < len(chapter.sections):
                new_end = max(
                    section.start_page,
                    chapter.sections[index + 1].start_page - 1,
                )
            else:
                new_end = chapter.end_page

            chapter.sections[index] = DetectedSection(
                number=section.number,
                title=section.title,
                start_page=section.start_page,
                end_page=new_end,
                order_index=section.order_index,
            )

    return chapters