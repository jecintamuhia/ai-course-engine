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
    extract_lesson_id,
    lesson_id_marker,
    strip_lesson_id_marker,
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


class TestLessonIdMarker:
    def test_marker_round_trip(self):
        lesson_id = uuid.uuid4()
        marker = lesson_id_marker(lesson_id)
        content = f"{marker}\n<h3>Title</h3><p>Body</p>"
        assert extract_lesson_id(content) == lesson_id
        assert strip_lesson_id_marker(content) == "<h3>Title</h3><p>Body</p>"

    def test_marker_survives_surrounding_whitespace(self):
        lesson_id = uuid.uuid4()
        content = f"prefix <!-- skillup-lesson-id: {lesson_id} --> suffix"
        assert extract_lesson_id(content) == lesson_id

    def test_no_marker_yields_none(self):
        assert extract_lesson_id("<h3>No marker here</h3>") is None
        assert extract_lesson_id(None) is None
        assert extract_lesson_id("") is None

    def test_garbage_marker_yields_none(self):
        assert extract_lesson_id("<!-- skillup-lesson-id: not-a-uuid -->") is None

    def test_strip_without_marker_is_noop(self):
        content = "<h3>Title</h3>"
        assert strip_lesson_id_marker(content) == content


class TestSectionNameDisambiguation:
    def test_duplicate_unit_titles_get_week_suffixed_names(self):
        units = [
            _make_unit(week_number=1, title="Applications"),
            _make_unit(week_number=2, title="Applications"),
        ]
        c = _make_curriculum(title="Course", units=units)
        plan = build_course_plan(c)

        names = [w.section_name for w in plan.weeks]
        assert names == ["Applications (Week 1)", "Applications (Week 2)"]
        assert len(set(names)) == 2

    def test_unique_unit_titles_keep_raw_names(self):
        units = [
            _make_unit(week_number=1, title="Basics"),
            _make_unit(week_number=2, title="Advanced"),
        ]
        c = _make_curriculum(title="Course", units=units)
        plan = build_course_plan(c)

        assert [w.section_name for w in plan.weeks] == ["Basics", "Advanced"]

    def test_literal_suffix_title_collision_gets_counter_guard(self):
        # A unit literally titled "Applications (Week 2)" would collide
        # with the disambiguated name of the week-2 "Applications" unit.
        units = [
            _make_unit(week_number=1, title="Applications"),
            _make_unit(week_number=2, title="Applications"),
            _make_unit(week_number=3, title="Applications (Week 2)"),
        ]
        c = _make_curriculum(title="Course", units=units)
        plan = build_course_plan(c)

        names = [w.section_name for w in plan.weeks]
        assert len(set(names)) == 3
        assert names[0] == "Applications (Week 1)"
        assert names[1] == "Applications (Week 2)"


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

    def test_lesson_id_passes_through_to_plan(self):
        u = self.make_unit()
        c = _make_curriculum(title="Course", units=[u])
        lesson_id = uuid.uuid4()

        def renderer(unit):
            return [
                MoodleLessonPlan(
                    name="Lesson", content_html="<p>c</p>", lesson_id=lesson_id
                )
            ]

        plan = build_course_plan(c, lesson_renderer=renderer)
        assert plan.weeks[0].lessons[0].lesson_id == lesson_id

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
