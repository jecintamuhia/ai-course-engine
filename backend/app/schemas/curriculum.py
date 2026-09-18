"""Pydantic schemas for curriculum resources."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from app.models.curriculum import CurriculumStatus
from app.models.curriculum_review import ReviewDecision
from pydantic import BaseModel, ConfigDict, Field


class CurriculumUnitTopicRead(BaseModel):
    """A topic assigned to a weekly unit, with its plan order."""

    model_config = ConfigDict(from_attributes=True)

    topic_id: uuid.UUID
    title: str
    order_index: int


class CurriculumUnitRead(BaseModel):
    """A single weekly unit of a curriculum."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    week_number: int
    title: str
    description: str
    learning_objectives: list[str]
    estimated_workload_minutes: int
    order_index: int
    topics: list[CurriculumUnitTopicRead] = Field(default_factory=list)


class CurriculumRead(BaseModel):
    """Public representation of a generated curriculum."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    title: str
    description: str | None = None
    status: CurriculumStatus
    total_weeks: int
    start_date: date | None
    learning_days_per_week: int
    hours_per_day: int
    max_weekly_workload_minutes: int
    min_topic_allocation_minutes: int
    max_topic_allocation_minutes: int
    version_number: int
    is_latest_version: bool
    created_at: datetime
    units: list[CurriculumUnitRead] = Field(default_factory=list)


class CurriculumGenerateRequest(BaseModel):
    """
    Configuration for generating a curriculum for a document.

    Defaults produce a 16-week / 4-month plan at 5 days a week, 4 hours
    a day, which is the platform's standard offering; nothing is
    hardcoded in the planner itself.
    """

    document_id: uuid.UUID
    total_weeks: int = Field(default=16, ge=1, le=52)
    learning_days_per_week: int = Field(default=5, ge=1, le=7)
    hours_per_day: int = Field(default=4, ge=1, le=12)
    start_date: date | None = None
    title: str | None = Field(
        default=None,
        max_length=500,
        description="Optional course title override; defaults to the source filename.",
    )
    description: str | None = Field(
        default=None,
        description="Optional course description stored on the generated curriculum.",
    )


class CurriculumGenerateResponse(BaseModel):
    """Response returned after generating a curriculum."""

    curriculum: CurriculumRead


class CurriculumReviewRequest(BaseModel):
    """A lecturer's review decision on a curriculum."""

    decision: Literal["approved", "rejected"]
    reviewer_name: str | None = Field(default=None, max_length=255)
    comments: str | None = None


class CurriculumReviewRead(BaseModel):
    """Public representation of a stored review record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    curriculum_id: uuid.UUID
    reviewer_name: str | None
    decision: ReviewDecision
    comments: str | None
    reviewed_at: datetime


class CurriculumDetailRead(BaseModel):
    """A curriculum with its review history attached."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    title: str
    description: str | None = None
    status: CurriculumStatus
    total_weeks: int
    start_date: date | None
    learning_days_per_week: int
    hours_per_day: int
    max_weekly_workload_minutes: int
    min_topic_allocation_minutes: int
    max_topic_allocation_minutes: int
    version_number: int
    is_latest_version: bool
    created_at: datetime
    units: list[CurriculumUnitRead] = Field(default_factory=list)
    reviews: list[CurriculumReviewRead] = Field(default_factory=list)


class CurriculumListResponse(BaseModel):
    """List of curricula for a document, newest version first."""

    curricula: list[CurriculumRead]
