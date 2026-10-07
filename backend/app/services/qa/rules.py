"""Pure content-QA rules for curriculum inspection.

Every rule is a pure function over a dataclass ``QAData`` bundle and
returns a list of ``QAFinding`` records (error / warning / info) with a
stable rule code. The service layer (:mod:`.service`) assembles
``QAData`` from the repositories, runs all rules, computes the verdict
and summary, and persists a ``QualityReport``.

Severity contract:
- ``error`` findings block lecturer approval and Moodle publishing;
- ``warning`` findings are surfaced to the lecturer but do not block;
- ``info`` findings are contextual counts the lecturer can review.

This mirrors the production rule: a successful pipeline with shallow
content, repeated topics, empty lessons, fake links, or UUID course
names must fail QA rather than being marked complete.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from app.models.assessment import Assessment
from app.models.chapter import Chapter
from app.models.course import Course
from app.models.curriculum import Curriculum
from app.models.dependency import Dependency
from app.models.lesson import Lesson
from app.models.lesson_content_block import LessonBlockType
from app.models.topic import Topic
from app.schemas.qa import QAFinding, QALocation
from app.services.topics.canonicalization import (
    canonical_key_for,
    normalize_title,
    title_similarity,
)

_PLACEHOLDER_PATTERN = re.compile(
    r"\b(todo|tbd|placeholder|lorem ipsum)\b"
    r"|\[(insert|placeholder|image|figure)[^]]*\]",
    re.IGNORECASE,
)
_GENERIC_LINK_HOSTS = {
    "example.com",
    "example.org",
    "example.net",
    "youtube.com/watch?v=xxxx",
}
_UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
_URL_SCHEME = re.compile(r"^https?://", re.IGNORECASE)
_YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{6,20}$")


@dataclass
class QAData:
    """The full inspection surface for one curriculum."""

    curriculum: Curriculum
    topics: list[Topic]
    lessons: list[Lesson]
    assessments: list[Assessment]
    chapters: list[Chapter]
    course: Course | None
    dependencies: list[Dependency] = field(default_factory=list)
    min_major_prose_chars: int = 600
    min_supporting_prose_chars: int = 200
    duplicate_title_similarity: float = 0.8

    importance_by_topic: dict[uuid.UUID, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.importance_by_topic = {
            topic.id: topic.importance for topic in self.topics if topic.importance
        }


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _loc(
    kind: str,
    name: str,
    obj_id: uuid.UUID | None = None,
    detail: str | None = None,
) -> QALocation:
    return QALocation(kind=kind, id=obj_id, title=name, detail=detail)


def _finding(
    rule: str, code: str, severity: str, message: str, locations: list[QALocation]
) -> QAFinding:
    return QAFinding(
        rule=rule,
        code=code,
        severity=severity,
        message=message,
        locations=locations,
    )


def _prose(block) -> str:
    """Render the searchable prose of a text-kind block."""
    if block.block_type == LessonBlockType.HEADING:
        return block.payload.get("text") or ""
    return block.payload.get("content") or ""


def _block_markers(block) -> list[str]:
    return list(block.payload.get("source_chunk_markers") or [])


def _url_text(block) -> str:
    return block.payload.get("url") or ""


# ---------------------------------------------------------------------------
# Rule 1: coverage
# ---------------------------------------------------------------------------


def check_coverage(data: QAData) -> list[QAFinding]:
    """Every curriculum topic accounted for; chapters represented."""
    findings: list[QAFinding] = []

    root_topics = [
        t
        for t in data.topics
        if t.parent_topic_id is None and t.duplicate_of_id is None
    ]
    if not root_topics:
        findings.append(
            _finding(
                "coverage",
                "no_canonical_topics",
                "error",
                "The document has no canonical (non-duplicate) topics; "
                "the curriculum is not grounded in the textbook.",
                [],
            )
        )
        return findings

    mapped_ids = {
        link.topic_id
        for unit in data.curriculum.units
        for link in unit.topic_links
        if link.topic_id is not None
    }

    lesson_topic_ids = {lesson.topic_id for lesson in data.lessons if lesson.topic_id}

    for topic in root_topics:
        mapped = topic.id in mapped_ids
        has_lesson = topic.id in lesson_topic_ids
        locs = [_loc("topic", topic.title, topic.id)]
        if not mapped and topic.importance in ("major", "major_foundational"):
            findings.append(
                _finding(
                    "coverage",
                    "major_topic_unmapped",
                    "error",
                    f"Major topic {topic.title!r} is not mapped to any weekly unit.",
                    locs,
                )
            )
        elif not mapped:
            findings.append(
                _finding(
                    "coverage",
                    "topic_not_mapped",
                    "info",
                    f"Topic {topic.title!r} is not mapped to any weekly unit.",
                    locs,
                )
            )
        elif mapped and not has_lesson:
            findings.append(
                _finding(
                    "coverage",
                    "topic_without_lesson",
                    "error",
                    f"Topic {topic.title!r} has no generated lesson yet.",
                    locs,
                )
            )

    # Orphan lessons: no topic linkage means provenance and coverage
    # cannot be verified, and the lesson cannot be traced to the source.
    for lesson in data.lessons:
        if lesson.topic_id is None:
            findings.append(
                _finding(
                    "coverage",
                    "lesson_without_topic",
                    "error",
                    f"Lesson {lesson.title!r} is not linked to any topic "
                    "(topic_id is null), so it cannot be traced to the "
                    "textbook. Regenerate or relink it before approval.",
                    [_loc("lesson", lesson.title, lesson.id)],
                )
            )

    # Zero-output weeks: a scheduled week with no lessons at all.
    weeks_with_lessons = {lesson.week_number for lesson in data.lessons}
    seen_units: set[int] = set()
    for unit in data.curriculum.units:
        week = unit.week_number
        if week in seen_units:
            continue
        seen_units.add(week)
        if week not in weeks_with_lessons:
            findings.append(
                _finding(
                    "coverage",
                    "week_without_lessons",
                    "error",
                    f"Week {week} has no generated lessons (zero output); "
                    "the curriculum is incomplete.",
                    [_loc("unit", unit.title, unit.id)],
                )
            )

    chapter_ids = {topic.chapter_id for topic in root_topics if topic.chapter_id}
    for chapter in data.chapters:
        if chapter.id in chapter_ids and not any(
            link.topic_id and _chapter_of_topic(data, link.topic_id) == chapter.id
            for unit in data.curriculum.units
            for link in unit.topic_links
        ):
            findings.append(
                _finding(
                    "coverage",
                    "chapter_uncovered",
                    "warning",
                    f"Chapter {chapter.title!r} has no topics mapped to the "
                    "curriculum.",
                    [_loc("chapter", chapter.title, chapter.id)],
                )
            )

    return findings


def _chapter_of_topic(data: QAData, topic_id: uuid.UUID) -> uuid.UUID | None:
    for topic in data.topics:
        if topic.id == topic_id:
            return topic.chapter_id
    return None


# ---------------------------------------------------------------------------
# Rule 2: duplication
# ---------------------------------------------------------------------------


def check_duplication(data: QAData) -> list[QAFinding]:
    """Duplicate topics, lessons, resources, and videos."""
    findings: list[QAFinding] = []
    had_canonicalization = any(t.canonical_key for t in data.topics)

    clusters: dict[str, list[Topic]] = {}
    for topic in (t for t in data.topics if t.parent_topic_id is None):
        clusters.setdefault(canonical_key_for(topic.title), []).append(topic)

    for key, members in clusters.items():
        if len(members) < 2 or not key:
            continue
        flagged = [m for m in members if m.duplicate_of_id is not None]
        if had_canonicalization and len(flagged) == len(members) - 1:
            findings.append(
                _finding(
                    "duplication",
                    "duplicate_topic_detected",
                    "info",
                    f"{len(members)} topics share canonical identity {key!r}; "
                    "duplicates are flagged and excluded from curricula.",
                    [_loc("topic", m.title, m.id) for m in members],
                )
            )
        else:
            findings.append(
                _finding(
                    "duplication",
                    "duplicate_topic_detected",
                    "error",
                    f"{len(members)} topics share canonical identity {key!r} and "
                    "were not deduplicated. Run canonicalization before approving.",
                    [_loc("topic", m.title, m.id) for m in members],
                )
            )

    # Near-duplicate titles: strong token overlap but distinct canonical
    # keys. Deterministic threshold; never auto-merged — surfaced as a
    # warning with an explanation the lecturer can adjudicate.
    root_for_similarity = [t for t in data.topics if t.parent_topic_id is None]
    threshold = data.duplicate_title_similarity
    for i, left in enumerate(root_for_similarity):
        for right in root_for_similarity[i + 1 :]:
            left_key = canonical_key_for(left.title)
            right_key = canonical_key_for(right.title)
            if not left_key or not right_key or left_key == right_key:
                continue
            similarity = title_similarity(left.title, right.title)
            if similarity < threshold:
                continue
            findings.append(
                _finding(
                    "duplication",
                    "near_duplicate_topic_detected",
                    "warning",
                    f"Topics {left.title!r} and {right.title!r} look like "
                    f"near-duplicates (similarity {similarity:.2f} >= "
                    f"threshold {threshold:.2f}) but their normalized keys "
                    f"differ ({left_key!r} vs {right_key!r}), so they were "
                    "not merged. Review and decide whether one is redundant.",
                    [
                        _loc("topic", left.title, left.id),
                        _loc("topic", right.title, right.id),
                    ],
                )
            )

    # Duplicate lessons within a unit (same normalized title) are accidental.
    lessons_by_unit: dict[uuid.UUID, list[Lesson]] = {}
    for lesson in data.lessons:
        lessons_by_unit.setdefault(lesson.curriculum_unit_id, []).append(lesson)

    for _unit_id, lessons in lessons_by_unit.items():
        by_title: dict[str, list[Lesson]] = {}
        for lesson in lessons:
            by_title.setdefault(normalize_title(lesson.title), []).append(lesson)
        for _key, group in by_title.items():
            if len(group) < 2:
                continue
            findings.append(
                _finding(
                    "duplication",
                    "duplicate_lesson_detected",
                    "error",
                    f"{len(group)} lessons in one week share the title "
                    f"{group[0].title!r}.",
                    [_loc("lesson", lesson.title, lesson.id) for lesson in group],
                )
            )

    # Same-title lessons across weeks are allowed (distinct content) but flagged.
    by_global_title: dict[str, list[Lesson]] = {}
    for lesson in data.lessons:
        by_global_title.setdefault(normalize_title(lesson.title), []).append(lesson)
    for _key, group in by_global_title.items():
        if len(group) >= 2 and len({lesson.week_number for lesson in group}) > 1:
            findings.append(
                _finding(
                    "duplication",
                    "repeated_lesson_title",
                    "warning",
                    f"Lesson title {group[0].title!r} appears across weeks; verify "
                    "each is genuinely distinct content.",
                    [_loc("lesson", lesson.title, lesson.id) for lesson in group],
                )
            )

    findings += _duplicate_link_findings(data)
    findings += _duplicate_video_findings(data)
    return findings


def _resource_blocks(lesson: Lesson):
    return [
        b
        for b in lesson.content_blocks
        if b.block_type == LessonBlockType.EXTERNAL_RESOURCE
    ]


def _duplicate_link_findings(data: QAData) -> list[QAFinding]:
    findings: list[QAFinding] = []
    seen: dict[str, list] = {}
    for lesson in data.lessons:
        for block in _resource_blocks(lesson):
            url = _url_text(block)
            if not url:
                continue
            seen.setdefault(url, []).append((lesson, block))
    for url, holders in seen.items():
        if len(holders) < 2:
            continue
        locs = [
            _loc("resource", block.title or url, block.id, lesson.title)
            for lesson, block in holders
        ]
        findings.append(
            _finding(
                "duplication",
                "duplicate_resource_detected",
                "warning",
                f"External resource {url!r} is attached to {len(holders)} lessons.",
                locs,
            )
        )
    return findings


def _video_blocks(lesson: Lesson):
    return [b for b in lesson.content_blocks if b.block_type == LessonBlockType.VIDEO]


def _duplicate_video_findings(data: QAData) -> list[QAFinding]:
    findings: list[QAFinding] = []
    seen: dict[str, list] = {}
    for lesson in data.lessons:
        for block in _video_blocks(lesson):
            video_id = block.payload.get("video_id") or ""
            if not video_id:
                continue
            seen.setdefault(video_id, []).append((lesson, block))
    for video_id, holders in seen.items():
        if len(holders) < 2:
            continue
        locs = [
            _loc("video", block.title or video_id, block.id, lesson.title)
            for lesson, block in holders
        ]
        findings.append(
            _finding(
                "duplication",
                "duplicate_video_detected",
                "warning",
                f"YouTube video {video_id!r} is attached to {len(holders)} lessons.",
                locs,
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Rule 3: provenance
# ---------------------------------------------------------------------------


def check_provenance(data: QAData) -> list[QAFinding]:
    """Textbook grounding, validated URLs, and real YouTube IDs."""
    findings: list[QAFinding] = []

    for lesson in data.lessons:
        marker_count = sum(len(_block_markers(b)) for b in lesson.content_blocks)
        if not lesson.content_blocks:
            findings.append(
                _finding(
                    "provenance",
                    "empty_lesson",
                    "error",
                    f"Lesson {lesson.title!r} has no content blocks.",
                    [_loc("lesson", lesson.title, lesson.id)],
                )
            )
        elif marker_count == 0:
            findings.append(
                _finding(
                    "provenance",
                    "missing_source_grounding",
                    "error",
                    f"Lesson {lesson.title!r} has content but no textbook source "
                    "references; grounding cannot be verified.",
                    [_loc("lesson", lesson.title, lesson.id)],
                )
            )

        for block in _resource_blocks(lesson):
            url = _url_text(block)
            if not url or not _URL_SCHEME.match(url):
                findings.append(
                    _finding(
                        "provenance",
                        "invalid_resource_url",
                        "error",
                        f"Resource {block.title or '(untitled)'!r} has an invalid URL.",
                        [_loc("resource", block.title or url, block.id, lesson.title)],
                    )
                )
            elif not (block.payload.get("validated_at") or ""):
                findings.append(
                    _finding(
                        "provenance",
                        "unverified_resource",
                        "warning",
                        f"Resource {block.title!r} has no validation timestamp.",
                        [_loc("resource", block.title or url, block.id, lesson.title)],
                    )
                )

        for block in _video_blocks(lesson):
            video_id = block.payload.get("video_id") or ""
            url = block.payload.get("url") or ""
            if not video_id or not _YOUTUBE_ID.match(video_id):
                findings.append(
                    _finding(
                        "provenance",
                        "invalid_video_id",
                        "error",
                        f"Video block {block.title or '(untitled)'!r} has an invalid "
                        "YouTube video id.",
                        [_loc("video", block.title or url, block.id, lesson.title)],
                    )
                )
            elif not url:
                findings.append(
                    _finding(
                        "provenance",
                        "invalid_video_url",
                        "error",
                        "Video block is missing its watch URL.",
                        [_loc("video", block.title or url, block.id, lesson.title)],
                    )
                )

    return findings


# ---------------------------------------------------------------------------
# Rule 4: quality / depth
# ---------------------------------------------------------------------------


def check_quality(data: QAData) -> list[QAFinding]:
    """Substantial lessons, no placeholders, no fake links."""
    findings: list[QAFinding] = []
    for lesson in data.lessons:
        combined = " ".join(_prose(b) for b in lesson.content_blocks)

        importance = _importance_of(data, lesson)
        minimum = (
            data.min_major_prose_chars
            if importance in ("major", "major_foundational")
            else data.min_supporting_prose_chars
        )
        if len(combined.strip()) < minimum:
            severity = (
                "error" if importance in ("major", "major_foundational") else "warning"
            )
            findings.append(
                _finding(
                    "quality",
                    "shallow_lesson",
                    severity,
                    f"Lesson {lesson.title!r} ({importance or 'supporting'}) has only "
                    f"{len(combined)} characters of content (minimum {minimum}).",
                    [_loc("lesson", lesson.title, lesson.id)],
                )
            )

        if _PLACEHOLDER_PATTERN.search(combined):
            findings.append(
                _finding(
                    "quality",
                    "placeholder_content",
                    "error",
                    f"Lesson {lesson.title!r} contains placeholder/TODO text that must "
                    "be resolved before approval.",
                    [_loc("lesson", lesson.title, lesson.id)],
                )
            )

        for host in _GENERIC_LINK_HOSTS:
            if host in combined.lower():
                findings.append(
                    _finding(
                        "quality",
                        "fake_link",
                        "error",
                        f"Lesson {lesson.title!r} contains a placeholder link "
                        f"({host!r}) that should not be published.",
                        [_loc("lesson", lesson.title, lesson.id)],
                    )
                )
                break

        for block in lesson.content_blocks:
            if not _is_leaf(block) and not _prose(block).strip():
                findings.append(
                    _finding(
                        "quality",
                        "empty_content_block",
                        "info",
                        "Content block has empty text.",
                        [
                            _loc(
                                "block",
                                block.title or block.block_type.value,
                                block.id,
                                lesson.title,
                            )
                        ],
                    )
                )

    findings += _check_knowledge_unit_utilization(data)
    return findings


def _concept_has_ku(concept) -> bool:
    return bool(
        (concept.definition and concept.definition.strip())
        or concept.terminology
        or concept.procedures
        or concept.formulas
        or concept.worked_examples
        or concept.exercises
    )


def _check_knowledge_unit_utilization(data: QAData) -> list[QAFinding]:
    """Structured knowledge units must exist and reach the lessons."""
    findings: list[QAFinding] = []

    topics_with_ku: list[Topic] = []
    topics_with_terms: dict[uuid.UUID, list[str]] = {}
    for topic in data.topics:
        concepts = topic.concepts or []
        if any(_concept_has_ku(c) for c in concepts):
            topics_with_ku.append(topic)
        terms = [t for c in concepts for t in (c.terminology or [])]
        if terms:
            topics_with_terms[topic.id] = terms

    if data.topics and not topics_with_ku:
        findings.append(
            _finding(
                "quality",
                "knowledge_units_not_extracted",
                "warning",
                "No topic carries structured knowledge units "
                "(definitions/terminology/procedures/formulas); re-run topic "
                "extraction so lessons can be built from them.",
                [],
            )
        )
        return findings

    for lesson in data.lessons:
        if not lesson.topic_id or lesson.topic_id not in topics_with_terms:
            continue
        terms = topics_with_terms[lesson.topic_id]
        if len(terms) < 3:
            continue
        combined = " ".join(_prose(b) for b in lesson.content_blocks).lower()
        if not combined.strip():
            continue
        hits = [t for t in terms if t.lower() in combined]
        if not hits:
            findings.append(
                _finding(
                    "quality",
                    "knowledge_units_unused",
                    "warning",
                    f"Lesson {lesson.title!r} does not use any of the "
                    f"{len(terms)} terminology terms extracted for its topic; "
                    "the structured knowledge units were not carried into "
                    "the lesson.",
                    [_loc("lesson", lesson.title, lesson.id)],
                )
            )
    return findings


def _is_leaf(block) -> bool:
    return block.block_type not in (
        LessonBlockType.TEXT,
        LessonBlockType.HEADING,
        LessonBlockType.EXAMPLE,
        LessonBlockType.SUMMARY,
    )


def _importance_of(data: QAData, lesson: Lesson) -> str | None:
    return data.importance_by_topic.get(lesson.topic_id) if lesson.topic_id else None


# ---------------------------------------------------------------------------
# Rule 5: learning design
# ---------------------------------------------------------------------------


def check_learning_design(data: QAData) -> list[QAFinding]:
    """Objectives ↔ lessons ↔ activities ↔ knowledge checks ↔ assessments."""
    findings: list[QAFinding] = []

    for lesson in data.lessons:
        if not lesson.learning_objectives:
            findings.append(
                _finding(
                    "learning_design",
                    "lesson_without_objectives",
                    "warning",
                    f"Lesson {lesson.title!r} has no learning objectives.",
                    [_loc("lesson", lesson.title, lesson.id)],
                )
            )
        if _importance_of(data, lesson) in ("major", "major_foundational"):
            has_knowledge_check = any(
                b.block_type == LessonBlockType.KNOWLEDGE_CHECK
                for b in lesson.content_blocks
            )
            has_activity = any(
                b.block_type == LessonBlockType.ACTIVITY for b in lesson.content_blocks
            )
            has_diagram = any(
                b.block_type == LessonBlockType.DIAGRAM for b in lesson.content_blocks
            )
            if not has_knowledge_check:
                findings.append(
                    _finding(
                        "learning_design",
                        "major_topic_missing_knowledge_check",
                        "warning",
                        f"Major lesson {lesson.title!r} has no knowledge check.",
                        [_loc("lesson", lesson.title, lesson.id)],
                    )
                )
            if not has_activity:
                findings.append(
                    _finding(
                        "learning_design",
                        "major_topic_missing_activity",
                        "warning",
                        f"Major lesson {lesson.title!r} has no learning activity.",
                        [_loc("lesson", lesson.title, lesson.id)],
                    )
                )
            if not has_diagram:
                findings.append(
                    _finding(
                        "learning_design",
                        "major_topic_missing_diagram",
                        "info",
                        f"Major lesson {lesson.title!r} has no diagram; consider a "
                        "visual explanation.",
                        [_loc("lesson", lesson.title, lesson.id)],
                    )
                )

    if data.lessons and not data.assessments:
        findings.append(
            _finding(
                "learning_design",
                "course_without_assessment",
                "warning",
                "The course has generated lessons but no assessments yet; "
                "assessments should map to learning outcomes.",
                [],
            )
        )

    for assessment in data.assessments:
        if not assessment.learning_objectives:
            findings.append(
                _finding(
                    "learning_design",
                    "assessment_without_objectives",
                    "error",
                    f"Assessment {assessment.title!r} covers no learning objectives.",
                    [_loc("assessment", assessment.title, assessment.id)],
                )
            )
        if not assessment.items:
            findings.append(
                _finding(
                    "learning_design",
                    "assessment_without_items",
                    "error",
                    f"Assessment {assessment.title!r} has no items.",
                    [_loc("assessment", assessment.title, assessment.id)],
                )
            )

    findings += _check_week_workload_balance(data)
    findings += _check_progression(data)
    findings += _check_prerequisite_ordering(data)
    return findings


def _check_week_workload_balance(data: QAData) -> list[QAFinding]:
    """Weekly lesson workload must stay within the curriculum's limits."""
    findings: list[QAFinding] = []
    max_weekly = data.curriculum.max_weekly_workload_minutes or 0
    if max_weekly <= 0 or not data.lessons:
        return findings

    workload_by_week: dict[int, int] = {}
    for lesson in data.lessons:
        workload_by_week[lesson.week_number] = (
            workload_by_week.get(lesson.week_number, 0)
            + (lesson.estimated_workload_minutes or 0)
        )

    for week, total in sorted(workload_by_week.items()):
        if total > max_weekly:
            findings.append(
                _finding(
                    "learning_design",
                    "week_workload_exceeded",
                    "warning",
                    f"Week {week} totals {total} minutes of lesson workload, "
                    f"above the weekly maximum of {max_weekly} minutes.",
                    [_loc("unit", f"Week {week}", None)],
                )
            )
        elif total < max_weekly // 2:
            findings.append(
                _finding(
                    "learning_design",
                    "week_workload_underfilled",
                    "info",
                    f"Week {week} totals only {total} minutes of lesson "
                    f"workload, less than half the {max_weekly}-minute weekly "
                    "budget.",
                    [_loc("unit", f"Week {week}", None)],
                )
            )
    return findings


def _check_progression(data: QAData) -> list[QAFinding]:
    """BASIC → INTERMEDIATE → ADVANCED must advance across weeks.

    Also reports topics that never received a computed content level
    (P1.2 pass not run), since progression cannot be judged for them.
    """
    findings: list[QAFinding] = []
    root_topics = [
        t
        for t in data.topics
        if t.parent_topic_id is None and t.duplicate_of_id is None
    ]
    if not root_topics:
        return findings

    topic_week: dict[uuid.UUID, int] = {
        link.topic_id: unit.week_number
        for unit in data.curriculum.units
        for link in unit.topic_links
        if link.topic_id is not None
    }

    level_first_week: dict[str, int] = {}
    missing_levels: list[Topic] = []
    for topic in root_topics:
        if topic.id not in topic_week:
            continue
        level = topic.content_level
        if level is None:
            missing_levels.append(topic)
            continue
        level_name = (
            level.value if hasattr(level, "value") else str(level)
        ).upper()
        week = topic_week[topic.id]
        if level_name not in level_first_week or week < level_first_week[level_name]:
            level_first_week[level_name] = week

    if missing_levels:
        findings.append(
            _finding(
                "learning_design",
                "content_level_missing",
                "warning",
                f"{len(missing_levels)} scheduled topic(s) have no computed "
                "content level; run the content-level pass so progression "
                "can be verified.",
                [_loc("topic", t.title, t.id) for t in missing_levels],
            )
        )

    order = ["BASIC", "INTERMEDIATE", "ADVANCED"]
    present = [
        (name, level_first_week[name]) for name in order if name in level_first_week
    ]
    for index, (name, week) in enumerate(present):
        earlier = [(n, w) for n, w in present[:index] if w > week]
        for earlier_name, earlier_week in earlier:
            findings.append(
                _finding(
                    "learning_design",
                    "progression_inverted",
                    "warning",
                    f"{name} topics start in week {week} but {earlier_name} "
                    f"topics start later, in week {earlier_week}; the "
                    "BASIC → INTERMEDIATE → ADVANCED progression is inverted.",
                    [],
                )
            )
    return findings


def _check_prerequisite_ordering(data: QAData) -> list[QAFinding]:
    """Check order using only resolved prerequisite edges."""
    findings: list[QAFinding] = []
    topic_week: dict[uuid.UUID, int] = {
        link.topic_id: unit.week_number
        for unit in data.curriculum.units
        for link in unit.topic_links
        if link.topic_id is not None
    }
    topics_by_id = {
        topic.id: topic
        for topic in data.topics
        if topic.parent_topic_id is None and topic.duplicate_of_id is None
    }
    for edge in data.dependencies:
        topic = topics_by_id.get(edge.topic_id)
        target = topics_by_id.get(edge.depends_on_topic_id)
        if topic is None or target is None:
            continue
        week = topic_week.get(topic.id)
        target_week = topic_week.get(target.id)
        if week is None or target_week is None or target_week <= week:
            continue
        findings.append(
            _finding(
                "learning_design",
                "prerequisite_ordering",
                "warning",
                f"Topic {topic.title!r} (week {week}) depends on "
                f"{target.title!r}, scheduled in a later week ({target_week}).",
                [
                    _loc("topic", topic.title, topic.id),
                    _loc("topic", target.title, target.id),
                ],
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Rule 6: Moodle readiness
# ---------------------------------------------------------------------------


def check_moodle(data: QAData) -> list[QAFinding]:
    """Course naming, no week-page duplication, clean hierarchy."""
    findings: list[QAFinding] = []

    title = data.curriculum.title
    if _UUID_PATTERN.search(title or ""):
        findings.append(
            _finding(
                "moodle",
                "uuid_course_name",
                "error",
                "The curriculum title looks like a UUID; lesson/course display "
                "would expose internal identity as a course name.",
                [_loc("curriculum", title, data.curriculum.id)],
            )
        )

    if data.course is not None:
        for field_name, value in (
            ("fullname", data.course.fullname),
            ("shortname", data.course.shortname),
        ):
            if _UUID_PATTERN.search(value or "") or "ai-ece-" in (value or ""):
                findings.append(
                    _finding(
                        "moodle",
                        "uuid_course_name",
                        "error",
                        f"The Moodle course {field_name} exposes the internal "
                        "idnumber/UUID as a visible name.",
                        [_loc("course", value, data.course.id)],
                    )
                )

    for unit in data.curriculum.units:
        unit_key = normalize_title(unit.title)
        for lesson in data.lessons:
            if (
                lesson.curriculum_unit_id == unit.id
                and normalize_title(lesson.title) == unit_key
            ):
                findings.append(
                    _finding(
                        "moodle",
                        "duplicate_week_page",
                        "error",
                        f"A lesson page repeats week {unit.week_number} section name "
                        f"({unit.title!r}); the week is the section, so this is a "
                        "duplicate week page.",
                        [
                            _loc("unit", unit.title, unit.id),
                            _loc("lesson", lesson.title, lesson.id),
                        ],
                    )
                )

    return findings


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

_RULES = (
    ("coverage", check_coverage),
    ("duplication", check_duplication),
    ("provenance", check_provenance),
    ("quality", check_quality),
    ("learning_design", check_learning_design),
    ("moodle", check_moodle),
)


def run_all_rules(data: QAData) -> dict[str, list[QAFinding]]:
    """Run every QA rule domain and return {domain: findings}."""
    return {name: rule(data) for name, rule in _RULES}
