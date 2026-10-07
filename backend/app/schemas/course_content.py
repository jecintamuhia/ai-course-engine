"""Pydantic schemas for course content (lessons, blocks, source maps)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from app.models.lesson import LessonStatus
from app.models.lesson_content_block import BlockReviewStatus, LessonBlockType
from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Block payload schemas (validated on write; stored as JSONB on the model)
# ---------------------------------------------------------------------------


class _BlockPayloadBase(BaseModel):
    """Shared fields of every stored block payload."""

    source_chunk_markers: list[str] = Field(default_factory=list)


class TextBlockPayload(_BlockPayloadBase):
    """A prose block."""

    content: str = Field(min_length=1, max_length=6000)


class HeadingBlockPayload(_BlockPayloadBase):
    """A section heading."""

    level: Literal[2, 3] = 2
    text: str = Field(min_length=1, max_length=300)


class ExampleBlockPayload(_BlockPayloadBase):
    """A worked example."""

    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=6000)


class DiagramNodePayload(BaseModel):
    """A node within a stored diagram."""

    id: str = Field(min_length=1, max_length=50)
    label: str = Field(min_length=1, max_length=200)


class DiagramEdgePayload(BaseModel):
    """A directed edge within a stored diagram."""

    source: str = Field(min_length=1, max_length=50)
    target: str = Field(min_length=1, max_length=50)
    label: str | None = Field(default=None, max_length=150)


class DiagramBlockPayload(_BlockPayloadBase):
    """A structured diagram (rendered to Moodle-safe HTML at publish time)."""

    diagram_type: Literal["flowchart", "hierarchy", "concept_map", "comparison"]
    caption: str = Field(min_length=1, max_length=500)
    nodes: list[DiagramNodePayload] = Field(default_factory=list)
    edges: list[DiagramEdgePayload] = Field(default_factory=list)


class TableBlockPayload(_BlockPayloadBase):
    """A data table."""

    caption: str | None = Field(default=None, max_length=500)
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class ExternalResourcePayload(_BlockPayloadBase):
    """A validated external resource (URL confirmed reachable)."""

    kind: Literal["article", "documentation", "tool", "video_lesson"]
    title: str = Field(min_length=1, max_length=300)
    url: str = Field(min_length=1, max_length=2000)
    description: str = Field(min_length=1, max_length=1000)
    why_recommended: str = Field(min_length=1, max_length=1000)
    validated_at: datetime | None = None


class VideoPayload(_BlockPayloadBase):
    """A discovered video (YouTube Data API, never LLM-fabricated)."""

    title: str = Field(min_length=1, max_length=500)
    video_id: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=2000)
    channel: str | None = Field(default=None, max_length=300)
    description: str = Field(default="", max_length=1500)
    reason: str = Field(default="", max_length=1000)


class ActivityPayload(_BlockPayloadBase):
    """A learning activity."""

    kind: Literal["practice_exercise", "project", "discussion", "research"]
    title: str = Field(min_length=1, max_length=300)
    instructions: str = Field(min_length=1, max_length=4000)
    estimated_minutes: int = Field(ge=0, le=10080)


class KnowledgeCheckOptionPayload(BaseModel):
    """One multiple-choice option."""

    id: str = Field(min_length=1, max_length=50)
    text: str = Field(min_length=1, max_length=500)


class KnowledgeCheckPayload(_BlockPayloadBase):
    """A single multiple-choice knowledge check."""

    question: str = Field(min_length=1, max_length=1000)
    options: list[KnowledgeCheckOptionPayload] = Field(default_factory=list)
    correct_option_id: str = Field(min_length=1, max_length=50)
    explanation: str = Field(min_length=1, max_length=1500)
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class SummaryBlockPayload(_BlockPayloadBase):
    """A lesson summary."""

    content: str = Field(min_length=1, max_length=4000)


# ---------------------------------------------------------------------------
# Read schemas
# ---------------------------------------------------------------------------


class LessonBlockRead(BaseModel):
    """Public representation of a single lesson content block."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lesson_id: uuid.UUID
    block_type: LessonBlockType
    order_index: int
    title: str | None = None
    payload: dict
    review_status: BlockReviewStatus
    review_comments: str | None = None
    created_at: datetime
    updated_at: datetime


class LessonRead(BaseModel):
    """Public representation of a generated lesson."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    curriculum_id: uuid.UUID
    curriculum_unit_id: uuid.UUID
    topic_id: uuid.UUID | None = None
    week_number: int
    order_index: int
    title: str
    description: str
    learning_objectives: list[str]
    estimated_workload_minutes: int
    status: LessonStatus
    generation_errors: list
    created_at: datetime
    updated_at: datetime
    blocks: list[LessonBlockRead] = Field(default_factory=list)


class LessonListResponse(BaseModel):
    """Lessons ordered for a weekly unit."""

    curriculum_unit_id: uuid.UUID
    lessons: list[LessonRead]


# ---------------------------------------------------------------------------
# Source map
# ---------------------------------------------------------------------------


class SourceMapBlockCitation(BaseModel):
    """Which block cites a chunk and for what block type."""

    block_id: uuid.UUID
    block_type: LessonBlockType
    title: str | None = None
    order_index: int


class SourceMapItem(BaseModel):
    """One source chunk supporting a lesson."""

    chunk_id: uuid.UUID
    page_number: int | None = None
    document_index: int
    content: str
    cited_by: list[SourceMapBlockCitation] = Field(default_factory=list)


class LessonSourceMapRead(BaseModel):
    """Full provenance of a lesson back to the source material."""

    lesson_id: uuid.UUID
    sources: list[SourceMapItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class LessonReviewRequest(BaseModel):
    """A lecturer's decision on a generated lesson."""

    decision: Literal["approved", "rejected"]
    reviewer_name: str | None = Field(default=None, max_length=255)
    comments: str | None = None


class BlockReviewRequest(BaseModel):
    """A lecturer's decision on a single content block."""

    review_status: Literal["approved", "rejected"]
    comments: str | None = None


class GenerateWeekResponse(BaseModel):
    """Result of generating lessons for one weekly unit."""

    curriculum_unit_id: uuid.UUID
    generated: list[LessonRead] = Field(default_factory=list)
    skipped: list[dict] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)


class ContentGenerationRequest(BaseModel):
    """Request to bulk-generate lessons for every week of a curriculum."""

    rebuild_existing: bool = Field(
        default=False,
        description=(
            "Regenerate weeks that already have lessons. Leave False to only "
            "fill in missing weeks, which makes re-running cheap."
        ),
    )


class ContentGenerationRead(BaseModel):
    """Progress of a bulk lesson-generation run."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    curriculum_id: uuid.UUID
    status: str
    correlation_id: str
    total_weeks: int
    completed_weeks: int
    lessons_generated: int
    skipped_weeks: int
    failed_weeks: int
    rebuild_existing: bool
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ContentGenerationCreateResponse(BaseModel):
    """Response to a request to bulk-generate a curriculum's lessons.

    ``created`` is False when a run was already in flight and the existing
    job was returned instead.
    """

    job: ContentGenerationRead
    created: bool
