"""LLM-backed generators for course content blocks.

Each generator is a thin, testable wrapper over the LLMProvider interface;
all of them return validated Pydantic models (never raw prose) and raise
``AIProviderError``/``AIOutputValidationError`` so the orchestrator can
record per-component failures without fabricating content.
"""

from __future__ import annotations

from app.core.config import Settings
from app.core.exceptions import AIOutputValidationError
from app.schemas.ai_content import (
    ActivityGenerationResult,
    DiagramGenerationResult,
    GeneratedDiagram,
    KnowledgeCheckGenerationResult,
    LessonGenerationResult,
    ResourceCandidateResult,
)
from app.services.ai.base import LLMProvider
from app.services.course_content.prompts import (
    _ACTIVITY_SYSTEM_PROMPT,
    _DIAGRAM_SYSTEM_PROMPT,
    _KNOWLEDGE_CHECK_SYSTEM_PROMPT,
    _LESSON_SYSTEM_PROMPT,
    _RESOURCE_SYSTEM_PROMPT,
    build_activity_prompt,
    build_diagram_prompt,
    build_knowledge_check_prompt,
    build_lesson_prompt,
    build_resource_prompt,
)

_VALID_TEXT_KINDS = {"heading", "text", "example", "summary"}


async def generate_lesson(
    provider: LLMProvider,
    settings: Settings,
    *,
    topic_title: str,
    learning_objectives: list[str],
    week_title: str,
    annotated_text: str,
    max_objectives: int = 4,
    content_level: str | None = None,
    concept_names: list[str] | None = None,
    prerequisite_topics: list[str] | None = None,
    neighboring_topics: list[str] | None = None,
    week_number: int | None = None,
    lesson_position: int | None = None,
) -> LessonGenerationResult:
    """Generate a complete lesson for one topic grounded in annotated text."""
    result = await provider.complete_structured(
        system_prompt=_LESSON_SYSTEM_PROMPT,
        user_prompt=build_lesson_prompt(
            topic_title=topic_title,
            learning_objectives=learning_objectives,
            week_title=week_title,
            annotated_text=annotated_text,
            max_objectives=max_objectives,
            content_level=content_level,
            concept_names=concept_names,
            prerequisite_topics=prerequisite_topics,
            neighboring_topics=neighboring_topics,
            week_number=week_number,
            lesson_position=lesson_position,
        ),
        response_model=LessonGenerationResult,
        temperature=0.0,
        max_output_tokens=settings.content_max_tokens,
    )
    _validate_lesson_blocks(result)
    return result


async def generate_diagrams(
    provider: LLMProvider,
    settings: Settings,
    *,
    lesson_title: str,
    annotated_text: str,
    max_diagrams: int,
) -> DiagramGenerationResult:
    """Generate structured diagrams for a lesson."""
    result = await provider.complete_structured(
        system_prompt=_DIAGRAM_SYSTEM_PROMPT,
        user_prompt=build_diagram_prompt(
            lesson_title=lesson_title,
            annotated_text=annotated_text,
            max_diagrams=max_diagrams,
        ),
        response_model=DiagramGenerationResult,
        temperature=0.0,
        max_output_tokens=settings.content_max_tokens,
    )
    _validate_diagram_edges(result.diagrams)
    return result


async def generate_knowledge_checks(
    provider: LLMProvider,
    settings: Settings,
    *,
    lesson_title: str,
    annotated_text: str,
    max_checks: int,
) -> KnowledgeCheckGenerationResult:
    """Generate multiple-choice knowledge checks for a lesson."""
    return await provider.complete_structured(
        system_prompt=_KNOWLEDGE_CHECK_SYSTEM_PROMPT,
        user_prompt=build_knowledge_check_prompt(
            lesson_title=lesson_title,
            annotated_text=annotated_text,
            max_checks=max_checks,
        ),
        response_model=KnowledgeCheckGenerationResult,
        temperature=0.0,
        max_output_tokens=settings.content_max_tokens,
    )


async def generate_activities(
    provider: LLMProvider,
    settings: Settings,
    *,
    lesson_title: str,
    annotated_text: str,
    max_activities: int,
) -> ActivityGenerationResult:
    """Generate learning activities for a lesson."""
    return await provider.complete_structured(
        system_prompt=_ACTIVITY_SYSTEM_PROMPT,
        user_prompt=build_activity_prompt(
            lesson_title=lesson_title,
            annotated_text=annotated_text,
            max_activities=max_activities,
        ),
        response_model=ActivityGenerationResult,
        temperature=0.0,
        max_output_tokens=settings.content_max_tokens,
    )


async def propose_resource_candidates(
    provider: LLMProvider,
    settings: Settings,
    *,
    lesson_title: str,
    annotated_text: str,
    max_resources: int,
) -> ResourceCandidateResult:
    """Ask the LLM to propose external resource candidates (URLs unverified)."""
    return await provider.complete_structured(
        system_prompt=_RESOURCE_SYSTEM_PROMPT,
        user_prompt=build_resource_prompt(
            lesson_title=lesson_title,
            annotated_text=annotated_text,
            max_resources=max_resources,
        ),
        response_model=ResourceCandidateResult,
        temperature=0.0,
        max_output_tokens=settings.content_max_tokens,
    )


def _validate_lesson_blocks(result: LessonGenerationResult) -> None:
    """Reject lessons that do not conform to the block-kind vocabulary."""
    if not any(block.content.strip() for block in result.lesson.blocks):
        raise AIOutputValidationError(
            "Lesson generator returned no substantive lesson content."
        )
    for block in result.lesson.blocks:
        if block.kind not in _VALID_TEXT_KINDS:
            raise AIOutputValidationError(
                f"Lesson generator returned an unsupported block kind "
                f"{block.kind!r}. Expected one of {sorted(_VALID_TEXT_KINDS)}."
            )
        if block.kind == "heading" and block.heading_level not in (2, 3, None):
            raise AIOutputValidationError(
                "Heading blocks must declare heading_level 2 or 3."
            )


def _validate_diagram_edges(diagrams: list[GeneratedDiagram]) -> None:
    """Reject diagrams whose edges reference missing nodes."""
    for diagram in diagrams:
        node_ids = {node.id for node in diagram.nodes}
        for edge in diagram.edges:
            if edge.source not in node_ids or edge.target not in node_ids:
                raise AIOutputValidationError(
                    f"Diagram {diagram.title!r} references a missing node in "
                    f"edge {edge.source!r} -> {edge.target!r}."
                )
