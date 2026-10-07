"""Moodle-ready curriculum export (fallback delivery path).

When Moodle is unavailable or lacks the publishing capabilities, this
produces a structured, human-consumable JSON description of the planned
course: title, description, the full week schedule, per-topic learning
objectives, prerequisites, difficulty/workload estimates, and the source
provenance for every item.

This export is intentionally NOT a Moodle backup/restore archive. It
does not claim to be importable into Moodle: ``importable`` is always
false, because no generic Moodle import path accepts this format. It is
a reference document a lecturer or Moodle administrator can use to
recreate the course by hand, and a fallback when live publishing is
blocked.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from app.models.curriculum import Curriculum
from app.models.document import Document

EXPORT_FORMAT = "ai-course-engine/curriculum-export"
EXPORT_VERSION = 1

_NOT_IMPORTABLE_NOTE = (
    "Reference export of the planned course. This is not a Moodle backup "
    "file and cannot be imported into Moodle directly; use live publishing "
    "once the Moodle administrator has granted the required capabilities."
)


def build_curriculum_export(
    curriculum: Curriculum,
    *,
    document: Document | None = None,
) -> dict:
    """Build the Moodle-ready curriculum export payload for a curriculum."""
    weeks = [
        {
            "week_number": unit.week_number,
            "title": unit.title,
            "description": unit.description,
            "learning_objectives": list(unit.learning_objectives or []),
            "estimated_workload_minutes": unit.estimated_workload_minutes,
            "topics": [
                _topic_payload(link.topic)
                for link in unit.topic_links
                if link.topic is not None
            ],
        }
        for unit in curriculum.units
    ]

    return {
        "format": EXPORT_FORMAT,
        "version": EXPORT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "importable": False,
        "notes": _NOT_IMPORTABLE_NOTE,
        "curriculum": {
            "id": str(curriculum.id),
            "version_number": curriculum.version_number,
            "status": getattr(curriculum.status, "value", curriculum.status),
            "title": curriculum.title,
            "description": curriculum.description,
            "total_weeks": curriculum.total_weeks,
            "learning_days_per_week": curriculum.learning_days_per_week,
            "hours_per_day": curriculum.hours_per_day,
            "max_weekly_workload_minutes": curriculum.max_weekly_workload_minutes,
        },
        "source": {
            "document_id": str(curriculum.document_id),
            "document_filename": (
                document.original_filename if document is not None else None
            ),
            "provenance": (
                "Topics carry per-item source_type (ai_generated / "
                "source_derived / ai_enriched) and are grounded in the "
                "source document via topic source chunks."
            ),
        },
        "weeks": weeks,
    }


def _topic_payload(topic) -> dict:
    """Serialize a Topic (or test double) into the export payload shape."""
    return {
        "title": topic.title,
        "learning_objectives": list(topic.learning_objectives or []),
        "prerequisite_titles": list(topic.prerequisite_titles or []),
        "difficulty": topic.difficulty,
        "estimated_workload_minutes": topic.estimated_workload_minutes,
        "source_type": _enum_value(topic.source_type),
    }


def _enum_value(value):
    """Return ``value.value`` for enums and the raw value otherwise."""
    if isinstance(value, enum.Enum):
        return value.value
    return value
