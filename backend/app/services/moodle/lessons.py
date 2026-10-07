"""Build the Moodle lesson renderer from reviewer-approved lessons.

The Moodle mapper stays pure and generic: it receives a callable that
maps a weekly unit to its publishable lesson pages. This module builds
that callable from the lessons that a lecturer approved, using the
course-content renderer so the published page matches review.
"""

from __future__ import annotations

from collections.abc import Callable

from app.models.curriculum_unit import CurriculumUnit
from app.models.lesson import Lesson
from app.services.course_content.render import render_lesson_html
from app.services.moodle.mapper import MoodleLessonPlan


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
    collapsed to a single page (the first occurrence wins), so duplicated
    curriculum/lesson items never create duplicate Moodle Pages. Lesson
    identity is content-based: two genuinely different lessons that happen
    to share a title are both kept.
    """
    by_unit: dict[str, list[MoodleLessonPlan]] = {}
    for lesson in lessons:
        plans = by_unit.setdefault(str(lesson.curriculum_unit_id), [])
        plans.append(
            MoodleLessonPlan(
                name=lesson.title,
                content_html=render_lesson_html(lesson),
            )
        )

    def render_unit(unit: CurriculumUnit) -> list[MoodleLessonPlan]:
        plans = by_unit.get(str(unit.id), [])
        seen: set[str] = set()
        unique: list[MoodleLessonPlan] = []
        for plan in plans:
            if plan.content_html in seen:
                continue
            seen.add(plan.content_html)
            unique.append(plan)
        return unique

    return render_unit
