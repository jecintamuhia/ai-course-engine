"""Unit tests for semantic text chunking."""

from __future__ import annotations

from app.services.ingestion.chunker import chunk_text


def test_merges_short_paragraphs_into_one_chunk() -> None:
    text = "Short paragraph one.\n\nShort paragraph two.\n\nShort paragraph three."

    chunks = chunk_text(text, target_size=100, max_size=200, min_size=20)

    assert len(chunks) == 1
    assert "Short paragraph one." in chunks[0].content
    assert "Short paragraph three." in chunks[0].content


def test_splits_oversized_paragraph_by_sentence_within_max_size() -> None:
    text = "Sentence one is here. " * 30

    chunks = chunk_text(text, target_size=200, max_size=300, min_size=50)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.char_count <= 320


def test_merges_tiny_trailing_chunk_into_previous() -> None:
    text = ("A" * 150) + "\n\n" + ("B" * 20)

    chunks = chunk_text(text, target_size=100, max_size=200, min_size=50)

    assert len(chunks) == 1
    assert "A" * 150 in chunks[0].content
    assert "B" * 20 in chunks[0].content


def test_empty_text_returns_no_chunks() -> None:
    assert chunk_text("   ") == []


def test_char_count_matches_content_length() -> None:
    text = "Some paragraph content here."
    chunks = chunk_text(text, target_size=10, max_size=1000, min_size=1)

    for chunk in chunks:
        assert chunk.char_count == len(chunk.content)


def test_respects_custom_size_bounds() -> None:
    text = "\n\n".join(f"Paragraph number {i} with some content." for i in range(20))

    chunks = chunk_text(text, target_size=50, max_size=80, min_size=10)

    for chunk in chunks[:-1]:
        assert chunk.char_count <= 80
