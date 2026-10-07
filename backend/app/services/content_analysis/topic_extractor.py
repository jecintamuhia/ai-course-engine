"""AI-assisted topic/concept extraction for a single chapter's text."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.exceptions import AIOutputValidationError
from app.schemas.ai_extraction import ExtractedTopic, TopicExtractionResult
from app.services.ai.base import LLMProvider
from app.services.ai.prompts import (
    TOPIC_EXTRACTION_SYSTEM_PROMPT,
    build_topic_extraction_user_prompt,
)


def _collect_titles(topics: list[ExtractedTopic]) -> list[str]:
    """Recursively collect every topic/subtopic title in the result."""
    titles: list[str] = []
    for topic in topics:
        titles.append(topic.title)
        titles.extend(_collect_titles(topic.subtopics))
    return titles


def validate_extraction_result(result: TopicExtractionResult) -> None:
    """
    Business-level validation beyond Pydantic's schema conformance.

    Raises AIOutputValidationError on duplicate topic titles within the
    same result (ambiguous for downstream prerequisite resolution) or
    on a result with topics but zero concepts and zero learning
    objectives anywhere (very likely a low-quality extraction rather
    than genuinely content-free source material).
    """
    all_titles = _collect_titles(result.topics)

    duplicates = {title for title in all_titles if all_titles.count(title) > 1}
    if duplicates:
        raise AIOutputValidationError(
            "Extraction result contains duplicate topic titles.",
            details={"duplicate_titles": sorted(duplicates)},
        )

    if result.topics:
        has_any_concept = any(_has_any_concept(topic) for topic in result.topics)
        has_any_objective = any(_has_any_objective(topic) for topic in result.topics)

        if not has_any_concept and not has_any_objective:
            raise AIOutputValidationError(
                "Extraction produced topics with no concepts or "
                "learning objectives anywhere in the result.",
            )


def _has_any_concept(topic: ExtractedTopic) -> bool:
    if topic.concepts:
        return True
    return any(_has_any_concept(sub) for sub in topic.subtopics)


def _has_any_objective(topic: ExtractedTopic) -> bool:
    if topic.learning_objectives:
        return True
    return any(_has_any_objective(sub) for sub in topic.subtopics)


async def extract_topics_for_chapter(
    llm_provider: LLMProvider,
    *,
    chapter_title: str,
    chapter_text: str,
) -> TopicExtractionResult:
    """
    Extract topics/subtopics/concepts for one chapter's text.

    ``chapter_text`` is expected to be marker-annotated (see
    chunk_context.build_marker_annotated_context) so the model can cite
    which chunks support each topic.

    Cross-chapter prerequisites are out of scope for this call. It runs
    once per chapter, so the other chapters' topic titles do not exist yet
    and any cross-chapter name it emitted would be invented rather than
    observed. Those links are made by the document-wide linking pass
    (dependency.linking_service), which sees every real title at once.

    Returns a validated TopicExtractionResult. Raises AIProviderError
    (from the provider) or AIOutputValidationError (from business-level
    validation) — never returns an unvalidated or partially-valid result.
    """
    settings = get_settings()

    result = await llm_provider.complete_structured(
        system_prompt=TOPIC_EXTRACTION_SYSTEM_PROMPT,
        user_prompt=build_topic_extraction_user_prompt(
            chapter_title=chapter_title,
            chapter_text=chapter_text,
            max_topics=settings.ai_extract_max_topics,
            max_objectives=settings.ai_extract_max_objectives,
            max_concepts=settings.ai_extract_max_concepts,
            max_prerequisites=settings.ai_extract_max_prerequisites,
        ),
        response_model=TopicExtractionResult,
        temperature=settings.ai_extract_temperature,
        max_output_tokens=settings.ai_extract_max_tokens,
    )

    validate_extraction_result(result)

    return result
