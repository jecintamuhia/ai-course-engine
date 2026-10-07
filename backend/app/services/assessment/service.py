"""Assessment service: generate, retrieve, review, and align assessments.

An assessment is generated from the learning objectives of one weekly
unit (or of the whole course for a final assessment) and grounded in the
unit's actual textbook chunks — same grounding discipline as lessons, but
provenance per item is stored directly on the Assessment as
``source_chunk_markers`` (resolved chunk UUID strings) since there is no
separate join table.

Alignment is computed deterministically on generation: each assessment
item's declared ``learning_objective`` is matched back to the lesson(s)
that teach it, and the evidence list captures the lesson's activity /
knowledge-check blocks. This is what lets content-QA verify the course
teaches what it assesses.
"""

from __future__ import annotations

import uuid

from app.core.config import Settings
from app.core.exceptions import (
    AssessmentNotFound,
    CurriculumNotFound,
    CurriculumUnitNotFound,
    CurriculumValidationError,
)
from app.core.logging import get_logger
from app.db.repositories.assessments import AssessmentRepository
from app.db.repositories.chunks import ChunkRepository
from app.db.repositories.curriculum import CurriculumRepository
from app.db.repositories.lessons import LessonRepository
from app.models.assessment import (
    Assessment,
    AssessmentStatus,
    AssessmentType,
)
from app.models.lesson import Lesson
from app.schemas.ai_assessment import GeneratedAssessment
from app.schemas.assessment import (
    AssessmentAlignment,
    AssessmentItem,
)
from app.services.ai.base import LLMProvider
from app.services.assessment.generators import generate_assessment
from app.services.content_analysis.chunk_context import (
    build_marker_annotated_context,
    resolve_markers,
)
from app.services.course_content.context import collect_unit_chunk_ids

logger = get_logger(__name__)

_DEFAULT_UNIT_TYPE = AssessmentType.WEEKLY_QUIZ


class AssessmentService:
    """Coordinates assessment generation, retrieval, and review."""

    def __init__(
        self,
        curriculum_repository: CurriculumRepository,
        assessment_repository: AssessmentRepository,
        chunk_repository: ChunkRepository,
        lesson_repository: LessonRepository,
        provider: LLMProvider,
        settings: Settings,
    ) -> None:
        self._curriculum_repository = curriculum_repository
        self._assessment_repository = assessment_repository
        self._chunk_repository = chunk_repository
        self._lesson_repository = lesson_repository
        self._provider = provider
        self._settings = settings

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    async def generate_for_unit(
        self,
        curriculum_id: uuid.UUID,
        unit_id: uuid.UUID,
        *,
        assessment_type: AssessmentType | None = None,
        max_items: int = 6,
    ) -> Assessment:
        """Generate an assessment for one weekly unit's objectives."""
        curriculum = await self._curriculum_repository.get_by_id(curriculum_id)
        if curriculum is None:
            raise CurriculumNotFound(f"Curriculum {curriculum_id} was not found.")

        unit = await self._curriculum_repository.get_unit_with_lesson_context(unit_id)
        if unit is None or unit.curriculum_id != curriculum_id:
            raise CurriculumUnitNotFound(f"Unit {unit_id} was not found.")

        if not unit.learning_objectives:
            raise CurriculumValidationError(
                f"Unit {unit.title!r} (week {unit.week_number}) has no "
                "learning objectives; an assessment cannot be aligned to it."
            )

        chunks = await self._chunk_repository.get_by_ids(collect_unit_chunk_ids(unit))
        annotated_text, marker_map = build_marker_annotated_context(
            chunks, max_chars=self._settings.ai_max_context_chars
        )

        assessment_type = assessment_type or _DEFAULT_UNIT_TYPE

        result = await generate_assessment(
            self._provider,
            self._settings,
            assessment_type=assessment_type,
            unit_title=unit.title,
            week_number=unit.week_number,
            learning_objectives=list(unit.learning_objectives),
            annotated_text=annotated_text,
            max_items=max_items,
        )

        unit_lessons = await self._lesson_repository.list_by_unit(unit.id)
        alignment = self._build_alignment(result, unit_lessons)

        assessment = Assessment(
            curriculum_id=curriculum_id,
            curriculum_unit_id=unit.id,
            week_number=unit.week_number,
            title=result.title,
            description=result.description,
            assessment_type=assessment_type,
            learning_objectives=list(unit.learning_objectives),
            estimated_minutes=result.estimated_minutes,
            items=[item.model_dump(mode="json") for item in result.items],
            alignment=[a.model_dump(mode="json") for a in alignment],
            status=AssessmentStatus.AWAITING_REVIEW,
            source_chunk_markers=self._collect_markers(result, marker_map),
        )
        await self._assessment_repository.add(assessment)
        await self._assessment_repository.commit()

        logger.info(
            "Assessment generated curriculum_id=%s unit_id=%s type=%s items=%s",
            curriculum_id,
            unit_id,
            assessment_type.value,
            len(result.items),
        )
        return assessment

    async def generate_final(
        self,
        curriculum_id: uuid.UUID,
        *,
        max_items: int = 12,
    ) -> Assessment:
        """Generate a comprehensive final assessment for the whole course."""
        curriculum = await self._curriculum_repository.get_by_id_for_content(
            curriculum_id
        )
        if curriculum is None:
            raise CurriculumNotFound(f"Curriculum {curriculum_id} was not found.")

        objectives: list[str] = []
        for unit in curriculum.units:
            for objective in unit.learning_objectives:
                if objective not in objectives:
                    objectives.append(objective)
        if not objectives:
            raise CurriculumValidationError(
                "The curriculum has no learning objectives; a final "
                "assessment cannot be aligned to it."
            )

        chunk_ids: list[uuid.UUID] = []
        for unit in curriculum.units:
            for chunk_id in collect_unit_chunk_ids(unit):
                if chunk_id not in chunk_ids:
                    chunk_ids.append(chunk_id)

        chunks = await self._chunk_repository.get_by_ids(chunk_ids)
        annotated_text, marker_map = build_marker_annotated_context(
            chunks, max_chars=self._settings.ai_max_context_chars
        )

        result = await generate_assessment(
            self._provider,
            self._settings,
            assessment_type=AssessmentType.FINAL,
            unit_title=curriculum.title,
            week_number=None,
            learning_objectives=objectives,
            annotated_text=annotated_text,
            max_items=max_items,
        )

        course_lessons = await self._lesson_repository.list_by_curriculum(curriculum_id)
        alignment = self._build_alignment(result, course_lessons)

        assessment = Assessment(
            curriculum_id=curriculum_id,
            curriculum_unit_id=None,
            week_number=None,
            title=result.title,
            description=result.description,
            assessment_type=AssessmentType.FINAL,
            learning_objectives=objectives,
            estimated_minutes=result.estimated_minutes,
            items=[item.model_dump(mode="json") for item in result.items],
            alignment=[a.model_dump(mode="json") for a in alignment],
            status=AssessmentStatus.AWAITING_REVIEW,
            source_chunk_markers=self._collect_markers(result, marker_map),
        )
        await self._assessment_repository.add(assessment)
        await self._assessment_repository.commit()

        logger.info(
            "Final assessment generated curriculum_id=%s items=%s objectives=%s",
            curriculum_id,
            len(result.items),
            len(objectives),
        )
        return assessment

    def _build_alignment(
        self, result: GeneratedAssessment, lessons: list[Lesson]
    ) -> list[AssessmentAlignment]:
        """Map each item's objective to the lessons that teach it."""
        alignment: list[AssessmentAlignment] = []
        for item in result.items:
            lesson = _find_teaching_lesson(item, lessons)
            alignment.append(
                AssessmentAlignment(
                    learning_objective=item.learning_objective,
                    lesson_id=lesson.id if lesson else None,
                    lesson_title=lesson.title if lesson else None,
                    unit_week=lesson.week_number if lesson else None,
                    evidence=_evidence_for(lesson),
                )
            )
        return alignment

    def _collect_markers(
        self, result: GeneratedAssessment, marker_map: dict[str, uuid.UUID]
    ) -> list[str]:
        """Resolve per-item chunk markers into persisted chunk UUID strings."""
        resolved: list[uuid.UUID] = []
        for item in result.items:
            chunk_ids, dropped_markers = resolve_markers(
                list(item.source_chunk_markers), marker_map
            )
            if dropped_markers:
                logger.warning("Assessment markers dropped markers=%s", dropped_markers)
            for chunk_id in chunk_ids:
                if chunk_id not in resolved:
                    resolved.append(chunk_id)
        return [str(chunk_id) for chunk_id in resolved]

    # ------------------------------------------------------------------
    # Retrieval / review
    # ------------------------------------------------------------------

    async def get_by_id(
        self, assessment_id: uuid.UUID, curriculum_id: uuid.UUID | None = None
    ) -> Assessment:
        assessment = await self._assessment_repository.get_by_id(assessment_id)
        if assessment is None:
            raise AssessmentNotFound(f"Assessment {assessment_id} was not found.")
        if curriculum_id is not None and assessment.curriculum_id != curriculum_id:
            raise AssessmentNotFound(
                f"Assessment {assessment_id} does not belong to curriculum "
                f"{curriculum_id}."
            )
        return assessment

    async def list_by_curriculum(self, curriculum_id: uuid.UUID) -> list[Assessment]:
        return await self._assessment_repository.list_by_curriculum(curriculum_id)

    async def list_by_unit(self, curriculum_unit_id: uuid.UUID) -> list[Assessment]:
        return await self._assessment_repository.list_by_unit(curriculum_unit_id)

    async def review(
        self,
        assessment_id: uuid.UUID,
        *,
        decision: str,
        reviewer_name: str | None,
        comments: str | None,
    ) -> Assessment:
        assessment = await self.get_by_id(assessment_id)

        if assessment.status == AssessmentStatus.APPROVED and decision == "approved":
            return assessment
        if assessment.status == AssessmentStatus.APPROVED and decision == "rejected":
            raise CurriculumValidationError(
                "An approved assessment must be regenerated before it can "
                "be rejected again."
            )

        if decision == "approved":
            assessment.status = AssessmentStatus.APPROVED
        else:
            assessment.status = AssessmentStatus.REJECTED
        assessment.reviewer_name = reviewer_name
        assessment.review_comments = comments

        await self._assessment_repository.commit()
        return assessment


def _find_teaching_lesson(item: AssessmentItem, lessons: list[Lesson]) -> Lesson | None:
    """Return the lesson whose objectives cover the item's objective."""
    objective = item.learning_objective.strip().lower()
    best: Lesson | None = None
    best_score = 0
    for lesson in lessons:
        score = 0
        for declared in lesson.learning_objectives:
            if declared.strip().lower() == objective:
                score = 3
                break
            if (
                objective in declared.strip().lower()
                or declared.strip().lower() in objective
            ):
                score = max(score, 1)
        if score > best_score:
            best_score = score
            best = lesson
    return best


def _evidence_for(lesson: Lesson | None) -> list[str]:
    """Titles of the lesson's activity / knowledge check blocks."""
    if lesson is None:
        return []
    evidence: list[str] = []
    for block in lesson.content_blocks:
        if block.block_type.value in ("activity", "knowledge_check") and block.title:
            evidence.append(block.title)
    return evidence
