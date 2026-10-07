"""Pydantic schemas defining the LLM's structured extraction output.

These schemas are the contract with the AI provider — OpenAI's
structured outputs mode guarantees the response conforms to this shape
at the API level. No arbitrary LLM prose is ever accepted.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedConcept(BaseModel):
    """A single concept identified within a topic."""

    name: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=2000)
    definition: str | None = Field(default=None, max_length=2000)
    terminology: list[str] = Field(default_factory=list)
    procedures: list[str] = Field(default_factory=list)
    formulas: list[str] = Field(default_factory=list)
    worked_examples: list[dict[str, str]] = Field(default_factory=list)
    exercises: list[dict[str, str]] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    provenance: list[dict[str, str]] = Field(default_factory=list)


class ExtractedTopic(BaseModel):
    """A topic (or subtopic, via nesting) extracted from source content."""

    title: str = Field(min_length=1, max_length=300)
    learning_objectives: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    concepts: list[ExtractedConcept] = Field(default_factory=list)
    difficulty: int = Field(ge=1, le=5)
    estimated_workload_minutes: int = Field(ge=0, le=10080)
    source_chunk_markers: list[str] = Field(default_factory=list)
    subtopics: list[ExtractedTopic] = Field(default_factory=list)


class TopicExtractionResult(BaseModel):
    """Full extraction result for one unit of source content (a chapter)."""

    topics: list[ExtractedTopic] = Field(default_factory=list)


class PrerequisiteLink(BaseModel):
    """
    One topic's cross-chapter prerequisites, named by exact title.

    Produced by the second (linking) pass, which sees the whole document's
    real topic titles at once — something per-chapter extraction can never
    do, because the other chapters' topics do not exist yet when it runs.
    """

    topic: str = Field(min_length=1, max_length=300)
    prerequisites: list[str] = Field(default_factory=list)


class PrerequisiteLinkResult(BaseModel):
    """Result of the document-wide prerequisite linking pass."""

    links: list[PrerequisiteLink] = Field(default_factory=list)
