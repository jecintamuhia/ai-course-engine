"""Schemas for taking an assessment and verifying a certificate."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from app.schemas.assessment import AssessmentItemKind, AssessmentOption
from pydantic import BaseModel, ConfigDict, Field


class AssessmentQuestionRead(BaseModel):
    """
    A question shown before submission.

    The correct option, correct answer and explanation are deliberately
    absent so the payload cannot be used to cheat. They are returned in
    the attempt result once the answer sheet has been submitted.
    """

    item_index: int
    kind: AssessmentItemKind
    prompt: str
    learning_objective: str
    difficulty: Literal["easy", "medium", "hard"]
    options: list[AssessmentOption] = Field(default_factory=list)
    auto_gradable: bool


class AssessmentAttemptSummary(BaseModel):
    """Compact history of one past attempt."""

    id: uuid.UUID
    attempt_number: int
    score_percent: int
    correct_count: int
    auto_gradable_count: int
    passed: bool
    submitted_at: datetime


class CertificateSummary(BaseModel):
    """Certificate reference shown on the assessment page."""

    reference: str
    issued_at: datetime
    score_percent: int


class FinalAssessmentRead(BaseModel):
    """A learner's view of the course's final assessment and eligibility."""

    assessment_id: uuid.UUID
    title: str
    description: str
    estimated_minutes: int
    pass_percent: int
    questions: list[AssessmentQuestionRead]
    auto_gradable_count: int
    total_items: int
    completed_lessons: int
    total_lessons: int
    all_lessons_completed: bool
    attempts: list[AssessmentAttemptSummary]
    best_score_percent: int | None = None
    best_attempt_id: uuid.UUID | None = None
    passed: bool
    certificate: CertificateSummary | None = None


class AssessmentAnswer(BaseModel):
    """One answer. Objective items use ``option_id``; text items use ``answer``."""

    item_index: int = Field(ge=0)
    option_id: str | None = None
    answer: str | None = None


class AssessmentSubmitRequest(BaseModel):
    """A complete answer sheet."""

    answers: list[AssessmentAnswer]


class AssessmentItemResult(BaseModel):
    """Per-question feedback returned after submission."""

    item_index: int
    kind: AssessmentItemKind
    prompt: str
    answered: bool
    auto_graded: bool
    correct: bool | None = None
    submitted_option_id: str | None = None
    submitted_answer: str | None = None
    correct_option_id: str | None = None
    correct_answer: str | None = None
    explanation: str = ""


class AssessmentAttemptRead(BaseModel):
    """A submitted attempt, including per-question feedback."""

    id: uuid.UUID
    assessment_id: uuid.UUID
    attempt_number: int
    score_percent: int
    correct_count: int
    auto_gradable_count: int
    passed: bool
    submitted_at: datetime
    results: list[AssessmentItemResult]


class AssessmentAttemptListResponse(BaseModel):
    """A learner's full attempt history for one assessment."""

    attempts: list[AssessmentAttemptRead]


class CertificateRead(BaseModel):
    """A verifiable certificate."""

    model_config = ConfigDict(from_attributes=True)

    reference: str
    learner_name: str
    course_title: str
    score_percent: int
    completed_lessons: int
    total_lessons: int
    issued_at: datetime


class CertificateCourseRead(CertificateRead):
    """A certificate enriched with the course it belongs to."""

    course_id: uuid.UUID


class CertificateListResponse(BaseModel):
    """All certificates earned by the signed-in learner."""

    certificates: list[CertificateCourseRead]
