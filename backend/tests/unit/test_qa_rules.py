"""Unit tests for the pure content-QA rules."""

from __future__ import annotations

import uuid

from app.models.assessment import Assessment, AssessmentStatus, AssessmentType
from app.models.chapter import Chapter
from app.models.concept import Concept
from app.models.curriculum import Curriculum
from app.models.curriculum_unit import CurriculumUnit
from app.models.curriculum_unit_topic import CurriculumUnitTopic
from app.models.dependency import Dependency
from app.models.lesson import Lesson
from app.models.lesson_content_block import LessonBlockType, LessonContentBlock
from app.models.topic import ContentLevel, Topic, TopicImportance
from app.services.qa.rules import (
    QAData,
    check_coverage,
    check_duplication,
    check_learning_design,
    check_moodle,
    check_provenance,
    check_quality,
    run_all_rules,
)


def _topic(
    title: str,
    *,
    topic_id: uuid.UUID | None = None,
    importance: str | None = None,
    parent: uuid.UUID | None = None,
    duplicate_of: uuid.UUID | None = None,
    chapter_id: uuid.UUID | None = None,
    canonical_key: str | None = None,
    prerequisites: list[str] | None = None,
    content_level: ContentLevel | None = None,
) -> Topic:
    topic = Topic(
        id=topic_id or uuid.uuid4(),
        document_id=uuid.uuid4(),
        title=title,
        difficulty=2,
        estimated_workload_minutes=120,
        order_index=0,
    )
    topic.importance = importance
    topic.parent_topic_id = parent
    topic.duplicate_of_id = duplicate_of
    topic.chapter_id = chapter_id
    topic.canonical_key = canonical_key
    topic.prerequisite_titles = prerequisites or []
    topic.content_level = content_level
    return topic


def _concept(
    *,
    terminology: list[str] | None = None,
    definition: str | None = None,
) -> Concept:
    concept = Concept(
        id=uuid.uuid4(),
        topic_id=uuid.uuid4(),
        name="Concept",
        description="d",
        order_index=0,
    )
    concept.terminology = terminology or []
    concept.procedures = []
    concept.formulas = []
    concept.worked_examples = []
    concept.exercises = []
    concept.misconceptions = []
    concept.provenance = []
    concept.definition = definition
    return concept


def _block(
    block_type: LessonBlockType,
    payload: dict | None = None,
    *,
    title: str | None = None,
) -> LessonContentBlock:
    return LessonContentBlock(
        id=uuid.uuid4(),
        lesson_id=uuid.uuid4(),
        order_index=0,
        block_type=block_type,
        title=title,
        payload=payload or {},
    )


def _lesson(
    title: str,
    *,
    blocks: list[LessonContentBlock] | None = None,
    lesson_id: uuid.UUID | None = None,
    unit_id: uuid.UUID | None = None,
    topic: Topic | None = None,
    objectives: list[str] | None = None,
    week: int = 1,
) -> Lesson:
    lesson = Lesson(
        id=lesson_id or uuid.uuid4(),
        curriculum_id=uuid.uuid4(),
        curriculum_unit_id=unit_id or uuid.uuid4(),
        topic_id=topic.id if topic else uuid.uuid4(),
        week_number=week,
        order_index=0,
        title=title,
        description="d",
        learning_objectives=(
            objectives if objectives is not None else ["Understand " + title]
        ),
        estimated_workload_minutes=60,
    )
    lesson.content_blocks = blocks or []
    return lesson


def _unit(topic: Topic, *, week: int = 1) -> tuple[CurriculumUnit, CurriculumUnitTopic]:
    unit = CurriculumUnit(
        id=uuid.uuid4(),
        curriculum_id=uuid.uuid4(),
        week_number=week,
        title=f"Week {week}",
        description="unit",
        learning_objectives=["LO for " + topic.title],
        estimated_workload_minutes=120,
        order_index=week - 1,
    )
    link = CurriculumUnitTopic(
        id=uuid.uuid4(),
        curriculum_unit_id=unit.id,
        topic_id=topic.id,
        order_index=0,
    )
    unit.topic_links = [link]
    return unit, link


def _curriculum(
    *, units: list[CurriculumUnit] | None = None, title: str = "DoE"
) -> Curriculum:
    curriculum = Curriculum(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        title=title,
        description=None,
        total_weeks=16,
        learning_days_per_week=5,
        hours_per_day=2,
        max_weekly_workload_minutes=600,
        min_topic_allocation_minutes=60,
        max_topic_allocation_minutes=240,
    )
    curriculum.units = units or []
    return curriculum


def _chapter(title: str) -> Chapter:
    return Chapter(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        title=title,
        number=1,
        start_page=1,
        end_page=10,
        order_index=0,
    )


def _data(curriculum, topics, lessons, **kwargs) -> QAData:
    return QAData(
        curriculum=curriculum,
        topics=topics,
        lessons=lessons,
        assessments=kwargs.pop("assessments", []),
        chapters=[],
        course=None,
        **kwargs,
    )


def test_coverage_requires_canonical_topics():
    curriculum = _curriculum()
    data = _data(curriculum, [], [])
    findings = check_coverage(data)
    assert any(
        f.code == "no_canonical_topics" and f.severity == "error" for f in findings
    )


def test_coverage_reports_unmapped_and_lessonless_topics():
    major = _topic("Major Topic", importance=TopicImportance.MAJOR.value)
    minor = _topic("Minor Topic", importance=TopicImportance.MINOR.value)
    unit, _ = _unit(major)
    curriculum = _curriculum(units=[unit])

    lesson = _lesson("Major Topic Lesson", topic=major, unit_id=unit.id)

    data = _data(curriculum, [major, minor], [lesson])
    findings = check_coverage(data)
    codes = {f.code: f for f in findings}

    assert "topic_not_mapped" in codes  # minor, info severity
    assert codes["topic_not_mapped"].severity == "info"
    assert "major_topic_unmapped" not in codes
    assert "topic_without_lesson" not in codes  # major has its lesson

    no_lesson = _topic("Another Major", importance=TopicImportance.MAJOR.value)
    (unit2, _) = _unit(no_lesson)
    curriculum2 = _curriculum(units=[unit, unit2])
    data2 = _data(curriculum2, [major, minor, no_lesson], [lesson])
    findings2 = check_coverage(data2)
    assert any(
        f.code == "topic_without_lesson" and f.severity == "error"
        for f in findings2
    )


def test_coverage_flags_unmapped_major_topic_as_error():
    major = _topic("Orphan", importance=TopicImportance.MAJOR.value)
    minor = _topic("Mapped", importance=TopicImportance.MINOR.value)
    unit, _ = _unit(minor)
    curriculum = _curriculum(units=[unit])
    data = _data(curriculum, [major, minor], [])
    findings = check_coverage(data)
    assert any(
        f.code == "major_topic_unmapped" and f.severity == "error" for f in findings
    )


def test_duplication_errors_on_unhandled_duplicate_topics():
    topics = [
        _topic("Decision Trees"),
        _topic("Decision tree"),
    ]
    data = _data(_curriculum(), topics, [])
    findings = check_duplication(data)
    assert any(
        f.code == "duplicate_topic_detected" and f.severity == "error" for f in findings
    )


def test_duplication_downgrades_to_info_after_canonicalization():
    first = _topic("Decision Trees", canonical_key="decision trees")
    topics = [
        first,
        _topic(
            "Decision tree",
            canonical_key="decision trees",
            duplicate_of=first.id,
        ),
    ]
    data = _data(_curriculum(), topics, [])
    findings = check_duplication(data)
    assert any(
        f.code == "duplicate_topic_detected" and f.severity == "info" for f in findings
    )


def test_duplication_flags_near_duplicates_above_threshold():
    left = _topic(
        "Information Security Risk Management",
        canonical_key="information security risk management",
    )
    right = _topic(
        "Information Security Risk Management Framework",
        canonical_key="information security risk management framework",
    )
    data = _data(_curriculum(), [left, right], [])
    findings = check_duplication(data)

    near = [
        f
        for f in findings
        if f.code == "near_duplicate_topic_detected" and f.severity == "warning"
    ]
    assert len(near) == 1
    assert "0.80" in near[0].message
    assert "not merged" in near[0].message


def test_duplication_ignores_pairs_below_similarity_threshold():
    left = _topic("Decision Trees", canonical_key="decision trees")
    right = _topic(
        "Introduction to Accounting", canonical_key="introduction accounting"
    )
    data = _data(_curriculum(), [left, right], [])
    findings = check_duplication(data)

    assert not any(f.code == "near_duplicate_topic_detected" for f in findings)


def test_duplication_never_reports_same_key_pairs_as_near_duplicates():
    first = _topic("Decision Trees", canonical_key="decision trees")
    second = _topic(
        "Decision tree",
        canonical_key="decision trees",
        duplicate_of=first.id,
    )
    data = _data(_curriculum(), [first, second], [])
    findings = check_duplication(data)

    assert not any(f.code == "near_duplicate_topic_detected" for f in findings)


def test_duplication_errors_on_repeated_lesson_titles_in_week():
    lesson = _lesson("Beware", objectives=["x"])
    lesson2 = _lesson("Beware", objectives=["x"], unit_id=lesson.curriculum_unit_id)
    data = _data(_curriculum(), [], [lesson, lesson2])
    findings = check_duplication(data)
    assert any(f.code == "duplicate_lesson_detected" for f in findings)


def test_provenance_errors_on_ungrounded_and_empty_lessons():
    bare = _lesson("Empty")
    ungrounded = _lesson(
        "Ungrounded",
        blocks=[_block(LessonBlockType.TEXT, {"content": "some prose text"})],
    )
    data = _data(_curriculum(), [], [bare, ungrounded])
    findings = check_provenance(data)
    codes = {f.code for f in findings}
    assert "empty_lesson" in codes
    assert "missing_source_grounding" in codes


def test_provenance_validates_urls_and_video_ids():
    bad_url = _lesson(
        "Bad URL",
        blocks=[_block(LessonBlockType.TEXT, {"content": "text"})],
    )
    bad_url.content_blocks = [
        _block(
            LessonBlockType.TEXT,
            {"content": "body", "source_chunk_markers": ["chunk-1"]},
        ),
        _block(LessonBlockType.EXTERNAL_RESOURCE, {"url": "not-a-url"}, title="r"),
        _block(LessonBlockType.VIDEO, {"video_id": "bad id!"}, title="v"),
    ]
    data = _data(_curriculum(), [], [bad_url])
    findings = check_provenance(data)
    codes = {f.code for f in findings}
    assert "invalid_resource_url" in codes
    assert "invalid_video_id" in codes


def test_quality_flags_shallow_major_lesson_and_placeholders():
    major = _topic("Big", importance=TopicImportance.MAJOR.value)
    shallow = _lesson(
        "Shallow",
        topic=major,
        blocks=[
            _block(
                LessonBlockType.TEXT,
                {"content": "short", "source_chunk_markers": ["m"]},
            )
        ],
    )
    placeholder = _lesson(
        "Todo",
        blocks=[
            _block(
                LessonBlockType.TEXT,
                {"content": "TODO figure out this part", "source_chunk_markers": ["m"]},
            )
        ],
    )
    data = _data(_curriculum(), [], [shallow, placeholder])
    findings = check_quality(data)
    codes = {f.code for f in findings}
    assert "shallow_lesson" in codes
    assert "placeholder_content" in codes


def test_learning_design_demands_objectives_and_assessment_health():
    lesson = _lesson(
        "L",
        objectives=[],
        blocks=[
            _block(
                LessonBlockType.TEXT, {"content": "x", "source_chunk_markers": ["m"]}
            )
        ],
    )
    assessment = Assessment(
        id=uuid.uuid4(),
        curriculum_id=uuid.uuid4(),
        title="Bad Quiz",
        description="",
        assessment_type=AssessmentType.WEEKLY_QUIZ,
        learning_objectives=[],
        items=[],
        status=AssessmentStatus.DRAFT,
    )
    data = _data(_curriculum(), [], [lesson], assessments=[assessment])
    findings = check_learning_design(data)
    codes = {f.code for f in findings}
    assert "lesson_without_objectives" in codes
    assert "assessment_without_objectives" in codes
    assert "assessment_without_items" in codes


def test_learning_design_warns_without_assessments():
    lesson = _lesson(
        "L",
        blocks=[
            _block(
                LessonBlockType.TEXT, {"content": "x", "source_chunk_markers": ["m"]}
            )
        ],
    )
    data = _data(_curriculum(), [], [lesson])
    findings = check_learning_design(data)
    assert any(f.code == "course_without_assessment" for f in findings)


def test_learning_design_warns_on_prerequisite_scheduled_later():
    early = _topic("Early")
    late = _topic("Later")
    (early_unit, _) = _unit(early, week=2)
    (late_unit, _) = _unit(late, week=5)
    curriculum = _curriculum(units=[early_unit, late_unit])
    edge = Dependency(topic_id=early.id, depends_on_topic_id=late.id)
    data = _data(curriculum, [early, late], [], dependencies=[edge])
    findings = check_learning_design(data)
    assert any(f.code == "prerequisite_ordering" for f in findings)


def test_unresolved_prerequisite_title_does_not_create_qa_edge():
    early = _topic("Early", prerequisites=["Later"])
    late = _topic("Later")
    early_unit, _ = _unit(early, week=2)
    late_unit, _ = _unit(late, week=5)
    curriculum = _curriculum(units=[early_unit, late_unit])

    findings = check_learning_design(_data(curriculum, [early, late], []))

    assert not any(f.code == "prerequisite_ordering" for f in findings)


def test_moodle_rejects_uuid_course_name_and_duplicate_week_page():
    unit = CurriculumUnit(
        id=uuid.uuid4(),
        curriculum_id=uuid.uuid4(),
        week_number=1,
        title="Week 1",
        description="u",
        learning_objectives=[],
        estimated_workload_minutes=120,
        order_index=0,
    )
    unit.topic_links = []
    curriculum = _curriculum(units=[unit], title="uuid-name-ignored")
    curriculum.title = str(uuid.uuid4())
    duplicate_week = _lesson("Week 1", unit_id=unit.id)
    data = _data(curriculum, [], [duplicate_week])
    findings = check_moodle(data)
    codes = {f.code for f in findings}
    assert "uuid_course_name" in codes
    assert "duplicate_week_page" in codes


def test_run_all_rules_returns_all_six_domains():
    data = _data(_curriculum(), [], [])
    domains = run_all_rules(data)
    assert set(domains) == {
        "coverage",
        "duplication",
        "provenance",
        "quality",
        "learning_design",
        "moodle",
    }
    for findings in domains.values():
        assert isinstance(findings, list)


def test_coverage_flags_orphan_lessons_without_topic():
    topic = _topic('Grounded', importance=TopicImportance.MAJOR.value)
    unit, _ = _unit(topic)
    curriculum = _curriculum(units=[unit])
    lesson = _lesson('Orphan Lesson', topic=topic, unit_id=unit.id)
    lesson.topic_id = None

    data = _data(curriculum, [topic], [lesson])
    findings = check_coverage(data)
    assert any(
        f.code == 'lesson_without_topic' and f.severity == 'error'
        for f in findings
    )


def test_coverage_flags_zero_output_weeks():
    first = _topic('Week One Topic', importance=TopicImportance.MAJOR.value)
    second = _topic('Week Two Topic', importance=TopicImportance.MAJOR.value)
    unit1, _ = _unit(first, week=1)
    unit2, _ = _unit(second, week=2)
    curriculum = _curriculum(units=[unit1, unit2])
    lesson = _lesson('Only Week One', topic=first, unit_id=unit1.id, week=1)

    data = _data(curriculum, [first, second], [lesson])
    findings = check_coverage(data)

    zero_weeks = [
        f for f in findings if f.code == 'week_without_lessons'
    ]
    assert len(zero_weeks) == 1
    assert zero_weeks[0].severity == 'error'
    assert 'week 2' in zero_weeks[0].message.lower()


def test_coverage_accepts_week_that_has_lessons():
    topic = _topic('Covered', importance=TopicImportance.MAJOR.value)
    unit, _ = _unit(topic, week=1)
    curriculum = _curriculum(units=[unit])
    lesson = _lesson('Covered Lesson', topic=topic, unit_id=unit.id, week=1)

    data = _data(curriculum, [topic], [lesson])
    findings = check_coverage(data)

    assert not any(f.code == 'week_without_lessons' for f in findings)
    assert not any(f.code == 'lesson_without_topic' for f in findings)


def test_week_workload_exceeded_warns():
    topic = _topic('Busy', importance=TopicImportance.MAJOR.value)
    unit, _ = _unit(topic, week=1)
    curriculum = _curriculum(units=[unit])
    lesson = _lesson('Busy Lesson', topic=topic, unit_id=unit.id, week=1)
    lesson.estimated_workload_minutes = 700

    data = _data(curriculum, [topic], [lesson])
    findings = check_learning_design(data)

    assert any(
        f.code == 'week_workload_exceeded' and f.severity == 'warning'
        for f in findings
    )


def test_week_workload_underfilled_reports_info():
    topic = _topic('Light', importance=TopicImportance.MAJOR.value)
    unit, _ = _unit(topic, week=1)
    curriculum = _curriculum(units=[unit])
    lesson = _lesson('Light Lesson', topic=topic, unit_id=unit.id, week=1)

    data = _data(curriculum, [topic], [lesson])
    findings = check_learning_design(data)

    underfilled = [
        f for f in findings if f.code == 'week_workload_underfilled'
    ]
    assert underfilled and underfilled[0].severity == 'info'


def test_progression_inverted_when_advanced_starts_before_basic():
    basic = _topic('Basics', content_level=ContentLevel.BASIC)
    advanced = _topic('Advanced Stuff', content_level=ContentLevel.ADVANCED)
    unit_advanced, _ = _unit(advanced, week=1)
    unit_basic, _ = _unit(basic, week=4)
    curriculum = _curriculum(units=[unit_advanced, unit_basic])

    data = _data(curriculum, [basic, advanced], [])
    findings = check_learning_design(data)

    inverted = [f for f in findings if f.code == 'progression_inverted']
    assert len(inverted) == 1
    assert inverted[0].severity == 'warning'
    assert 'ADVANCED' in inverted[0].message
    assert 'BASIC' in inverted[0].message


def test_progression_ok_when_levels_advance_in_order():
    basic = _topic('Basics', content_level=ContentLevel.BASIC)
    intermediate = _topic(
        'Middle', content_level=ContentLevel.INTERMEDIATE
    )
    advanced = _topic('Advanced', content_level=ContentLevel.ADVANCED)
    unit1, _ = _unit(basic, week=1)
    unit2, _ = _unit(intermediate, week=2)
    unit3, _ = _unit(advanced, week=3)
    curriculum = _curriculum(units=[unit1, unit2, unit3])

    data = _data(curriculum, [basic, intermediate, advanced], [])
    findings = check_learning_design(data)

    assert not any(f.code == 'progression_inverted' for f in findings)


def test_content_level_missing_warns_for_scheduled_topics():
    topic = _topic('Unleveled', content_level=None)
    unit, _ = _unit(topic, week=1)
    curriculum = _curriculum(units=[unit])

    data = _data(curriculum, [topic], [])
    findings = check_learning_design(data)

    missing = [f for f in findings if f.code == 'content_level_missing']
    assert missing and missing[0].severity == 'warning'


def test_quality_warns_when_no_knowledge_units_extracted():
    topic = _topic('Bare Topic')
    topic.concepts = [_concept()]
    data = _data(_curriculum(), [topic], [])

    findings = check_quality(data)

    assert any(
        f.code == 'knowledge_units_not_extracted' and f.severity == 'warning'
        for f in findings
    )


def test_quality_skips_ku_check_entirely_without_topics():
    data = _data(_curriculum(), [], [])

    findings = check_quality(data)

    assert not any(
        f.code == 'knowledge_units_not_extracted' for f in findings
    )


def test_quality_flags_lesson_that_ignores_terminology():
    topic = _topic('Termy Topic')
    topic.concepts = [
        _concept(
            definition='def',
            terminology=['alpha', 'beta', 'gamma'],
        )
    ]
    lesson = _lesson('Termy Lesson', topic=topic)
    lesson.content_blocks = [
        _block(LessonBlockType.TEXT, {'content': 'generic prose only'})
    ]

    data = _data(_curriculum(), [topic], [lesson])
    findings = check_quality(data)

    unused = [f for f in findings if f.code == 'knowledge_units_unused']
    assert unused and unused[0].severity == 'warning'


def test_quality_accepts_lesson_that_uses_terminology():
    topic = _topic('Termy Topic')
    topic.concepts = [
        _concept(
            definition='def',
            terminology=['alpha', 'beta', 'gamma'],
        )
    ]
    lesson = _lesson('Termy Lesson', topic=topic)
    lesson.content_blocks = [
        _block(
            LessonBlockType.TEXT,
            {'content': 'prose explaining the alpha mechanism in detail'},
        )
    ]

    data = _data(_curriculum(), [topic], [lesson])
    findings = check_quality(data)

    assert not any(f.code == 'knowledge_units_unused' for f in findings)
