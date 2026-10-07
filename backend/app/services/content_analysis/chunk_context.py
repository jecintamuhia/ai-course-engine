"""Chunk-marker context building and citation resolution for provenance."""

from __future__ import annotations

import uuid

from app.models.chunks import Chunk


def build_marker_annotated_context(
    chunks: list[Chunk],
    *,
    max_chars: int | None = None,
) -> tuple[str, dict[str, uuid.UUID]]:
    """
    Build LLM-facing text with a short citation marker before each
    chunk, and a map from marker back to that chunk's real ID.

    Markers are simple sequential tokens ("C1", "C2", ...) rather than
    partial UUIDs, so the model can reproduce them exactly without
    transcription risk, and an invalid one is trivially detectable.

    When ``max_chars`` is given, the annotated text is capped at that
    many characters by keeping whole leading chunks and dropping later
    ones. The marker map only ever contains chunks that were actually
    included, so a marker for an omitted chunk is treated as a
    hallucinated citation by the caller. A short truncation note is
    appended so the model does not assume it saw the full chapter.
    """
    marker_to_chunk_id: dict[str, uuid.UUID] = {}
    lines: list[str] = []
    used_chars = 0
    omitted = 0

    for index, chunk in enumerate(chunks, start=1):
        line = f"[C{index}] {chunk.content}"
        cumulative = used_chars + len(line) + (2 if lines else 0)

        if max_chars is not None and lines and cumulative > max_chars:
            omitted += 1
            continue

        marker_to_chunk_id[f"C{index}"] = chunk.id
        lines.append(line)
        used_chars = cumulative

    text = "\n\n".join(lines)

    if omitted:
        text += (
            f"\n\n[Source truncated: {omitted} later chunk(s) omitted "
            "from this request.]"
        )

    return text, marker_to_chunk_id


def resolve_markers(
    markers: list[str], marker_map: dict[str, uuid.UUID]
) -> tuple[list[uuid.UUID], list[str]]:
    """
    Resolve a list of cited markers against the known marker map.

    Returns (resolved_chunk_ids, dropped_markers). A marker not present
    in marker_map (a hallucinated citation) is dropped rather than
    raising or silently fabricating a reference — the caller is
    expected to log dropped_markers.
    """
    resolved: list[uuid.UUID] = []
    dropped: list[str] = []

    for marker in markers:
        if marker in marker_map:
            resolved.append(marker_map[marker])
        else:
            dropped.append(marker)

    return resolved, dropped
