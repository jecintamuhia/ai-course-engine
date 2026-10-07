"""Tests for document-wide prerequisite linking and edge validation."""

from __future__ import annotations

import uuid

from app.schemas.ai_extraction import PrerequisiteLink
from app.services.dependency.linker import (
    build_catalogue,
    flatten_topics_in_reading_order,
    render_catalogue,
    resolve_links,
)


class _FakeTopic:
    """Minimal topic stand-in for the linker, which only reads these."""

    def __init__(self, title, *, chapter_id=None, subtopics=None):
        self.id = uuid.uuid4()
        self.title = title
        self.chapter_id = chapter_id
        self.subtopics = subtopics or []


def _catalogue(*titles):
    return build_catalogue([_FakeTopic(t) for t in titles])


def test_catalogue_numbers_topics_in_reading_order() -> None:
    entries = _catalogue("First", "Second", "Third")

    assert [e.position for e in entries] == [1, 2, 3]
    assert [e.title for e in entries] == ["First", "Second", "Third"]


def test_catalogue_includes_chapter_labels_when_known() -> None:
    chapter_id = uuid.uuid4()
    topics = [_FakeTopic("A", chapter_id=chapter_id), _FakeTopic("B")]

    entries = build_catalogue(topics, {chapter_id: "1.2"})

    rendered = render_catalogue(entries)
    assert "[1.2] A" in rendered
    assert "2. B" in rendered


def test_subtopics_are_flattened_after_their_parent() -> None:
    child = _FakeTopic("Child")
    parent = _FakeTopic("Parent", subtopics=[child])
    other = _FakeTopic("Other")

    flat = flatten_topics_in_reading_order([parent, other])

    assert [t.title for t in flat] == ["Parent", "Child", "Other"]


def test_link_to_earlier_topic_is_kept() -> None:
    entries = _catalogue("DNS Basics", "DKIM Signing")

    resolution = resolve_links(
        [PrerequisiteLink(topic="DKIM Signing", prerequisites=["DNS Basics"])],
        entries,
    )

    subject = entries[1]
    prerequisite = entries[0]
    assert resolution.edges[subject.topic_id] == {prerequisite.topic_id}
    assert resolution.rejected == []


def test_link_to_later_topic_is_rejected() -> None:
    """A prerequisite must never point forward in reading order."""
    entries = _catalogue("DNS Basics", "DKIM Signing")

    resolution = resolve_links(
        [PrerequisiteLink(topic="DNS Basics", prerequisites=["DKIM Signing"])],
        entries,
    )

    assert resolution.edges[entries[0].topic_id] == set()
    assert resolution.rejected[0].reason == "not_earlier"


def test_unknown_prerequisite_title_is_rejected_not_guessed() -> None:
    entries = _catalogue("DNS Basics", "DKIM Signing")

    resolution = resolve_links(
        [PrerequisiteLink(topic="DKIM Signing", prerequisites=["DNS Record Types"])],
        entries,
    )

    assert resolution.edges[entries[1].topic_id] == set()
    assert resolution.rejected[0].reason == "prerequisite_not_found"


def test_near_miss_title_is_not_treated_as_a_match() -> None:
    """A title that differs is a miss, not a fuzzy match."""
    entries = _catalogue("DKIM Signing", "DKIM Signing Configuration")

    resolution = resolve_links(
        [
            PrerequisiteLink(
                topic="DKIM Signing Configuration",
                prerequisites=["DKIM Signing Keys"],
            )
        ],
        entries,
    )

    assert resolution.edges[entries[1].topic_id] == set()
    assert resolution.rejected[0].reason == "prerequisite_not_found"


def test_self_reference_is_rejected() -> None:
    entries = _catalogue("Only Topic")

    resolution = resolve_links(
        [PrerequisiteLink(topic="Only Topic", prerequisites=["only topic"])],
        entries,
    )

    assert resolution.edges[entries[0].topic_id] == set()
    assert resolution.rejected[0].reason == "self_reference"


def test_ambiguous_subject_title_is_rejected() -> None:
    entries = _catalogue("Introduction", "Middle", "Introduction")

    resolution = resolve_links(
        [PrerequisiteLink(topic="Introduction", prerequisites=["Middle"])],
        entries,
    )

    assert resolution.rejected[0].reason == "subject_ambiguous"


def test_prerequisite_limit_is_enforced() -> None:
    titles = ["A", "B", "C", "D", "E", "Target"]
    entries = _catalogue(*titles)

    resolution = resolve_links(
        [PrerequisiteLink(topic="Target", prerequisites=["A", "B", "C", "D", "E"])],
        entries,
        max_prerequisites=2,
    )

    assert len(resolution.edges[entries[-1].topic_id]) == 2
    assert any(r.reason == "limit_exceeded" for r in resolution.rejected)


def test_repeated_links_are_idempotent() -> None:
    entries = _catalogue("A", "B")

    resolution = resolve_links(
        [
            PrerequisiteLink(topic="B", prerequisites=["A"]),
            PrerequisiteLink(topic="B", prerequisites=["A"]),
        ],
        entries,
    )

    assert resolution.edges[entries[1].topic_id] == {entries[0].topic_id}


def test_titles_are_matched_ignoring_case_and_whitespace() -> None:
    entries = _catalogue("DNS Basics")

    resolution = resolve_links(
        [PrerequisiteLink(topic="  dns   BASICS ", prerequisites=[])],
        entries,
    )

    assert resolution.rejected == []
