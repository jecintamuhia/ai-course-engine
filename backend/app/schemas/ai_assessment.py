"""Pydantic schemas for the LLM's structured assessment output.

These schemas describe the contract with the AI provider for generating a
complete assessment (a weekly quiz, assignment, or course final) from a
unit or course's learning objectives. The LLM is forbidden from
restating objectives — those come from the pipeline — and from
fabricating textbook facts; every item must cite only the
``source_chunk_markers`` that genuinely support it.

The item shape reuses ``AssessmentItem`` from ``app.schemas.assessment``
so the persisted ``items`` JSONB always matches the validated contract.
"""

from __future__ import annotations

from app.schemas.assessment import AssessmentItem
from pydantic import BaseModel, Field


class GeneratedAssessment(BaseModel):
    """A single complete assessment returned by the provider."""

    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=3000)
    estimated_minutes: int = Field(ge=0, le=10080)
    items: list[AssessmentItem] = Field(default_factory=list)

    @classmethod
    def validate_items(cls, items: list[AssessmentItem]) -> list[AssessmentItem]:
        """
        Structural validation of generated items.

        Several checks are intentionally strict because the result is
        persisted: correct_option_id must reference a real option for
        choice items; every item needs an explanation long enough to be a
        real answer key; at most 20 items are kept. Invalid output is
        rejected at the API/provider layer rather than silently persisted.
        """
        limited = items[:20]
        for item in limited:
            if item.correct_option_id is not None:
                option_ids = {option.id for option in item.options}
                if item.correct_option_id not in option_ids:
                    raise ValueError(
                        f"Assessment item {item.prompt[:60]!r} references a "
                        f"correct option {item.correct_option_id!r} that does "
                        "not exist among its options."
                    )
            if not item.explanation.strip():
                raise ValueError(
                    f"Assessment item {item.prompt[:60]!r} has no explanation "
                    "(answer key) — refusing to persist an unkeyed item."
                )
            if (
                item.kind in ("multiple_choice", "true_false", "matching")
                and not item.options
            ):
                raise ValueError(f"Choice item {item.prompt[:60]!r} has no options.")
        return limited
