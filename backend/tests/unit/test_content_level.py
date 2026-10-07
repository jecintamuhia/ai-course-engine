from __future__ import annotations

from app.models.topic import ContentLevel
from app.services.content_level.service import compute_content_level


def test_basic() -> None:
    level = compute_content_level(
        depth=0, prereq_count=0, technical_terms=0, workload_minutes=10
    )
    assert level == ContentLevel.BASIC


def test_intermediate() -> None:
    level = compute_content_level(
        depth=2, prereq_count=0, technical_terms=0, workload_minutes=10
    )
    assert level == ContentLevel.INTERMEDIATE
    level = compute_content_level(
        depth=0, prereq_count=1, technical_terms=0, workload_minutes=10
    )
    assert level == ContentLevel.INTERMEDIATE
    level = compute_content_level(
        depth=0, prereq_count=0, technical_terms=2, workload_minutes=10
    )
    assert level == ContentLevel.INTERMEDIATE


def test_advanced() -> None:
    level = compute_content_level(
        depth=4, prereq_count=0, technical_terms=0, workload_minutes=10
    )
    assert level == ContentLevel.ADVANCED
    level = compute_content_level(
        depth=0, prereq_count=3, technical_terms=0, workload_minutes=10
    )
    assert level == ContentLevel.ADVANCED
