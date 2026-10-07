"""Pydantic schemas for content QA and textbook coverage reports."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

QAVerdict = Literal["pass", "warning", "fail"]
FindingSeverity = Literal["error", "warning", "info"]
AreaStatus = Literal["pass", "warning", "fail"]


class QALocation(BaseModel):
    """A concrete location a QA finding refers to."""

    kind: str
    id: uuid.UUID | None = None
    title: str | None = None
    detail: str | None = None


class QAFinding(BaseModel):
    """One automated QA finding."""

    rule: str
    code: str
    severity: FindingSeverity
    message: str
    locations: list[QALocation] = Field(default_factory=list)


class QAAreaStatus(BaseModel):
    """Per-rule-domain QA outcome."""

    status: AreaStatus
    findings: int


class QAReportRead(BaseModel):
    """Persisted content-QA inspection of a curriculum."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    curriculum_id: uuid.UUID
    version_number: int
    verdict: QAVerdict
    areas: dict[str, QAAreaStatus]
    findings: list[QAFinding]
    summary: dict
    checked_at: datetime


class QAReportResponse(BaseModel):
    """Response returned after running (and persisting) a QA pass."""

    report: QAReportRead
    blocked: bool = False


class TopicCoverageItem(BaseModel):
    """A single topic row in the textbook coverage report."""

    topic_id: uuid.UUID
    title: str
    chapter_id: uuid.UUID | None = None
    chapter_title: str | None = None
    importance: str | None = None
    workload_minutes: int
    sources_chapters: int = 0
    mapped: bool
    has_lesson: bool


class CoverageReportRead(BaseModel):
    """Textbook coverage report: how completely the document is covered."""

    document_id: uuid.UUID
    document_title: str
    curriculum_id: uuid.UUID | None = None
    chapters: int
    sections: int
    topic_count: int
    importance_counts: dict[str, int] = Field(default_factory=dict)
    mapped_topic_count: int
    lesson_count: int
    coverage_percent: float
    duplicate_topics_removed: int
    unresolved_topic_count: int
    unresolved_topics: list[str] = Field(default_factory=list)
    resource_count: int
    video_count: int
    activity_count: int
    knowledge_check_count: int
    diagram_count: int
    topics: list[TopicCoverageItem] = Field(default_factory=list)
