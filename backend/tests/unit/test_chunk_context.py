"""Unit tests for chunk-marker provenance context building and resolution."""

from __future__ import annotations

import uuid

from app.models.chunks import Chunk
from app.services.content_analysis.chunk_context import (
    build_marker_annotated_context,
    resolve_markers,
)


def _fake_chunk(content: str) -> Chunk:
    chunk = Chunk(
        document_id=uuid.uuid4(),
        page_id=uuid.uuid4(),
        document_index=0,
        page_index=0,
        content=content,
        char_count=len(content),
        content_hash="fake",
    )
    return chunk


def test_build_marker_annotated_context_assigns_sequential_markers() -> None:
    chunks = [_fake_chunk("First chunk."), _fake_chunk("Second chunk.")]

    text, marker_map = build_marker_annotated_context(chunks)

    assert "[C1] First chunk." in text
    assert "[C2] Second chunk." in text
    assert marker_map["C1"] == chunks[0].id
    assert marker_map["C2"] == chunks[1].id


def test_resolve_markers_returns_correct_chunk_ids() -> None:
    chunks = [_fake_chunk("A"), _fake_chunk("B"), _fake_chunk("C")]
    _, marker_map = build_marker_annotated_context(chunks)

    resolved, dropped = resolve_markers(["C1", "C3"], marker_map)

    assert resolved == [chunks[0].id, chunks[2].id]
    assert dropped == []


def test_resolve_markers_drops_hallucinated_marker_without_raising() -> None:
    chunks = [_fake_chunk("A"), _fake_chunk("B")]
    _, marker_map = build_marker_annotated_context(chunks)

    resolved, dropped = resolve_markers(["C1", "C99"], marker_map)

    assert resolved == [chunks[0].id]
    assert dropped == ["C99"]


def test_resolve_markers_with_no_valid_markers_returns_empty_resolved() -> None:
    _, marker_map = build_marker_annotated_context([_fake_chunk("A")])

    resolved, dropped = resolve_markers(["C5", "C6"], marker_map)

    assert resolved == []
    assert dropped == ["C5", "C6"]


def test_build_marker_annotated_context_respects_max_chars() -> None:
    chunks = [
        _fake_chunk("Alpha content."),
        _fake_chunk("Beta content."),
        _fake_chunk("Gamma content."),
        _fake_chunk("Delta content."),
    ]

    text, marker_map = build_marker_annotated_context(chunks, max_chars=60)

    assert "[C1] Alpha content." in text
    assert "[C2] Beta content." in text
    assert len(marker_map) < len(chunks)
    assert "[Source truncated:" in text


def test_build_marker_annotated_context_marker_map_only_contains_sent_chunks(
) -> None:
    chunks = [
        _fake_chunk("A"),
        _fake_chunk("B"),
        _fake_chunk("C"),
        _fake_chunk("D"),
    ]

    text, marker_map = build_marker_annotated_context(chunks, max_chars=20)

    assert all(marker in text for marker in ("C1", "C2"))
    assert all(chunk_marker not in marker_map for chunk_marker in ("C3", "C4"))


def test_build_marker_annotated_context_keeps_first_chunk_when_oversized(
) -> None:
    chunks = [_fake_chunk("A long chunk."), _fake_chunk("B chunk.")]

    text, marker_map = build_marker_annotated_context(chunks, max_chars=10)

    assert "[C1] A long chunk." in text
    assert marker_map == {"C1": chunks[0].id}


def test_build_marker_annotated_context_without_max_chars_is_unbounded() -> None:
    chunks = [_fake_chunk("A" * 200), _fake_chunk("B" * 200), _fake_chunk("C" * 200)]

    text, marker_map = build_marker_annotated_context(chunks)

    assert "[C1]" in text
    assert "[C2]" in text
    assert "[C3]" in text
    assert len(marker_map) == 3