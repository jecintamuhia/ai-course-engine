"""Map a generated Curriculum into a Moodle course structure.

The mapper is pure (no I/O): it turns an in-memory Curriculum ORM graph
(units with their topic links) into plain data classes describing the
Moodle course and its weekly sections. Each week becomes exactly one
course section named after the week; lecturer-approved lessons render to
"Page" activities inside that section (no page repeats the week's
section name). The sync service then executes that plan through the
MoodleClient.

Every published lesson page embeds an identity marker (an HTML comment
carrying the lesson id) so lesson content can always be resolved back
to exactly the lesson it was generated from, even when two lessons
share a title. Section and lesson page names are disambiguated
course-wide so no two published records of the same kind share a title.
"""

from __future__ import annotations

import html
import re
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

from app.models.curriculum import Curriculum
from app.models.curriculum_unit import CurriculumUnit

MOODLE_DEFAULT_COURSE_NAME = "AI-Generated Course"

# Moodle field length limits (defensive only; Moodle enforces its own).
MAX_FULLNAME = 1334
MAX_SHORTNAME = 255
MAX_TITLE = 255

# A title shaped like a UUID is an internal identifier, not a human course
# name. Guard so an internal UUID can never surface as the Moodle course
# fullname or leak verbatim into the shortname.
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# The shortname is a title slug plus a short stable uniqueness suffix taken
# from the tail of the curriculum id; the slug is capped so the suffix (and
# the full shortname) always fits under Moodle's 255-char limit.
SHORTNAME_SLUG_BASE = 200

#: Identity marker embedded at the top of every published lesson page.
#: Moodle stores page content verbatim, so the marker survives the
#: round trip and lets the content services resolve a lesson to exactly
#: its own page even when two lessons share a title.
LESSON_ID_MARKER_TEMPLATE = "<!-- skillup-lesson-id: {lesson_id} -->"

_LESSON_ID_MARKER_PATTERN = re.compile(
    r"<!--\s*skillup-lesson-id:\s*"
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\s*-->",
)


def lesson_id_marker(lesson_id: uuid.UUID) -> str:
    """Return the identity marker HTML comment for a lesson id."""
    return LESSON_ID_MARKER_TEMPLATE.format(lesson_id=lesson_id)


def extract_lesson_id(content_html: str | None) -> uuid.UUID | None:
    """
    Return the lesson id a published page was generated from, if any.

    Returns None for pages published before markers were introduced, or
    when the content carries no recognizable marker.
    """
    if not content_html:
        return None
    match = _LESSON_ID_MARKER_PATTERN.search(content_html)
    if match is None:
        return None
    try:
        return uuid.UUID(match.group(1))
    except ValueError:  # pragma: no cover - regex already constrains the shape
        return None


def strip_lesson_id_marker(content_html: str) -> str:
    """Remove the identity marker (and the whitespace around it) from HTML."""
    return _LESSON_ID_MARKER_PATTERN.sub("", content_html).lstrip("\n")


@dataclass
class MoodleLessonPlan:
    """A single lecturer-approved lesson published as a page in a week."""

    name: str
    content_html: str
    lesson_id: uuid.UUID | None = None


@dataclass
class MoodleWeekPlan:
    """One week of the Moodle course: its section and lesson pages."""

    section_number: int
    section_name: str
    section_summary_html: str
    lessons: list[MoodleLessonPlan] = field(default_factory=list)


@dataclass
class MoodleCoursePlan:
    """A complete plan for a Moodle course derived from a curriculum."""

    fullname: str
    shortname: str
    summary_html: str
    idnumber: str
    weeks: list[MoodleWeekPlan] = field(default_factory=list)


def _clamp(value: str, max_length: int) -> str:
    """Truncate a string to a byte-/char-safe maximum length."""
    if len(value) <= max_length:
        return value
    return value[: max_length - 3].rstrip() + "..."


def _course_fullname(curriculum: Curriculum) -> str:
    title = (curriculum.title or "").strip()
    if not title or UUID_PATTERN.fullmatch(title):
        title = MOODLE_DEFAULT_COURSE_NAME
    return _clamp(title, MAX_FULLNAME)


def _slugify(value: str) -> str:
    """Lower-case, ASCII-safe hyphenated slug; deterministic."""
    slug = "".join(
        ch if ("a" <= ch <= "z" or "0" <= ch <= "9") else "-" for ch in value.lower()
    )
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def _course_shortname(curriculum: Curriculum, idnumber: str) -> str:
    """
    Deterministic, unique-safe shortname derived from the course title.

    The human-readable title is slugified and a short stable suffix taken
    from the tail of the curriculum id keeps the value unique when two
    curricula share a title, while remaining fully deterministic so
    re-publishing the same curriculum never renames it. The full UUID and
    the ``ai-ece-`` idnumber prefix never appear in the shortname; the
    UUID stays in ``idnumber`` (the internal identity). When the title
    yields no slug (or is itself a UUID), a neutral deterministic base is
    used instead.
    """
    raw = (curriculum.title or "").strip()
    if UUID_PATTERN.fullmatch(raw):
        raw = ""
    base = _slugify(raw)[:SHORTNAME_SLUG_BASE] or "course"
    suffix = idnumber.rsplit("-", 1)[-1][-8:]
    return _clamp(f"{base}-{suffix}", MAX_SHORTNAME)


def _topic_titles(unit: CurriculumUnit) -> list[str]:
    """Return the titles of the topics planned into a unit, in plan order."""
    return [link.topic.title for link in unit.topic_links if link.topic is not None]


def _course_summary(curriculum: Curriculum) -> str:
    weeks = [
        (
            f"<p><strong>Week {unit.week_number}:</strong> "
            f"{html.escape(', '.join(_topic_titles(unit))) or '&mdash;'}</p>"
        )
        for unit in curriculum.units
    ]
    count = len(curriculum.units)
    header = f"<p>{count} weekly units.</p>" if count else "<p>No weekly units yet.</p>"
    return header + "".join(weeks)


def _objectives_list(unit: CurriculumUnit) -> str:
    if not unit.learning_objectives:
        return "<p>This week has no explicit learning objectives.</p>"
    items = "".join(f"<li>{html.escape(obj)}</li>" for obj in unit.learning_objectives)
    return f"<ul>{items}</ul>"


def _section_summary(unit: CurriculumUnit) -> str:
    topics = _topic_titles(unit)
    topics_text = f"<p>Covers: {html.escape(', '.join(topics))}.</p>" if topics else ""
    return _clamp(
        f"{topics_text}"
        f"<p>By the end of this week, learners will be able to:</p>"
        f"{_objectives_list(unit)}",
        max_length=MAX_FULLNAME,
    )


def _section_name(unit: CurriculumUnit) -> str:
    """Name of the weekly section (the section itself represents the week)."""
    return _clamp(unit.title or f"Week {unit.week_number}", MAX_TITLE)


def _unique_section_names(
    units: list[CurriculumUnit],
) -> dict[uuid.UUID, str]:
    """
    Deterministic, course-wide unique names for the weekly sections.

    Moodle identifies sections by number, so duplicate section names are
    not ambiguous to the integration — but two weeks sharing a title is
    confusing for learners and lecturers browsing the published course.
    When a raw section name is used by more than one unit, every unit
    with that name is published as "<title> (Week N)"; week numbers are
    unique, so the suffixed names are unique too. A final guard appends
    a counter for the pathological case where even a disambiguated name
    collides with another unit's literal title.
    """
    raw_names = {unit.id: _section_name(unit) for unit in units}
    counts = Counter(raw_names.values())

    names: dict[uuid.UUID, str] = {}
    taken: set[str] = set()
    for unit in units:
        base = raw_names[unit.id]
        candidate = (
            base if counts[base] == 1 else f"{base} (Week {unit.week_number})"
        )
        name = _clamp(candidate, MAX_TITLE)
        counter = 2
        while name in taken:
            name = _clamp(f"{candidate} ({counter})", MAX_TITLE)
            counter += 1
        taken.add(name)
        names[unit.id] = name
    return names


def build_course_plan(
    curriculum: Curriculum,
    *,
    fullname_override: str | None = None,
    shortname_override: str | None = None,
    lesson_renderer: (Callable[[CurriculumUnit], list[MoodleLessonPlan]] | None) = None,
) -> MoodleCoursePlan:
    """
    Build the Moodle course plan for a curriculum.

    ``idnumber`` is derived deterministically from the curriculum id so
    the sync service can idempotently find-or-create the same course.

    ``fullname_override``/``shortname_override`` let callers customize
    the Moodle course names; each falls back to the derived value when
    blank.

    ``lesson_renderer`` optionally maps each weekly unit to the list of
    lecturer-approved lessons that should be published as additional
    page resources inside that week's section. When omitted (or when it
    returns an empty list) the plan contains no lesson pages, which is
    byte-identical to the pre-lesson plan format.
    """
    idnumber = f"ai-ece-{curriculum.id}"

    if fullname_override and fullname_override.strip():
        fullname = _clamp(fullname_override.strip(), MAX_FULLNAME)
    else:
        fullname = _course_fullname(curriculum)

    if shortname_override and shortname_override.strip():
        shortname = _clamp(shortname_override.strip(), MAX_SHORTNAME)
    else:
        shortname = _course_shortname(curriculum, idnumber)

    section_names = _unique_section_names(curriculum.units)
    weeks: list[MoodleWeekPlan] = []
    for unit in curriculum.units:
        lessons = lesson_renderer(unit) if lesson_renderer is not None else []
        named_lessons = [
            MoodleLessonPlan(
                name=_clamp(lesson.name, MAX_TITLE),
                content_html=lesson.content_html,
                lesson_id=lesson.lesson_id,
            )
            for lesson in lessons
        ]
        weeks.append(
            MoodleWeekPlan(
                section_number=unit.week_number,
                section_name=section_names[unit.id],
                section_summary_html=_section_summary(unit),
                lessons=named_lessons,
            )
        )

    return MoodleCoursePlan(
        fullname=fullname,
        shortname=shortname,
        summary_html=_course_summary(curriculum),
        idnumber=idnumber,
        weeks=weeks,
    )
