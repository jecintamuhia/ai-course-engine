"""
Deterministic chapter/section structure detection from page text.

Detection prefers, in order:

1. Keyword+number chapter headings ("Chapter 1", "Part IV", ...).
2. Dotted-decimal numbering depth ("1.3", "1.3.1"). Textbooks that number
   their sections without using the word "Chapter" are extremely common,
   and their top-level numbered divisions are the real chapters. Using
   this signal is what keeps chapter detection off command-line acronyms.
3. ALL-CAPS short lines, as a last resort. This path exists only for
   documents with no numbering at all, and rejects bare acronyms — a
   server-administration textbook is full of lines reading exactly
   "FTP", "SSL", "DNS", "BIND", "CSR", "DKIM", and treating those as
   chapters produced a document whose every real section was parented
   under a meaningless acronym.

No semantic analysis of content is performed; that is the AI provider's
job and layers on top of this deterministic structure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_CHAPTER_PATTERN = re.compile(
    r"^(chapter|part)\s+([0-9]+|[ivxlcdm]+)\s*[:.\-]?\s*(.*)$",
    re.IGNORECASE,
)

# Dotted-decimal numbering, e.g. "1.3" or "1.3.1". Captures the number, an
# optional separator, and the title. The title may begin with an uppercase
# letter, a digit ("30-Day Certification Study Plan"), or a lowercase-led
# brand name ("cPanel/WHM ..."); requiring [A-Z] here silently dropped
# every "cPanel..." subsection and the "5.3 30-Day..." chapter from the
# WHM textbook, because those headings never matched.
_NUMBERED_PATTERN = re.compile(
    r"^(\d+(?:\.\d+)+)\s*[:.\-]?\s+((?:[A-Z0-9]|[a-z][A-Z])[^\n]{1,100})$"
)

_ALL_CAPS_HEADING = re.compile(r"^[A-Z][A-Z0-9 ,'\-:]{2,79}$")

# A single all-caps token with no spaces, e.g. "FTP", "SSH", "HTTPS'".
_SINGLE_UPPERCASE_TOKEN = re.compile(r"^[A-Z][A-Z0-9'\-]*$")

# A line that begins a new numbered/chapter heading, used to stop a wrapped
# title from swallowing the heading that follows it.
_NEW_HEADING = re.compile(r"^(?:\d+(?:\.\d+)+|chapter\s|part\s)", re.IGNORECASE)


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
    return not stripped.endswith((".", ",", ";"))


# A wrapped continuation fragment is short and is a word or two, not a clause.
_MAX_CONTINUATION_CHARS = 60
_MAX_CONTINUATION_WORDS = 4
_MAX_CONTINUATION_LINES = 2


def _is_continuation_fragment(line: str) -> bool:
    """
    True for a line shaped like the tail of a wrapped heading.

    The word limit is what separates a wrapped title from running prose:
    real continuations are short tails ("Full", "Three Panels", "PTR"),
    while a body line that happens to be short ("This is body text that
    is") is a clause and is not absorbed.
    """
    candidate = line.strip()
    if not candidate or len(candidate) > _MAX_CONTINUATION_CHARS:
        return False
    if not _looks_like_heading_candidate(candidate):
        return False
    if _NEW_HEADING.match(candidate):
        return False
    if candidate.endswith(("—", "-", "–")):
        return False
    return len(candidate.split()) <= _MAX_CONTINUATION_WORDS


def _wrapped_continuation_run(lines: list[str], head_index: int) -> list[str]:
    """
    Return the lines that continue ``lines[head_index]``'s heading.

    Layout-mode PDF extraction keeps a multi-line heading as separate
    lines, so "1.3 DNS — The Domain Name System, Explained in" is followed
    by a bare "Full" on the next line. Taking only the first line yields
    titles ending in dangling words ("Explained in", "From Concepts to"),
    and those truncated titles are what the AI is later told to cite as
    prerequisite names.

    The run is accepted only when the heading block is unambiguously
    finished immediately after it, which requires a blank line. Seeing
    that blank line is what keeps ordinary body text following a heading
    from being absorbed into the title. A heading wrapped across a page
    boundary is therefore left truncated, which is the safe direction to
    be wrong in.
    """
    run: list[str] = []
    index = head_index + 1

    while index < len(lines) and len(run) < _MAX_CONTINUATION_LINES:
        if not _is_continuation_fragment(lines[index]):
            break
        run.append(lines[index].strip())
        index += 1

    if not run:
        return []

    if index < len(lines) and lines[index].strip():
        return []

    return run


def _merge_wrapped_headings(lines: list[str]) -> list[str]:
    """
    Join headings that the PDF laid out across several lines into one
    logical line, so the heading patterns below see whole titles.
    """
    merged: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index].strip()

        if not line or not _looks_like_heading_candidate(line):
            merged.append(line)
            index += 1
            continue

        run = _wrapped_continuation_run(lines, index)
        if run:
            merged.append(" ".join([line, *run]))
            index += 1 + len(run)
            continue

        merged.append(line)
        index += 1

    return merged


def _is_bare_acronym(line: str) -> bool:
    """
    True for a short single all-caps token such as "FTP", "SSL", "DNS",
    "BIND", "CSR", "DKIM".

    Technical books are full of command names, protocol acronyms and file
    extensions that match an ALL-CAPS heading pattern. Rejecting short
    single tokens keeps the fallback from shredding such a book into
    dozens of one-word "chapters".

    Length is the discriminator: command and extension names are short
    ("FTP", "CSR", "HTTPS"), while single-word headings are not
    ("INTRODUCTION", "METHODOLOGY"). This is a heuristic, not a certainty
    — a five-letter acronym such as "WHMCS" still passes — so this path is
    only reached for documents with no numbering at all.
    """
    candidate = line.strip().rstrip("'")
    if " " in candidate or not candidate:
        return False
    if not _SINGLE_UPPERCASE_TOKEN.match(candidate):
        return False
    return len(candidate) <= 4


def _scan_headings(
    pages: list[tuple[int, str]],
) -> tuple[
    list[tuple[int, str | None, str]],
    list[tuple[int, str, str]],
    list[tuple[int, str, str]],
]:
    """
    Single pass over the document collecting three heading kinds:

    - keyword+number chapter headings ("Chapter 1")
    - dotted-decimal headings (all depths)
    - dotted-decimal section headings (depth >= 2, i.e. 1.3.1)

    Scanning once keeps the detector from walking the text repeatedly for
    each strategy.
    """
    chapter_boundaries: list[tuple[int, str | None, str]] = []
    numbered_boundaries: list[tuple[int, str, str]] = []
    section_boundaries: list[tuple[int, str, str]] = []

    for page_number, text in pages:
        for line in _merge_wrapped_headings(text.splitlines()):
            if not line or not _looks_like_heading_candidate(line):
                continue

            chapter_match = _CHAPTER_PATTERN.match(line)
            if chapter_match:
                number = chapter_match.group(2)
                title = chapter_match.group(3).strip() or f"Chapter {number}"
                chapter_boundaries.append((page_number, number, title))
                continue

            numbered_match = _NUMBERED_PATTERN.match(line)
            if numbered_match:
                number = numbered_match.group(1)
                title = numbered_match.group(2).strip()
                numbered_boundaries.append((page_number, number, title))

                if number.count(".") >= 1:
                    section_boundaries.append((page_number, number, title))

    return chapter_boundaries, numbered_boundaries, section_boundaries


def _numbering_depth(number: str) -> int:
    """Dotted-decimal depth: "1.3" -> 2, "1.3.1" -> 3."""
    return number.count(".") + 1


def _numbered_chapter_boundaries(
    numbered_boundaries: list[tuple[int, str, str]],
) -> list[tuple[int, str | None, str]]:
    """
    Promote the shallowest dotted-decimal depth to chapter boundaries.

    A book numbered 1.1, 1.2, ... 1.9, 2.1, ... has chapters at depth 2
    ("1.3") and sections at depth 3 ("1.3.1"). A book numbered only
    1, 1.1, 1.1.1 ... has chapters at depth 1 — but bare "1" is not
    matched by the dotted-decimal pattern, so the shallowest depth
    actually seen is always the chapter depth.
    """
    if not numbered_boundaries:
        return []

    chapter_depth = min(
        _numbering_depth(number) for _, number, _ in numbered_boundaries
    )

    return [
        (page_number, number, title)
        for page_number, number, title in numbered_boundaries
        if _numbering_depth(number) == chapter_depth
    ]


def _find_parent_chapter(
    chapters: list[DetectedChapter],
    section_number: str,
    section_page: int,
) -> DetectedChapter | None:
    """
    Find the chapter a numbered section belongs to.

    Prefers numbering over page ranges: the section's number is matched to
    the chapter whose number is its leading segment, so "1.1.4" belongs to
    chapter "1.1" even when the heading lands on the first page of chapter
    "1.2". Page-range assignment alone put "Data Centres and Server
    Infrastructure" (1.1.4) inside chapter 1.2 because the two headings
    share a page.

    A numbered match is still refused when the heading appears *before* the
    chapter it claims. That is front matter or a table of contents, not
    chapter content, and keeps pre-chapter sections from being absorbed
    into the first chapter.

    Falls back to page range for documents whose chapters carry no number
    (the ALL-CAPS path), where numbering cannot arbitrate.
    """
    if "." in section_number:
        prefix = section_number.rsplit(".", 1)[0]
        for chapter in chapters:
            if chapter.number == prefix and section_page >= chapter.start_page:
                return chapter

    for chapter in chapters:
        if chapter.start_page <= section_page <= chapter.end_page:
            return chapter

    return None


def detect_structure(
    pages: list[tuple[int, str]],
) -> list[DetectedChapter]:
    """
    Detect chapter/section structure from a document's extracted pages.

    ``pages`` is a list of (page_number, normalized_text) tuples in page
    order. Returns detected chapters in document order, each with its
    resolved page span and any nested sections.

    Detection order:
    1. Keyword+number chapter headings ("Chapter 1", "Part IV", ...).
    2. Dotted-decimal numbering ("1.1", "1.3.1"): the shallowest depth
       becomes the chapters, deeper levels become their sections. This
       covers textbooks that number their divisions but never use the
       word "Chapter".
    3. ALL-CAPS short-line headings, rejecting bare acronyms. This is a
       last resort for documents with no numbering whatsoever; sections
       are not detected in this path, since dotted section numbering
       without a numbered chapter context is unreliable to attribute.

    A page span with no detected next boundary extends to the document's
    last page. Sentence fragments containing numbers (e.g. "3.14", "table
    4.5") are excluded by the heading-candidate pre-filter and the
    section pattern's requirement of a capitalized, non-sentence-ending
    title.
    """
    (
        chapter_boundaries,
        numbered_boundaries,
        section_boundaries,
    ) = _scan_headings(pages)

    if not chapter_boundaries:
        chapter_boundaries = _numbered_chapter_boundaries(numbered_boundaries)
        # Sections come from the depths below the chapter depth; anything
        # at chapter depth is the chapter itself.
        if chapter_boundaries:
            chapter_depth = _numbering_depth(chapter_boundaries[0][1])
            section_boundaries = [
                item
                for item in section_boundaries
                if _numbering_depth(item[1]) > chapter_depth
            ]

    if not chapter_boundaries:
        for page_number, text in pages:
            for line in _merge_wrapped_headings(text.splitlines()):
                if (
                    _ALL_CAPS_HEADING.match(line)
                    and len(line.split()) <= 8
                    and not _is_bare_acronym(line)
                ):
                    chapter_boundaries.append((page_number, None, line.title()))

    if not chapter_boundaries:
        return []

    last_page = pages[-1][0] if pages else chapter_boundaries[-1][0]

    chapters: list[DetectedChapter] = []
    for index, (page_number, number, title) in enumerate(chapter_boundaries):
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
        target_chapter = _find_parent_chapter(chapters, section_number, section_page)

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
                # A section heading can share a page with the next chapter's
                # heading, putting it past its own chapter's nominal end.
                # Never emit an inverted range (end before start).
                end_page=max(new_end, section.start_page),
                order_index=section.order_index,
            )

    return chapters
