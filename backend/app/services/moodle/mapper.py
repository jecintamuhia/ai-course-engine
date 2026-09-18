"""Map a generated Curriculum into a Moodle course structure.

The mapper is pure (no I/O): it turns an in-memory Curriculum ORM graph
(units with their topic links) into plain data classes describing the
Moodle course, its weekly sections, and the "Page" activities that will
be created inside each section. The sync service then executes that
plan through the MoodleClient.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field

from app.models.curriculum import Curriculum
from app.models.curriculum_unit import CurriculumUnit

MOODLE_DEFAULT_COURSE_NAME = "AI-Generated Course"

# Moodle field length limits (defensive only; Moodle enforces its own).
MAX_FULLNAME = 1334
MAX_SHORTNAME = 255
MAX_TITLE = 255


@dataclass
class MoodleWeekPlan:
    """One week of the Moodle course: its section and page content."""

    section_number: int
    section_name: str
    section_summary_html: str
    page_name: str
    page_content_html: str


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
    title = curriculum.title or MOODLE_DEFAULT_COURSE_NAME
    return _clamp(title, MAX_FULLNAME)


def _course_shortname(curriculum: Curriculum, idnumber: str) -> str:
    return _clamp(idnumber, MAX_SHORTNAME)


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


def _page_content(unit: CurriculumUnit) -> str:
    description = html.escape(unit.description) or (
        f"Week {unit.week_number} study plan."
    )
    return (
        f"<h3>{html.escape(unit.title)}</h3>"
        f"<p>{description}</p>"
        f"<h4>Learning objectives</h4>"
        f"{_objectives_list(unit)}"
    )


def _page_name(unit: CurriculumUnit) -> str:
    return _clamp(unit.title or f"Week {unit.week_number}", MAX_TITLE)


def build_course_plan(
    curriculum: Curriculum,
    *,
    fullname_override: str | None = None,
    shortname_override: str | None = None,
) -> MoodleCoursePlan:
    """
    Build the Moodle course plan for a curriculum.

    ``idnumber`` is derived deterministically from the curriculum id so
    the sync service can idempotently find-or-create the same course.

    ``fullname_override``/``shortname_override`` let callers customize
    the Moodle course names; each falls back to the derived value when
    blank.
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

    weeks: list[MoodleWeekPlan] = []
    for unit in curriculum.units:
        weeks.append(
            MoodleWeekPlan(
                section_number=unit.week_number,
                section_name=_page_name(unit),
                section_summary_html=_section_summary(unit),
                page_name=_page_name(unit),
                page_content_html=_page_content(unit),
            )
        )

    return MoodleCoursePlan(
        fullname=fullname,
        shortname=shortname,
        summary_html=_course_summary(curriculum),
        idnumber=idnumber,
        weeks=weeks,
    )
