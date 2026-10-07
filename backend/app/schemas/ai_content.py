"""Pydantic schemas defining the LLM's structured course-content output.

These schemas are the contract with the AI provider for course content
generation (lessons, diagrams, activities, knowledge checks, external
resource candidates). Structured-output mode guarantees the response
conforms to this shape at the API level; no arbitrary LLM prose is
accepted.

External resource URLs are returned as *candidates* only — they are
HTTP-validated before being persisted (see
``app.services.course_content.resource_discovery``) precisely because an
LLM can hallucinate URLs. Video blocks are never produced by the LLM;
they come from the YouTube discovery service.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class SourceMarkersMixin(BaseModel):
    """Shared fields for every groundable generated unit."""

    source_chunk_markers: list[str] = Field(
        default_factory=list,
        description=(
            "Only the markers (e.g. 'C1', 'C3') genuinely supporting this "
            "item. Never invent or over-include; hallucinated markers are "
            "dropped before persistence."
        ),
    )


class GeneratedTextBlock(SourceMarkersMixin):
    """A paragraph/heading/example/summary block of lesson prose."""

    kind: str = Field(description="One of: 'heading', 'text', 'example', 'summary'.")
    title: str | None = Field(default=None, max_length=300)
    content: str = Field(min_length=1, max_length=6000)
    heading_level: int | None = Field(default=None, ge=2, le=3)


class GeneratedLesson(SourceMarkersMixin):
    """An entire generated lesson for one topic within a weekly unit."""

    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=3000)
    learning_objectives: list[str] = Field(default_factory=list)
    estimated_workload_minutes: int = Field(ge=0, le=10080)
    blocks: list[GeneratedTextBlock] = Field(default_factory=list)


class LessonGenerationResult(BaseModel):
    """A single generated lesson."""

    lesson: GeneratedLesson


class DiagramNode(BaseModel):
    """One node of a generated diagram."""

    id: str = Field(min_length=1, max_length=50)
    label: str = Field(min_length=1, max_length=200)


class DiagramEdge(BaseModel):
    """One directed edge of a generated diagram."""

    source: str = Field(min_length=1, max_length=50)
    target: str = Field(min_length=1, max_length=50)
    label: str | None = Field(default=None, max_length=150)


class GeneratedDiagram(SourceMarkersMixin):
    """A structured diagram definition rendered to Moodle-safe HTML later."""

    title: str = Field(min_length=1, max_length=300)
    diagram_type: str = Field(
        description="One of: 'flowchart', 'hierarchy', 'concept_map', 'comparison'."
    )
    caption: str = Field(min_length=1, max_length=500)
    nodes: list[DiagramNode] = Field(default_factory=list)
    edges: list[DiagramEdge] = Field(default_factory=list)


class DiagramGenerationResult(BaseModel):
    """Diagrams generated for a single lesson."""

    diagrams: list[GeneratedDiagram] = Field(default_factory=list)


class GeneratedKnowledgeCheck(SourceMarkersMixin):
    """A single multiple-choice knowledge check grounded in the lesson."""

    question: str = Field(min_length=1, max_length=1000)
    options: list[dict] = Field(default_factory=list)
    correct_option_id: str = Field(min_length=1, max_length=50)
    explanation: str = Field(min_length=1, max_length=1500)
    difficulty: str = Field(
        default="medium", description="One of: 'easy', 'medium', 'hard'."
    )


class KnowledgeCheckGenerationResult(BaseModel):
    """Knowledge checks generated for a single lesson."""

    checks: list[GeneratedKnowledgeCheck] = Field(default_factory=list)


class GeneratedActivity(SourceMarkersMixin):
    """A learning activity generated for one lesson."""

    kind: str = Field(
        description="One of: 'practice_exercise', 'project', 'discussion', 'research'."
    )
    title: str = Field(min_length=1, max_length=300)
    instructions: str = Field(min_length=1, max_length=4000)
    estimated_minutes: int = Field(ge=0, le=10080)


class ActivityGenerationResult(BaseModel):
    """Activities generated for a single lesson."""

    activities: list[GeneratedActivity] = Field(default_factory=list)


class GeneratedResourceCandidate(SourceMarkersMixin):
    """A candidate external resource whose URL has NOT yet been validated."""

    kind: str = Field(
        description="One of: 'article', 'documentation', 'tool', 'video_lesson'."
    )
    title: str = Field(min_length=1, max_length=300)
    url: str = Field(min_length=1, max_length=2000)
    description: str = Field(min_length=1, max_length=1000)
    why_recommended: str = Field(min_length=1, max_length=1000)


class ResourceCandidateResult(BaseModel):
    """External resource candidates proposed by the LLM for one lesson."""

    candidates: list[GeneratedResourceCandidate] = Field(default_factory=list)

    @field_validator("candidates")
    @classmethod
    def _limit_candidates(
        cls, value: list[GeneratedResourceCandidate]
    ) -> list[GeneratedResourceCandidate]:
        """Guard against a single over-large response by capping candidates."""
        return value[:10]
