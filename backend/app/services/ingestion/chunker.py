"""Semantic text chunking: paragraph-based accumulation with size bounds."""

from __future__ import annotations

import re
from dataclasses import dataclass

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

DEFAULT_TARGET_SIZE = 800
DEFAULT_MAX_SIZE = 1200
DEFAULT_MIN_SIZE = 100


@dataclass(frozen=True)
class TextChunk:
    """A single chunk of text and its character count."""

    content: str
    char_count: int


def _split_into_paragraphs(text: str) -> list[str]:
    """Group consecutive non-blank lines into paragraphs, separated by blank lines."""
    paragraphs: list[str] = []
    current_lines: list[str] = []

    for line in text.splitlines():
        if line.strip() == "":
            if current_lines:
                paragraphs.append("\n".join(current_lines))
                current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        paragraphs.append("\n".join(current_lines))

    return paragraphs


def _split_oversized_paragraph(paragraph: str, max_size: int) -> list[str]:
    """Split a paragraph that exceeds max_size by sentence boundaries."""
    sentences = _SENTENCE_SPLIT.split(paragraph)
    pieces: list[str] = []
    current = ""

    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence

        if len(candidate) > max_size and current:
            pieces.append(current)
            current = sentence
        else:
            current = candidate

    if current:
        pieces.append(current)

    return pieces


def chunk_text(
    text: str,
    *,
    target_size: int = DEFAULT_TARGET_SIZE,
    max_size: int = DEFAULT_MAX_SIZE,
    min_size: int = DEFAULT_MIN_SIZE,
) -> list[TextChunk]:
    """
    Split text into semantic chunks, respecting paragraph boundaries
    where possible.

    Paragraphs are accumulated greedily until adding another would
    exceed max_size, or the current chunk has already reached
    target_size. A single paragraph larger than max_size is split by
    sentence. A final trailing chunk smaller than min_size is merged
    into the previous chunk rather than left as an orphan fragment.
    """
    text = text.strip()

    if not text:
        return []

    raw_paragraphs = _split_into_paragraphs(text)

    units: list[str] = []
    for paragraph in raw_paragraphs:
        if len(paragraph) > max_size:
            units.extend(_split_oversized_paragraph(paragraph, max_size))
        else:
            units.append(paragraph)

    chunks: list[str] = []
    current = ""

    for unit in units:
        candidate = f"{current}\n\n{unit}".strip() if current else unit

        if len(candidate) > max_size and current:
            chunks.append(current)
            current = unit
        elif len(current) >= target_size and current:
            chunks.append(current)
            current = unit
        else:
            current = candidate

    if current:
        if chunks and len(current) < min_size:
            chunks[-1] = f"{chunks[-1]}\n\n{current}".strip()
        else:
            chunks.append(current)

    return [TextChunk(content=c, char_count=len(c)) for c in chunks]