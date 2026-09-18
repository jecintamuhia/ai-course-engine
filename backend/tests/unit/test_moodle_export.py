"""Unit tests for the Moodle-ready curriculum export (fallback path)."""

import uuid
from unittest.mock import MagicMock

from app.models.topic import SourceType
from app.services.moodle.export import (
    EXPORT_FORMAT,
    EXPORT_VERSION,
    build_curriculum_export,
)


def _make_topic(
    *,
    title: str,
    difficulty: int = 3,
    workload: int = 60,
    objectives: list[str] | None = None,
    prerequisites: list[str] | None = None,
    source_type: SourceType = SourceType.AI_GENERATED,
):
    t = MagicMock()
    t.title = title
    t.difficulty = difficulty
    t.estimated_workload_minutes = workload
    t.learning_objectives = objectives or []
    t.prerequisite_titles = prerequisites or []
    t.source_type = source_type
    return t


def _make_unit(*, week_number: int, topics: list):
    u = MagicMock()
    u.week_number = week_number
    u.title = f"Week {week_number}"
    u.description = f"Week {week_number} description"
    u.learning_objectives = [f"Objective {week_number}"]
    u.estimated_workload_minutes = 60
    links = []
    for topic in topics:
        link = MagicMock()
        link.topic = topic
        links.append(link)
    u.topic_links = links
    return u


def _make_curriculum(*, weeks: int = 3) -> MagicMock:
    c = MagicMock()
    c.id = uuid.uuid4()
    c.version_number = 2
    c.status = MagicMock()
    c.status.value = "approved"
    c.title = "Machine Learning Fundamentals"
    c.description = "A 16-week ML course."
    c.total_weeks = weeks
    c.learning_days_per_week = 5
    c.hours_per_day = 4
    c.max_weekly_workload_minutes = 1200
    c.document_id = uuid.uuid4()
    c.units = [
        _make_unit(
            week_number=i,
            topics=[
                _make_topic(
                    title=f"Topic {i}.{j}",
                    difficulty=2,
                    workload=45,
                    objectives=[f"Objective {i}.{j}"],
                    prerequisites=[f"P {i}.{j}"],
                )
                for j in range(1, 3)
            ],
        )
        for i in range(1, weeks + 1)
    ]
    return c


class TestBuildCurriculumExport:
    def test_payload_marks_itself_as_not_importable(self):
        payload = build_curriculum_export(_make_curriculum())

        assert payload["format"] == EXPORT_FORMAT
        assert payload["version"] == EXPORT_VERSION
        assert payload["importable"] is False
        assert "backup" in payload["notes"]

    def test_contains_course_description_and_planning_context(self):
        course = _make_curriculum(weeks=2)
        payload = build_curriculum_export(course)

        curriculum = payload["curriculum"]
        assert curriculum["title"] == "Machine Learning Fundamentals"
        assert curriculum["description"] == "A 16-week ML course."
        assert curriculum["total_weeks"] == 2
        assert curriculum["max_weekly_workload_minutes"] == 1200

    def test_every_week_includes_topics_objectives_and_workload(self):
        payload = build_curriculum_export(_make_curriculum(weeks=4))

        assert len(payload["weeks"]) == 4
        for week in payload["weeks"]:
            assert week["learning_objectives"] == [f"Objective {week['week_number']}"]
            assert week["estimated_workload_minutes"] == 60
            assert len(week["topics"]) == 2

    def test_topics_carry_prequisites_difficulty_workload_and_source(self):
        payload = build_curriculum_export(_make_curriculum(weeks=1))
        topic = payload["weeks"][0]["topics"][0]

        assert topic["title"] == "Topic 1.1"
        assert topic["learning_objectives"] == ["Objective 1.1"]
        assert topic["prerequisite_titles"] == ["P 1.1"]
        assert topic["difficulty"] == 2
        assert topic["estimated_workload_minutes"] == 45
        assert topic["source_type"] == "ai_generated"

    def test_source_provenance_includes_document_info(self):
        course = _make_curriculum(weeks=1)
        document = MagicMock()
        document.original_filename = "ml-textbook.pdf"

        payload = build_curriculum_export(course, document=document)

        assert payload["source"]["document_id"] == str(course.document_id)
        assert payload["source"]["document_filename"] == "ml-textbook.pdf"

    def test_source_filename_is_null_without_document(self):
        payload = build_curriculum_export(_make_curriculum(weeks=1))

        assert payload["source"]["document_filename"] is None


class TestExportIndependentFromMoodle:
    def test_export_requires_no_moodle_client_or_config(self):
        payload = build_curriculum_export(_make_curriculum(weeks=16))

        assert payload["curriculum"]["total_weeks"] == 16
        assert payload["importable"] is False
        assert payload["format"] == EXPORT_FORMAT