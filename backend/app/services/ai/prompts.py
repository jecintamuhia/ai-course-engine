"""Prompt templates for AI-assisted content analysis."""

from __future__ import annotations

TOPIC_EXTRACTION_SYSTEM_PROMPT = """\
Extract the educational structure of this textbook chapter. The text \
is a series of numbered chunks prefixed with markers like "[C3]".

For each topic (nest genuinely subordinate material as subtopics):
- "title": short, exact, concise.
- "learning_objectives": 1-3 concrete "students will be able to..." \
statements.
- "concepts": the concepts the topic introduces. Each concept MUST be a \
JSON object with exactly two string fields, never a plain string:
  {"name": "Concise concept name (under 10 words)",
   "description": "One-sentence description under 20 words."}
- "prerequisites": titles ONLY, and only when the text explicitly \
relies on an earlier topic of this chapter. Never invent.
- "difficulty": 1 (introductory) to 5 (advanced).
- "estimated_workload_minutes": realistic for a typical learner, based \
on the depth and length present.
- "source_chunk_markers": ONLY the markers (e.g. "C1", "C3") that \
genuinely support this topic. Never invent or over-include.
- "subtopics": nest subordinate material, do not flatten it.

Return ONLY valid JSON matching the supplied schema. No prose, no \
explanations, no reasoning. Extract only content actually present in \
the text; do not pad or invent. Respect the numeric limits in the \
chapter message. If the text covers very little, return few or zero \
topics.
"""


def build_topic_extraction_user_prompt(
    *,
    chapter_title: str,
    chapter_text: str,
    max_topics: int = 10,
    max_objectives: int = 4,
    max_concepts: int = 4,
    max_prerequisites: int = 3,
) -> str:
    """Build the user-turn prompt for extracting topics from one chapter."""
    return (
        f"Chapter: {chapter_title}\n"
        f"Limits: at most {max_topics} top-level topics; per topic at "
        f"most {max_objectives} learning objectives, at most {max_concepts} "
        f"concepts, and at most {max_prerequisites} prerequisites.\n\n"
        f"Chapter text (numbered chunks):\n{chapter_text}"
    )