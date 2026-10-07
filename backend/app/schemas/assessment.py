"""Pydantic schemas for assessments and objective alignment."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from app.models.assessment import AssessmentStatus, AssessmentType
from pydantic import BaseModel, ConfigDict, Field

AssessmentItemKind = Literal[
    "multiple_choice",
    "true_false",
    "short_answer",
    "scenario",
    "practical",
    "coding",
    "matching",
]


class AssessmentOption(BaseModel):
    """An option for an objective multiple-choice assessment item."""

    id: str
    text: str


class AssessmentItem(BaseModel):
    """
    One assessment item. ``correct_answer`` carries the ground-truth
    answer text for review; choices items list ``options`` and their
    ``correct_option_id`` must reference an existing option.
    """

    kind: AssessmentItemKind
    prompt: str
    learning_objective: str
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    options: list[AssessmentOption] = Field(default_factory=list)
    correct_option_id: str | None = None
    correct_answer: str | None = None
    explanation: str = ""
    rubric: str | None = None
    source_chunk_markers: list[str] = Field(default_factory=list)


class AssessmentAlignment(BaseModel):
    """Explicit learning-objective → lesson → evidence mapping."""

    learning_objective: str
    lesson_id: uuid.UUID | None = None
    lesson_title: str | None = None
    unit_week: int | None = None
    evidence: list[str] = Field(default_factory=list)


class AssessmentRead(BaseModel):
    """Public representation of a generated assessment."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    curriculum_id: uuid.UUID
    curriculum_unit_id: uuid.UUID | None = None
    week_number: int | None = None
    title: str
    description: str
    assessment_type: AssessmentType
    learning_objectives: list[str]
    estimated_minutes: int
    items: list[AssessmentItem]
    alignment: list[AssessmentAlignment]
    status: AssessmentStatus
    generation_errors: list[dict] = Field(default_factory=list)
    reviewer_name: str | None = None
    review_comments: str | None = None
    created_at: datetime


class AssessmentGenerateRequest(BaseModel):
    """Request to generate assessments for a weekly unit or a course."""

    assessment_type: AssessmentType | None = None
    max_items: int = Field(default=6, ge=1, le=20)


class AssessmentListResponse(BaseModel):
    """List of assessments for a curriculum or unit."""

    assessments: list[AssessmentRead]


class AssessmentReviewRequest(BaseModel):
    """A lecturer's review decision on an assessment."""

    decision: Literal["approved", "rejected"]
    reviewer_name: str | None = Field(default=None, max_length=255)
    comments: str | None = None


class AssessmentAlignmentRead(BaseModel):
    """Alignment summary for the course: objectives ↔ lessons ↔ evidence."""

    assessment_id: uuid.UUID
    assessment_title: str
    objectives_covered: int
    objectives_total: int
    alignments: list[AssessmentAlignment]
