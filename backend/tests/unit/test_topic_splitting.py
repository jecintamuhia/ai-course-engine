"""Tests for topic splitting detection.

The splitter must surface oversized topics with an explainable reason and
must refuse to perform unsafe graph surgery until explicitly implemented.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.topic_splitting.service import TopicSplitter


class _FakeResult:
    def __init__(self, rows) -> None:
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDb:
    """Emulates the real query's HAVING clause: only rows exceeding
    either threshold are returned to the caller."""

    def __init__(self, rows, *, max_concepts: int = 12, max_chunks: int = 8) -> None:
        self._rows = [
            r
            for r in rows
            if (r.concept_count or 0) > max_concepts
            or (r.chunk_count or 0) > max_chunks
        ]
        self.executed = 0

    def execute(self, stmt):
        self.executed += 1
        return _FakeResult(self._rows)


def _row(topic_id: str, concepts: int, chunks: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=topic_id, concept_count=concepts, chunk_count=chunks
    )


def test_returns_no_candidates_when_below_thresholds() -> None:
    db = _FakeDb([_row("t1", 3, 2)])
    splitter = TopicSplitter(max_concepts=12, max_chunks=8)

    assert splitter.find_candidates(db, "doc-1") == []
    assert db.executed == 1


def test_flags_oversized_concept_count_with_reason() -> None:
    db = _FakeDb([_row("t1", 20, 1)])
    splitter = TopicSplitter(max_concepts=12, max_chunks=8)

    candidates = splitter.find_candidates(db, "doc-1")

    assert len(candidates) == 1
    assert candidates[0].topic_id == "t1"
    assert "20 concepts" in candidates[0].reason


def test_flags_oversized_chunk_count_with_reason() -> None:
    db = _FakeDb([_row("t1", 1, 15)])
    splitter = TopicSplitter(max_concepts=12, max_chunks=8)

    candidates = splitter.find_candidates(db, "doc-1")

    assert len(candidates) == 1
    assert "15 chunks" in candidates[0].reason


def test_combines_reasons_when_both_thresholds_exceeded() -> None:
    db = _FakeDb([_row("t1", 30, 30)])
    splitter = TopicSplitter(max_concepts=12, max_chunks=8)

    candidates = splitter.find_candidates(db, "doc-1")

    assert "30 concepts" in candidates[0].reason
    assert "30 chunks" in candidates[0].reason


def test_orders_candidates_by_score_descending() -> None:
    db = _FakeDb(
        [
            _row("small", 13, 0),
            _row("large", 40, 25),
            _row("medium", 20, 5),
        ]
    )
    splitter = TopicSplitter(max_concepts=12, max_chunks=8)

    candidates = splitter.find_candidates(db, "doc-1")

    assert [c.topic_id for c in candidates] == ["large", "medium", "small"]
    assert candidates[0].score >= candidates[1].score >= candidates[2].score


def test_split_topic_is_refused_until_safe_implementation_lands() -> None:
    splitter = TopicSplitter()

    try:
        splitter.split_topic(_FakeDb([]), "t1")
    except NotImplementedError:
        pass
    else:  # pragma: no cover - guards accidental unsafe implementation
        raise AssertionError("split_topic must not run without graph-safety work")
