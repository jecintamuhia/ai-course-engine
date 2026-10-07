"""LLM-backed generators for assessments.

Each generator is a thin, testable wrapper over the LLMProvider
interface; output is validated before returning (never raw prose) and
structural failures raise ``AIProviderError``/``AIOutputValidationError``
so the orchestrator can record a per-assessment failure without
persisting partially-valid content.
"""

from __future__ import annotations

from app.core.config import Settings
from app.core.exceptions import AIOutputValidationError
from app.models.assessment import AssessmentType
from app.schemas.ai_assessment import GeneratedAssessment
from app.services.ai.base import LLMProvider
from app.services.assessment.prompts import (
    _ASSESSMENT_SYSTEM_PROMPT,
    build_assessment_prompt,
)


async def generate_assessment(
    provider: LLMProvider,
    settings: Settings,
    *,
    assessment_type: AssessmentType,
    unit_title: str,
    learning_objectives: list[str],
    annotated_text: str,
    week_number: int | None = None,
    max_items: int = 6,
) -> GeneratedAssessment:
    """Generate a complete assessment grounded in annotated source text."""
    result = await provider.complete_structured(
        system_prompt=_ASSESSMENT_SYSTEM_PROMPT,
        user_prompt=build_assessment_prompt(
            assessment_type=assessment_type,
            unit_title=unit_title,
            week_number=week_number,
            learning_objectives=learning_objectives,
            annotated_text=annotated_text,
            max_items=max_items,
        ),
        response_model=GeneratedAssessment,
        temperature=0.0,
        max_output_tokens=settings.content_max_tokens,
    )

    try:
        validated = GeneratedAssessment.validate_items(result.items)
    except ValueError as exc:
        raise AIOutputValidationError(
            f"Assessment generator returned structurally invalid items: {exc}"
        ) from exc

    if not validated:
        raise AIOutputValidationError(
            "Assessment generator returned no valid assessment items."
        )

    return result.model_copy(update={"items": validated})
