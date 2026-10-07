"""Topic canonicalization and deduplication.

Production requirement: the final course must not contain accidental
topic repetition. Topic extraction is per-chapter, so the same concept
(``Decision Trees`` / ``Decision tree`` / ``Decision Trees Algorithm``)
can be persisted multiple times. This module gives every topic a stable,
normalized identity (``canonical_key``) and merges *safe* exact
normalized matches into a canonical topic with aliases; near—duplicates
that cannot be safely merged are left intact and instead surfaced by the
content-QA pipeline for lecturer review (``duplicate_topic_detected``)
so genuinely different concepts are never collapsed.

Merge policy (conservative by design):
- only top-level topics (``parent_topic_id IS NULL``) participate;
- two titles merge only when their normalized keys are equal
  (case/punctuation/whitespace folding + safe plural folding);
- the canonical member is the one with the most source-chunk evidence
  (ties broken by reading order);
- every non-canonical member is flagged ``duplicate_of_id`` and its
  original title recorded as an alias — nothing is deleted.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.models.topic import Topic, TopicImportance

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}
_WORD_PATTERN = re.compile(r"[a-z0-9']+")
_PLURAL_IRREGULAR = {"basis", "analysis", "synthesis", "diagnosis", "crisis"}


def normalize_title(title: str) -> str:
    """
    Lightweight canonical title normalization used for both the
    canonical key and QA title-similarity checks.
    """
    text = unicodedata.normalize("NFKC", title).lower()
    words = [word for word in _WORD_PATTERN.findall(text) if word not in _STOPWORDS]
    return " ".join(words)


def _fold_plural(word: str) -> str:
    """Safely fold a trailing plural suffix off a word, when obvious."""
    if len(word) <= 4 or word in _PLURAL_IRREGULAR:
        return word
    if word.endswith("ies") and len(word) > 4:
        return f"{word[:-3]}y"
    if word.endswith("sses") or word.endswith("xes") or word.endswith("zes"):
        return word[:-2]
    if word.endswith("es") and len(word) > 4 and not word.endswith("ses"):
        return word[:-1]
    if word.endswith("s") and len(word) > 4 and not word.endswith("ss"):
        return word[:-1]
    return word


def canonical_key_for(title: str) -> str:
    """Return the deterministic canonical identity of a topic title."""
    folded = " ".join(_fold_plural(word) for word in normalize_title(title).split())
    return folded or normalize_title(title)


def title_similarity(left: str, right: str) -> float:
    """Jaccard similarity over normalized title tokens (0..1)."""
    left_tokens = set(normalize_title(left).split())
    right_tokens = set(normalize_title(right).split())
    if not left_tokens or not right_tokens:
        return 0.0
    union = len(left_tokens | right_tokens)
    if union == 0:
        return 0.0
    return len(left_tokens & right_tokens) / union


def classify_importance(topic: Topic) -> str:
    """
    Heuristic learning-design weight used to size lesson depth and to
    drive content-QA depth rules.

    Derived from deterministic signals only: difficulty, workload, and
    the number of extracted concepts. Documented as a heuristic — the
    lecturer can correct it in review; QA never silently trusts it.
    """
    is_root = topic.parent_topic_id is None
    concept_count = len(topic.concepts or [])
    workload = topic.estimated_workload_minutes or 0
    difficulty = topic.difficulty or 1

    if difficulty >= 4:
        return TopicImportance.ADVANCED.value

    if is_root:
        if difficulty <= 1 and workload >= 60:
            return TopicImportance.MAJOR_FOUNDATIONAL.value
        if workload >= 90 or concept_count >= 2:
            return TopicImportance.MAJOR.value
        if workload < 45:
            return TopicImportance.MINOR.value
        return TopicImportance.SUPPORTING.value

    return (
        TopicImportance.SUPPORTING.value
        if workload >= 45
        else TopicImportance.MINOR.value
    )


@dataclass
class CanonicalizationResult:
    """Outcome of a canonicalization pass over a document's topics."""

    topics_seen: int
    clusters: int
    duplicates_flagged: int
    aliases_created: int
    near_duplicates: list[tuple[str, str, float]]


def _evidence_size(topic: Topic) -> int:
    return len(topic.source_chunk_links or [])


def apply_canonicalization(topics: list[Topic]) -> CanonicalizationResult:
    """
    Persist canonical identity/aliases/dedup flags onto a flat list of
    session-attached Topic rows (no database writes happen here — the
    caller commits the session).

    Returns a CanonicalizationResult with counts plus any near-duplicate
    candidate pairs (similar, but not safely mergeable) that QA should
    surface.
    """
    result = CanonicalizationResult(
        topics_seen=len(topics),
        clusters=0,
        duplicates_flagged=0,
        aliases_created=0,
        near_duplicates=[],
    )

    root_topics = [t for t in topics if t.parent_topic_id is None]
    clusters: dict[str, list[Topic]] = {}

    for topic in root_topics:
        topic.importance = classify_importance(topic)
        key = canonical_key_for(topic.title)
        topic.canonical_key = key
        clusters.setdefault(key, []).append(topic)

    for subtopic in (t for t in topics if t.parent_topic_id is not None):
        subtopic.importance = classify_importance(subtopic)
        subtopic.canonical_key = canonical_key_for(subtopic.title)

    root_canonical_keys = [key for key in clusters if key]
    for key in root_canonical_keys:
        members = clusters[key]
        if len(members) < 2:
            members[0].aliases = []
            continue

        result.clusters += 1
        canonical = min(
            members,
            key=lambda topic: (-_evidence_size(topic), topic.order_index),
        )
        for member in members:
            if member is canonical:
                member.duplicate_of_id = None
                member.aliases = [
                    other.title for other in members if other is not canonical
                ]
            else:
                member.duplicate_of_id = canonical.id
                member.aliases = []
                result.duplicates_flagged += 1
        result.aliases_created += len(canonical.aliases)

    # Near-duplicate pairs that we deliberately do NOT merge (distinct
    # keys but strong token overlap) are reported for lecturer review.
    for i, left in enumerate(root_topics):
        for right in root_topics[i + 1 :]:
            similarity = title_similarity(left.title, right.title)
            if similarity >= 0.8 and left.canonical_key != right.canonical_key:
                result.near_duplicates.append(
                    (left.title, right.title, round(similarity, 3))
                )

    return result


def canonical_of(left: str, right: str) -> bool:
    """Return whether two normalized titles share a canonical key."""
    return canonical_key_for(left) == canonical_key_for(right)
