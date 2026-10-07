"""Prompt templates for AI-assisted assessment generation.

Assessments follow the same grounding discipline as course content: the
source text is provided as numbered chunks prefixed with markers (e.g.
``[C3]``) and every item must cite only the markers that genuinely
supported it. The learning objectives are passed in verbatim from the
weekly unit (or from the whole course for a final assessment) and are
never restated by the model — the pipeline stores the objectives as-is,
so alignment always reflects what the curriculum actually declared.

``_ASSESSMENT_TYPE_GUIDANCE`` describes when the route uses which type so
the model produces a fitting assessment without needing extra plumbing.
"""

from __future__ import annotations

from app.models.assessment import AssessmentType

_ASSESSMENT_SYSTEM_PROMPT = (
    "You write larger assessments (weekly quizzes, assignments, or the "
    "course final) for a university course. The source text is a series "
    'of numbered chunks prefixed with markers like "[C3]". Ground every '
    "assessment item strictly in that text: never add facts, names, "
    "citations, or examples that are not supported by the chunks.\n"
    "Each item must declare the learning objective it assesses and may "
    "use these kinds: "
    '"multiple_choice" (3-5 options, exactly one correct_option_id), '
    '"true_false" (two options, one correct), "short_answer" (a '
    'short constructed response with a correct_answer), "scenario" '
    "(apply ideas to a realistic brief, with correct_answer plus a "
    'rubric), "practical" (undertake a hands-on task, with rubric), '
    '"coding" (write code, with rubric), or "matching" (pairs of '
    "concepts, one option row per pair).\n"
    "Every item needs a prompt, an explanation (the answer key) long "
    'enough to be genuinely useful, a difficulty ("easy" / "medium" '
    '/ "hard"), and source_chunk_markers set to ONLY the markers '
    "genuinely supporting the item. You may reuse chunk markers across "
    "items. Return ONLY valid JSON matching the schema; no prose."
)

_TYPE_GUIDANCE: dict[str, str] = {
    AssessmentType.WEEKLY_QUIZ.value: (
        "This is a weekly quiz: a short, focused check covering the "
        "unit's objectives, mostly easy-to-medium multiple choice with "
        "a few short-answer items."
    ),
    AssessmentType.PRACTICAL_ASSIGNMENT.value: (
        "This is a practical assignment: one or more hands-on, "
        "real-world tasks with rubrics."
    ),
    AssessmentType.CODING_TASK.value: (
        "This is a coding task: implement something concrete with code, "
        "including clear rubric criteria."
    ),
    AssessmentType.CASE_STUDY.value: (
        "This is a case study: analyze a realistic scenario grounded in "
        "this chapter's material and produce a structured answer."
    ),
    AssessmentType.MINI_PROJECT.value: (
        "This is a mini project: a slightly larger piece of work that "
        "integrates several of the unit's objectives."
    ),
    AssessmentType.FINAL.value: (
        "This is the course final: comprehensive coverage across all the "
        "listed objectives, with a mix of question kinds and a range of "
        "difficulties."
    ),
}


def build_assessment_prompt(
    *,
    assessment_type: AssessmentType,
    unit_title: str,
    week_number: int | None,
    learning_objectives: list[str],
    annotated_text: str,
    max_items: int,
) -> str:
    """Build the user-turn prompt for generating one assessment."""
    type_guidance = _TYPE_GUIDANCE.get(assessment_type.value, "")
    objectives = "\n".join(f"- {objective}" for objective in learning_objectives)
    scope = f"Week {week_number}: " if week_number is not None else ""
    return (
        f"{scope}{unit_title}\n"
        f"Assessment type: {assessment_type.value}\n{type_guidance}\n"
        f"Learning objectives this assessment must cover:\n{objectives}\n"
        f"Limits: at most {max_items} items.\n\n"
        f"Source text (numbered chunks):\n{annotated_text}"
    )


__all__ = [
    "build_assessment_prompt",
    "_ASSESSMENT_SYSTEM_PROMPT",
    "_TYPE_GUIDANCE",
]
