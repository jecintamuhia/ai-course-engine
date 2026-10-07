"""Unit tests for extraction result business-level validation."""

from __future__ import annotations

import pytest
from app.core.exceptions import AIOutputValidationError
from app.schemas.ai_extraction import (
    ExtractedConcept,
    ExtractedTopic,
    TopicExtractionResult,
)
from app.services.content_analysis.topic_extractor import (
    validate_extraction_result,
)


def _topic(**overrides) -> ExtractedTopic:
    defaults = {
        "title": "Some Topic",
        "learning_objectives": ["Do the thing"],
        "prerequisites": [],
        "concepts": [ExtractedConcept(name="X", description="Y")],
        "difficulty": 2,
        "estimated_workload_minutes": 30,
        "subtopics": [],
    }
    defaults.update(overrides)
    return ExtractedTopic(**defaults)


def test_valid_result_passes() -> None:
    result = TopicExtractionResult(topics=[_topic()])
    validate_extraction_result(result)


def test_empty_result_passes() -> None:
    validate_extraction_result(TopicExtractionResult(topics=[]))


def test_duplicate_top_level_titles_rejected() -> None:
    result = TopicExtractionResult(
        topics=[_topic(title="Same Title"), _topic(title="Same Title")]
    )

    with pytest.raises(AIOutputValidationError) as exc_info:
        validate_extraction_result(result)

    assert "Same Title" in exc_info.value.details["duplicate_titles"]


def test_duplicate_title_across_nesting_levels_rejected() -> None:
    child = _topic(title="Duplicate")
    parent = _topic(title="Duplicate", subtopics=[child])

    with pytest.raises(AIOutputValidationError):
        validate_extraction_result(TopicExtractionResult(topics=[parent]))


def test_topics_with_no_concepts_or_objectives_anywhere_rejected() -> None:
    empty_topic = _topic(learning_objectives=[], concepts=[], subtopics=[])

    with pytest.raises(AIOutputValidationError):
        validate_extraction_result(TopicExtractionResult(topics=[empty_topic]))


def test_topic_with_only_objectives_and_no_concepts_passes() -> None:
    topic = _topic(concepts=[], learning_objectives=["Some objective"])
    validate_extraction_result(TopicExtractionResult(topics=[topic]))


def test_nested_subtopic_with_concepts_satisfies_validation() -> None:
    child = _topic(
        title="Child", concepts=[ExtractedConcept(name="A", description="B")]
    )
    parent = _topic(
        title="Parent",
        concepts=[],
        learning_objectives=[],
        subtopics=[child],
    )

    validate_extraction_result(TopicExtractionResult(topics=[parent]))
