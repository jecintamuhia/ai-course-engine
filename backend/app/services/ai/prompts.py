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
JSON object with required fields. Include only what is actually present \
in the source material; omit empty fields:
  {"name": "Concise concept name (under 10 words)",
   "description": "One-sentence description under 20 words.",
   "definition": "Precise definition if stated (optional)",
   "terminology": ["key terms mentioned", ...],
   "procedures": ["step-by-step procedures if present", ...],
   "formulas": ["formulas/equations if present", ...],
   "worked_examples": [{"title": "...", "content": "..."}, ...],
   "exercises": [{"title": "...", "description": "..."}, ...],
   "misconceptions": ["common mistakes if identified", ...],
   "provenance": [{"source": "chunk marker or location", "note": "..."}, ...]}
- "prerequisites": titles ONLY. A prerequisite is an earlier topic in \
THIS chapter that a learner must understand first. Copy its title exactly \
as you wrote it. Base this on real structural dependency (a later topic \
that applies, extends, or assumes an earlier one) — not only on explicit \
sentences like "as discussed earlier". Never invent a title, and never \
list a topic that comes later in reading order. Do NOT try to reference \
topics from other chapters: a separate document-wide pass links \
cross-chapter prerequisites once every topic title is known.
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
    """Build the user-turn prompt for extracting topics from one chapter.

    Cross-chapter prerequisites are deliberately not in scope here: the
    other chapters' topic titles do not exist yet while this call runs, so
    any cross-chapter name the model produced would be a guess. They are
    resolved by the document-wide linking pass instead
    (``build_prerequisite_linking_user_prompt``).
    """
    limits = (
        f"Limits: at most {max_topics} top-level topics; per topic at "
        f"most {max_objectives} learning objectives, at most {max_concepts} "
        f"concepts, and at most {max_prerequisites} prerequisites.\n"
    )

    return (
        f"Chapter: {chapter_title}\n"
        f"{limits}\n"
        f"Chapter text (numbered chunks):\n{chapter_text}"
    )


PREREQUISITE_LINKING_SYSTEM_PROMPT = """\
You are given the complete, ordered list of topics for a textbook, \
numbered in reading order. Decide which EARLIER topics a learner must \
understand before a given topic.

For each entry that genuinely has cross-topic prerequisites, emit:
  {"topic": "<exact title from the list>",
   "prerequisites": ["<exact title from the list>", ...]}

Rules:
- Copy titles EXACTLY as they appear in the list, character for \
character. A title that is not in the list is discarded, so a near-miss \
is worse than omitting the link.
- "prerequisites" must contain only topics with a SMALLER number than \
"topic". Never link a later topic as a prerequisite of an earlier one.
- Link a topic only when the dependency is real: the later topic applies, \
extends, assumes, or is unintelligible without the earlier one. \
Terminology recaps are enough. Shared subject matter is NOT.
- Do not link a topic to its own immediate neighbour merely because \
they are adjacent; adjacency is not dependency.
- Prefer the most specific earlier topic that actually carries the \
required knowledge over a broad chapter-level topic.
- Emit nothing for topics with no genuine prerequisite. An empty list is \
correct and expected for most foundational topics.
- At most 4 prerequisites per topic.

Return ONLY valid JSON matching the supplied schema. No prose, no \
explanations, no reasoning.
"""


def build_prerequisite_linking_user_prompt(
    *,
    topic_catalogue: str,
    max_prerequisites: int = 4,
) -> str:
    """Build the user-turn prompt for the document-wide linking pass.

    ``topic_catalogue`` is the numbered, reading-order list of every
    topic in the document (see dependency.linker.build_topic_catalogue).
    The numbering is what the model uses to tell earlier from later, and
    the exact titles are what the resolver matches on.
    """
    return (
        f"Topics in reading order (topic number | chapter | title):\n"
        f"{topic_catalogue}\n\n"
        f"At most {max_prerequisites} prerequisites per topic. "
        f"Emit an entry only for topics with a genuine earlier dependency."
    )
