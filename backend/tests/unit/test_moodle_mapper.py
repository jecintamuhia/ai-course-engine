"""Unit tests for the Moodle mapper (pure, no I/O)."""

import uuid
from unittest.mock import MagicMock

from app.services.moodle.mapper import (
    MOODLE_DEFAULT_COURSE_NAME,
    MoodleCoursePlan,
    MoodleLessonPlan,
    _clamp,
    _course_fullname,
    _course_shortname,
    _objectives_list,
    _section_summary,
    _topic_titles,
    build_course_plan,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_topic(title: str, objectives: list[str] | None = None):
    t = MagicMock()
    t.title = title
    t.learning_objectives = objectives or []
    return t


def _make_unit(
    *,
    week_number: int,
    title: str = "Test Week",
    description: str = "",
    objectives: list[str] | None = None,
    topic_titles: list[str] | None = None,
):
    u = MagicMock()
    u.week_number = week_number
    u.title = title
    u.description = description
    u.learning_objectives = objectives or []
    links = []
    for i, t_title in enumerate(topic_titles or []):
        link = MagicMock()
        link.topic = _make_topic(t_title)
        link.order_index = i
        links.append(link)
    u.topic_links = links
    return u


def _make_curriculum(
    *,
    id_: uuid.UUID | None = None,
    title: str = "Test Curriculum",
    units=None,
):
    c = MagicMock()
    c.id = id_ or uuid.uuid4()
    c.title = title
    c.units = units or []
    return c


# ---------------------------------------------------------------------------
# _clamp
# ---------------------------------------------------------------------------


class TestClamp:
    def test_short_string_unchanged(self):
        assert _clamp("hello", 10) == "hello"

    def test_long_string_truncated_with_ellipsis(self):
        result = _clamp("a" * 30, 20)
        assert len(result) == 20
        assert result.endswith("...")

    def test_exact_length_unchanged(self):
        s = "x" * 10
        assert _clamp(s, 10) == s


# ---------------------------------------------------------------------------
# _topic_titles
# ---------------------------------------------------------------------------


class TestTopicTitles:
    def test_returns_titles_in_order(self):
        u = _make_unit(week_number=1, topic_titles=["A", "B", "C"])
        assert _topic_titles(u) == ["A", "B", "C"]

    def test_empty_when_no_links(self):
        u = _make_unit(week_number=1, topic_titles=[])
        assert _topic_titles(u) == []


# ---------------------------------------------------------------------------
# _course_fullname / _course_shortname
# ---------------------------------------------------------------------------


class TestCourseFullname:
    def test_uses_curriculum_title(self):
        c = _make_curriculum(title="Machine Learning 101")
        assert _course_fullname(c) == "Machine Learning 101"

    def test_fallback_when_empty(self):
        c = _make_curriculum(title="")
        result = _course_fullname(c)
        assert result  # should not be empty
        assert "AI-Generated" in result


class TestCourseShortname:
    def test_derived_from_title_slug_plus_id_suffix(self):
        c = _make_curriculum(title="Machine Learning 101")
        idnumber = f"ai-ece-{c.id}"
        result = _course_shortname(c, idnumber)
        assert result.startswith("machine-learning-101-")
        assert result.endswith(idnumber.rsplit("-", 1)[-1][-8:])

    def test_never_leaks_full_curriculum_uuid(self):
        c = _make_curriculum(title="Data Analysis")
        idnumber = f"ai-ece-{c.id}"
        result = _course_shortname(c, idnumber)
        assert result != idnumber
        assert "ai-ece-" not in result
        assert str(c.id) not in result

    def test_uuid_titled_curriculum_uses_neutral_base(self):
        title_uuid = uuid.uuid4()
        c = _make_curriculum(title=str(title_uuid))
        result = _course_shortname(c, f"ai-ece-{c.id}")
        assert result.startswith("course-")
        assert str(title_uuid) not in result

    def test_deterministic_given_same_curriculum(self):
        c = _make_curriculum(title="Stable Title")
        idnumber = f"ai-ece-{c.id}"
        assert _course_shortname(c, idnumber) == _course_shortname(c, idnumber)

    def test_truncates_to_255(self):
        c = _make_curriculum()
        long_id = "x" * 300
        result = _course_shortname(c, long_id)
        assert len(result) <= 255


# ---------------------------------------------------------------------------
# _objectives_list / _section_summary
# ---------------------------------------------------------------------------


class TestObjectivesList:
    def test_html_list(self):
        u = _make_unit(week_number=1, objectives=["Learn A", "Learn B"])
        html = _objectives_list(u)
        assert "<li>Learn A</li>" in html
        assert "<li>Learn B</li>" in html

    def test_empty_when_no_objectives(self):
        u = _make_unit(week_number=1, objectives=[])
        result = _objectives_list(u)
        assert "no explicit learning objectives" in result


class TestSectionSummary:
    def test_contains_topic_names(self):
        u = _make_unit(
            week_number=1,
            topic_titles=["Intro", "Basics"],
            objectives=["Obj1"],
        )
        html = _section_summary(u)
        assert "Intro" in html
        assert "Basics" in html

    def test_escaping(self):
        u = _make_unit(
            week_number=1,
            topic_titles=["<script>evil</script>"],
            objectives=[],
        )
        html = _section_summary(u)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class TestNoWeeklyPage:
    def test_week_is_represented_by_section_only(self):
        u = _make_unit(
            week_number=1,
            title="Week 1 Topic",
            description="This week we study things.",
            objectives=["Obj1"],
        )
        c = _make_curriculum(title="Course", units=[u])
        plan = build_course_plan(c)
        week = plan.weeks[0]
        assert week.section_name == "Week 1 Topic"
        assert week.lessons == []


# ---------------------------------------------------------------------------
# build_course_plan
# ---------------------------------------------------------------------------


class TestBuildCoursePlan:
    def test_basic_plan(self):
        topic1 = MagicMock()
        topic1.title = "Regression"
        link1 = MagicMock()
        link1.topic = topic1
        link1.order_index = 0

        u1 = MagicMock()
        u1.week_number = 1
        u1.title = "Intro"
        u1.description = "Week 1 desc"
        u1.learning_objectives = ["Understand regression"]
        u1.topic_links = [link1]

        c = _make_curriculum(title="ML Course", units=[u1])
        plan = build_course_plan(c)

        assert isinstance(plan, MoodleCoursePlan)
        assert plan.fullname == "ML Course"
        assert plan.idnumber == f"ai-ece-{c.id}"
        assert len(plan.weeks) == 1

        week = plan.weeks[0]
        assert week.section_number == 1
        assert week.section_name == "Intro"
        assert "Regression" in week.section_summary_html
        assert week.lessons == []

    def test_multiple_weeks(self):
        units = []
        for i in range(1, 4):
            u = MagicMock()
            u.week_number = i
            u.title = f"Week {i}"
            u.description = f"Desc {i}"
            u.learning_objectives = [f"Learn {i}"]
            link = MagicMock()
            link.topic = MagicMock(title=f"Topic {i}")
            link.order_index = 0
            u.topic_links = [link]
            units.append(u)

        c = _make_curriculum(title="Course", units=units)
        plan = build_course_plan(c)

        assert len(plan.weeks) == 3
        assert [w.section_number for w in plan.weeks] == [1, 2, 3]

    def test_escaping_in_plan(self):
        u = MagicMock()
        u.week_number = 1
        u.title = "XSS <b>alert</b>"
        u.description = "Desc"
        u.learning_objectives = ["<script>"]
        u.topic_links = []

        c = _make_curriculum(title="Course", units=[u])
        plan = build_course_plan(c)

        for week in plan.weeks:
            assert "<script>" not in week.section_summary_html
            assert week.lessons == []


class TestBuildCoursePlanLessons:
    def make_unit(self, week_number=1):
        u = MagicMock()
        u.week_number = week_number
        u.title = f"Week {week_number}"
        u.description = f"Desc {week_number}"
        u.learning_objectives = []
        u.topic_links = []
        return u

    def test_no_lesson_renderer_keeps_weeks_lesson_free(self):
        u = self.make_unit()
        c = _make_curriculum(title="Course", units=[u])
        plan = build_course_plan(c)
        assert plan.weeks[0].lessons == []

    def test_lesson_renderer_populates_week_lessons(self):
        u = self.make_unit()
        c = _make_curriculum(title="Course", units=[u])

        def renderer(unit):
            assert unit is u
            return [
                MoodleLessonPlan(
                    name=f"{unit.title} Lesson", content_html="<p>Lesson</p>"
                )
            ]

        plan = build_course_plan(c, lesson_renderer=renderer)
        lessons = plan.weeks[0].lessons
        assert len(lessons) == 1
        assert lessons[0].name == "Week 1 Lesson"
        assert lessons[0].content_html == "<p>Lesson</p>"

    def test_lesson_names_are_length_clamped(self):
        u = self.make_unit()
        c = _make_curriculum(title="Course", units=[u])

        def renderer(unit):
            return [MoodleLessonPlan(name="x" * 500, content_html="<p>c</p>")]

        plan = build_course_plan(c, lesson_renderer=renderer)
        assert len(plan.weeks[0].lessons[0].name) <= 255

    def test_empty_renderer_result_leaves_lesson_page_empty(self):
        u = self.make_unit()
        c = _make_curriculum(title="Course", units=[u])
        plan = build_course_plan(c, lesson_renderer=lambda unit: [])
        assert plan.weeks[0].lessons == []


class TestCoursePlanRegression:
    def test_sixteen_week_curriculum_maps_to_sixteen_sections(self):
        units = []
        for i in range(1, 17):
            u = MagicMock()
            u.week_number = i
            u.title = f"Week {i}"
            u.description = f"Desc {i}"
            u.learning_objectives = [f"Learn {i}"]
            u.topic_links = []
            units.append(u)

        c = _make_curriculum(title="Full Course", units=units)
        plan = build_course_plan(c)

        assert len(plan.weeks) == 16
        assert [w.section_number for w in plan.weeks] == list(range(1, 17))

    def test_each_week_maps_to_exactly_one_section(self):
        units = []
        for i in range(1, 5):
            u = MagicMock()
            u.week_number = i
            u.title = f"Week {i}"
            u.description = "Desc"
            u.learning_objectives = []
            u.topic_links = []
            units.append(u)

        c = _make_curriculum(title="Course", units=units)
        plan = build_course_plan(c)

        numbers = [w.section_number for w in plan.weeks]
        assert numbers == [1, 2, 3, 4]
        assert len(numbers) == len(set(numbers))

    def test_week_yields_no_dedicated_page_without_renderer(self):
        u = MagicMock()
        u.week_number = 7
        u.title = "Advanced Topics"
        u.description = "Desc"
        u.learning_objectives = []
        u.topic_links = []

        c = _make_curriculum(title="Course", units=[u])
        plan = build_course_plan(c)
        week = plan.weeks[0]

        assert week.section_name == "Advanced Topics"
        assert week.lessons == []
        assert all(lesson.name != week.section_name for lesson in week.lessons)

    def test_fullname_and_shortname_never_contain_curriculum_uuid(self):
        c = _make_curriculum(title="Human Course Name")
        plan = build_course_plan(c)

        assert plan.fullname == "Human Course Name"
        assert str(c.id) not in plan.fullname
        assert str(c.id) not in plan.shortname
        assert plan.idnumber == f"ai-ece-{c.id}"

    def test_uuid_titled_curriculum_uses_default_fullname(self):
        title_uuid = uuid.uuid4()
        c = _make_curriculum(title=str(title_uuid))
        plan = build_course_plan(c)

        assert plan.fullname == MOODLE_DEFAULT_COURSE_NAME
        assert str(title_uuid) not in plan.fullname
        assert str(title_uuid) not in plan.shortname
        assert plan.idnumber == f"ai-ece-{c.id}"
