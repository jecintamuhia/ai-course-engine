"""Build the Moodle lesson renderer from reviewer-approved lessons.

The Moodle mapper stays pure and generic: it receives a callable that
maps a weekly unit to its publishable lesson pages. This module builds
that callable from the lessons that a lecturer approved, using the
course-content renderer so the published page matches review.

Two guarantees make lesson content reliably resolvable after publishing:

1. Every published page embeds an identity marker (an HTML comment with
   the lesson id) so the content services can resolve a lesson to
   exactly its own page even when two lessons share a title.
2. Page names are unique course-wide: distinct lessons that share a
   title are published under deterministic, meaningful disambiguated
   names ("<title> (Week N)", then "<title> (Week N, Lesson K)"), derived
   only from stable lesson data so re-publishing never renames them.

Lessons whose rendered content is byte-identical within one unit are
collapsed to a single page (the first occurrence wins), so duplicated
curriculum/lesson items never create duplicate Moodle Pages.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from app.models.curriculum_unit import CurriculumUnit
from app.models.lesson import Lesson
from app.services.course_content.render import render_lesson_html
from app.services.moodle.mapper import (
    MAX_TITLE,
    MoodleLessonPlan,
    lesson_id_marker,
)


def _clamp(value: str, max_length: int) -> str:
    """Truncate a string to a character-safe maximum length."""
    if len(value) <= max_length:
        return value
    return value[: max_length - 3].rstrip() + "..."


def _lesson_order_key(lesson: Lesson) -> tuple[int, int, str]:
    """Stable course-wide ordering: week, position, then id."""
    return (lesson.week_number, lesson.order_index, str(lesson.id))


def _resolve_survivors(
    lessons: list[Lesson],
) -> tuple[list[Lesson], dict[uuid.UUID, uuid.UUID], dict[uuid.UUID, str]]:
    """
    Determine which lessons get their own Moodle page.

    Within one unit, lessons whose rendered content is byte-identical
    collapse to the first of them: the returned ``survivors`` list holds
    the lessons that are published as pages, ``survivor_by_id`` maps
    every collapsed lesson to the survivor it resolves to, and
    ``rendered_by_id`` holds each lesson's rendered HTML.
    """
    ordered = sorted(lessons, key=_lesson_order_key)

    survivors: list[Lesson] = []
    survivor_by_id: dict[uuid.UUID, uuid.UUID] = {}
    survivor_for_content: dict[tuple[uuid.UUID, str], uuid.UUID] = {}
    rendered_by_id: dict[uuid.UUID, str] = {}

    for lesson in ordered:
        rendered = render_lesson_html(lesson)
        rendered_by_id[lesson.id] = rendered
        key = (lesson.curriculum_unit_id, rendered)
        if key in survivor_for_content:
            survivor_by_id[lesson.id] = survivor_for_content[key]
            continue
        survivor_for_content[key] = lesson.id
        survivors.append(lesson)

    return survivors, survivor_by_id, rendered_by_id


def _disambiguated_name(
    base: str,
    *,
    week_number: int,
    ordinal_in_week: int,
    taken: set[str],
) -> str:
    """
    Return a unique, meaningful Moodle page name for a lesson.

    The raw title is kept whenever it is not already taken by another
    lesson. Later distinct lessons that share the title are qualified
    with their week, and — when the title repeats within one week —
    with their position in that week, which keeps the name meaningful
    to a learner browsing the published course. A final counter guard
    covers pathological collisions.
    """
    name = _clamp(base, MAX_TITLE)
    if name in taken:
        name = _clamp(f"{base} (Week {week_number})", MAX_TITLE)
    if name in taken:
        name = _clamp(
            f"{base} (Week {week_number}, Lesson {ordinal_in_week})", MAX_TITLE
        )
    counter = 2
    while name in taken:
        name = _clamp(f"{base} ({counter})", MAX_TITLE)
        counter += 1
    taken.add(name)
    return name


def compute_lesson_page_names(lessons: list[Lesson]) -> dict[uuid.UUID, str]:
    """
    Deterministic, course-wide unique Moodle page names for lessons.

    Returns a mapping of lesson id to the page name that lesson is (or
    was) published under. Lessons collapsed at publish time because
    their rendered content is byte-identical to an earlier lesson in
    the same unit map to that lesson's page name, since both resolve to
    the same page and the same content.

    The input order does not matter: lessons are ordered by week, then
    position, then id, so the same set of lessons always yields the
    same names on every publish and on every lookup.
    """
    survivors, survivor_by_id, _rendered = _resolve_survivors(lessons)

    names: dict[uuid.UUID, str] = {}
    taken: set[str] = set()
    ordinal_by_unit: dict[uuid.UUID, int] = {}
    for lesson in survivors:
        ordinal = ordinal_by_unit.get(lesson.curriculum_unit_id, 0) + 1
        ordinal_by_unit[lesson.curriculum_unit_id] = ordinal
        names[lesson.id] = _disambiguated_name(
            lesson.title,
            week_number=lesson.week_number,
            ordinal_in_week=ordinal,
            taken=taken,
        )

    for lesson_id, survivor_id in survivor_by_id.items():
        names[lesson_id] = names[survivor_id]
    return names


def build_lesson_renderer(
    lessons: list[Lesson],
) -> Callable[[CurriculumUnit], list[MoodleLessonPlan]]:
    """
    Return a unit → lesson-pages callable for the Moodle mapper.

    ``lessons`` must already be the publishable (lecturer-APPROVED)
    lessons for the curriculum, with ``content_blocks`` eager-loaded so
    rendering performs no database access. Lessons are grouped by their
    weekly unit and ordered by week then lesson position.

    Within a unit, lessons whose rendered content is byte-identical are
    collapsed to a single page (the first occurrence wins), so
    duplicated curriculum/lesson items never create duplicate Moodle
    Pages. Genuinely different lessons that happen to share a title are
    both kept, published under unique disambiguated names (see
    ``compute_lesson_page_names``), and each page carries the lesson's
    identity marker.
    """
    survivors, _survivor_by_id, rendered_by_id = _resolve_survivors(lessons)
    names = compute_lesson_page_names(lessons)

    by_unit: dict[str, list[MoodleLessonPlan]] = {}
    for lesson in survivors:
        plans = by_unit.setdefault(str(lesson.curriculum_unit_id), [])
        plans.append(
            MoodleLessonPlan(
                name=names[lesson.id],
                lesson_id=lesson.id,
                content_html=(
                    f"{lesson_id_marker(lesson.id)}\n{rendered_by_id[lesson.id]}"
                ),
            )
        )

    def render_unit(unit: CurriculumUnit) -> list[MoodleLessonPlan]:
        return by_unit.get(str(unit.id), [])

    return render_unit
