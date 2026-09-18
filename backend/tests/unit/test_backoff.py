"""Unit tests for exponential backoff calculation."""

from __future__ import annotations

from app.services.ingestion.job_queue import compute_backoff_seconds


def test_backoff_doubles_each_attempt() -> None:
    assert compute_backoff_seconds(1) == 2.0
    assert compute_backoff_seconds(2) == 4.0
    assert compute_backoff_seconds(3) == 8.0
    assert compute_backoff_seconds(4) == 16.0


def test_backoff_is_capped_at_max_seconds() -> None:
    assert compute_backoff_seconds(20) == 300.0


def test_backoff_respects_custom_base_and_cap() -> None:
    assert compute_backoff_seconds(1, base_seconds=1.0, max_seconds=5.0) == 1.0
    assert compute_backoff_seconds(3, base_seconds=1.0, max_seconds=5.0) == 4.0
    assert compute_backoff_seconds(5, base_seconds=1.0, max_seconds=5.0) == 5.0