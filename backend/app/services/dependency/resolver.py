"""Resolves AI-extracted prerequisite title references into real
topic-to-topic dependency edges."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.models.topic import Topic
from app.services.dependency.graph import Edges


@dataclass(frozen=True)
class UnresolvedPrerequisite:
    """A prerequisite title that could not be resolved to exactly one topic."""

    topic_id: uuid.UUID
    topic_title: str
    prerequisite_title: str
    reason: str  # "not_found" | "ambiguous"


def _normalize_title(title: str) -> str:
    return title.strip().lower()


def _flatten_topics(topics: list[Topic]) -> list[Topic]:
    """Recursively flatten a topic tree (including subtopics) into a flat list."""
    flat: list[Topic] = []
    for topic in topics:
        flat.append(topic)
        flat.extend(_flatten_topics(topic.subtopics))
    return flat


def resolve_prerequisites(
    top_level_topics: list[Topic],
) -> tuple[Edges, list[UnresolvedPrerequisite]]:
    """
    Resolve every topic's prerequisite_titles against all topics in the
    document (flattened, including subtopics) by normalized title match.

    A prerequisite title matching zero topics is reported as
    "not_found". A prerequisite title matching more than one topic
    (e.g. two chapters each producing a topic titled "Introduction") is
    reported as "ambiguous" and no edge is created for it — no edge is
    ever created from a guess.
    """
    all_topics = _flatten_topics(top_level_topics)

    title_index: dict[str, list[uuid.UUID]] = {}
    for topic in all_topics:
        title_index.setdefault(_normalize_title(topic.title), []).append(topic.id)

    edges: Edges = {topic.id: set() for topic in all_topics}
    unresolved: list[UnresolvedPrerequisite] = []

    for topic in all_topics:
        for prerequisite_title in topic.prerequisite_titles:
            matches = title_index.get(_normalize_title(prerequisite_title), [])

            if len(matches) == 0:
                unresolved.append(
                    UnresolvedPrerequisite(
                        topic_id=topic.id,
                        topic_title=topic.title,
                        prerequisite_title=prerequisite_title,
                        reason="not_found",
                    )
                )
            elif len(matches) > 1:
                unresolved.append(
                    UnresolvedPrerequisite(
                        topic_id=topic.id,
                        topic_title=topic.title,
                        prerequisite_title=prerequisite_title,
                        reason="ambiguous",
                    )
                )
            else:
                edges.setdefault(topic.id, set()).add(matches[0])

    return edges, unresolved
