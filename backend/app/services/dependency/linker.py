"""Document-wide prerequisite linking.

Per-chapter extraction cannot name a cross-chapter prerequisite: the other
chapters' topics do not exist yet while it runs, so any cross-chapter title
it produced would be invented. The earlier attempt to solve this by handing
each chapter the document's chapter/section outline did not work — the model
cited chapter titles ("Chapter 1.2: Linux Fundamentals for Hosting
Administrators") while the resolver only indexes topic titles, so two thirds
of the references were discarded as unresolvable.

This module is the second pass. Once every chapter has been analyzed, the
whole document's real topic titles exist, so a single LLM call can be shown
all of them at once and asked which earlier topics each one genuinely
requires. Its output is then filtered deterministically: only titles that
match a real topic exactly are kept, only links pointing backwards in
reading order survive, and every rejection is reported rather than silently
dropped. No edge is ever created from a guess.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.models.topic import Topic
from app.schemas.ai_extraction import PrerequisiteLink
from app.services.dependency.graph import Edges


@dataclass(frozen=True)
class CatalogueEntry:
    """A topic as presented to the linking pass."""

    position: int
    topic_id: uuid.UUID
    title: str
    chapter_label: str


@dataclass(frozen=True)
class RejectedLink:
    """A link the model proposed that was refused, with the reason."""

    topic_title: str
    prerequisite_title: str
    reason: str


@dataclass
class LinkResolution:
    """Validated edges from the linking pass, plus what was refused."""

    edges: Edges = field(default_factory=dict)
    rejected: list[RejectedLink] = field(default_factory=list)


def _normalize_title(title: str) -> str:
    """
    Fold a title to its matching key.

    Only case and surrounding whitespace are ignored, so a title that
    genuinely differs ("DKIM" vs "DKIM Records") is a miss rather than a
    silent match on a guess.
    """
    return " ".join(title.split()).strip().lower()


def flatten_topics_in_reading_order(topics: list[Topic]) -> list[Topic]:
    """
    Flatten a topic tree (top-level topics plus subtopics) preserving
    reading order: each parent's own position first, then its subtopics
    in order, then the next parent.
    """
    flat: list[Topic] = []

    def walk(items: list[Topic]) -> None:
        for topic in items:
            flat.append(topic)
            walk(topic.subtopics)

    walk(topics)
    return flat


def build_catalogue(
    topics: list[Topic],
    chapter_labels: dict[uuid.UUID, str] | None = None,
) -> list[CatalogueEntry]:
    """
    Number every topic in reading order for presentation to the model.

    The number is what the model uses to reason about which topic is
    earlier, so it must be stable and match the order the resolver will
    enforce.
    """
    labels = chapter_labels or {}
    return [
        CatalogueEntry(
            position=index,
            topic_id=topic.id,
            title=topic.title,
            chapter_label=labels.get(
                topic.chapter_id, "Unassigned" if topic.chapter_id else ""
            ),
        )
        for index, topic in enumerate(topics, start=1)
    ]


def render_catalogue(entries: list[CatalogueEntry]) -> str:
    """Render the numbered catalogue as prompt text."""
    lines: list[str] = []

    for entry in entries:
        chapter = f" [{entry.chapter_label}]" if entry.chapter_label else ""
        lines.append(f"{entry.position}.{chapter} {entry.title}")

    return "\n".join(lines)


def resolve_links(
    links: list[PrerequisiteLink],
    entries: list[CatalogueEntry],
    *,
    max_prerequisites: int = 4,
) -> LinkResolution:
    """
    Turn proposed links into validated edges.

    A proposal is kept only when the topic and the prerequisite each match
    exactly one catalogue entry, the prerequisite is distinct, and it
    appears EARLIER in reading order. The earlier-only rule is enforced
    here rather than trusted from the model, and it also makes a cycle
    impossible within a single pass's output.
    """
    by_title: dict[str, list[CatalogueEntry]] = {}
    for entry in entries:
        by_title.setdefault(_normalize_title(entry.title), []).append(entry)

    resolution = LinkResolution(edges={entry.topic_id: set() for entry in entries})

    for link in links:
        subject_matches = by_title.get(_normalize_title(link.topic), [])

        if len(subject_matches) != 1:
            resolution.rejected.append(
                RejectedLink(
                    topic_title=link.topic,
                    prerequisite_title="",
                    reason=(
                        "subject_not_found"
                        if not subject_matches
                        else "subject_ambiguous"
                    ),
                )
            )
            continue

        subject = subject_matches[0]

        for prerequisite_title in link.prerequisites:
            matches = by_title.get(_normalize_title(prerequisite_title), [])

            if len(matches) != 1:
                resolution.rejected.append(
                    RejectedLink(
                        topic_title=subject.title,
                        prerequisite_title=prerequisite_title,
                        reason=(
                            "prerequisite_not_found"
                            if not matches
                            else "prerequisite_ambiguous"
                        ),
                    )
                )
                continue

            prerequisite = matches[0]

            if prerequisite.topic_id == subject.topic_id:
                resolution.rejected.append(
                    RejectedLink(
                        topic_title=subject.title,
                        prerequisite_title=prerequisite.title,
                        reason="self_reference",
                    )
                )
                continue

            if prerequisite.position >= subject.position:
                resolution.rejected.append(
                    RejectedLink(
                        topic_title=subject.title,
                        prerequisite_title=prerequisite.title,
                        reason="not_earlier",
                    )
                )
                continue

            current = resolution.edges.setdefault(subject.topic_id, set())

            if (
                len(current) >= max_prerequisites
                and prerequisite.topic_id not in current
            ):
                resolution.rejected.append(
                    RejectedLink(
                        topic_title=subject.title,
                        prerequisite_title=prerequisite.title,
                        reason="limit_exceeded",
                    )
                )
                continue

            current.add(prerequisite.topic_id)

    return resolution
