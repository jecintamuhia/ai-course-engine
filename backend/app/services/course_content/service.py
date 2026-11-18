"""Course content service: orchestrates AI-assisted lesson generation.

The service follows the same transaction discipline as topic extraction:
read-only loading happens first and the read transaction is closed
*before* any LLM call, so no DB connection is held open across provider
waits. Content is only persisted after every external call for a lesson.

Per-component failures (a diagram that failed to generate, a resource URL
that failed validation, video discovery disabled or unreachable) are
recorded on the lesson's ``generation_errors`` so the lecturer can see
exactly what was and was not generated — the service never fabricates
content to fill a gap.
"""

from __future__ import annotations

import uuid

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    AIOutputValidationError,
    AIProviderError,
    CurriculumUnitNotFound,
    InvalidStateTransition,
    LessonContentBlockNotFound,
    LessonNotFound,
)
from app.core.logging import get_logger
from app.db.repositories.chunks import ChunkRepository
from app.db.repositories.curriculum import CurriculumRepository
from app.db.repositories.dependencies import DependencyRepository
from app.db.repositories.lessons import LessonRepository
from app.models.lesson import Lesson, LessonStatus
from app.models.lesson_content_block import (
    BlockReviewStatus,
    LessonBlockType,
    LessonContentBlock,
)
from app.models.lesson_source_chunk import LessonSourceChunk
from app.schemas.ai_content import (
    ActivityGenerationResult,
    DiagramGenerationResult,
    GeneratedActivity,
    GeneratedDiagram,
    GeneratedKnowledgeCheck,
    GeneratedPracticalTask,
    KnowledgeCheckGenerationResult,
    LessonGenerationResult,
    PracticalTaskGenerationResult,
    ResourceCandidateResult,
)
from app.schemas.course_content import (
    ActivityPayload,
    DiagramBlockPayload,
    DiagramEdgePayload,
    DiagramNodePayload,
    ExampleBlockPayload,
    ExternalResourcePayload,
    HeadingBlockPayload,
    KnowledgeCheckOptionPayload,
    KnowledgeCheckPayload,
    LessonSourceMapRead,
    PracticalTaskPayload,
    SourceMapBlockCitation,
    SourceMapItem,
    SummaryBlockPayload,
    TextBlockPayload,
    VideoPayload,
)
from app.services.ai.base import LLMProvider
from app.services.content_analysis.chunk_context import (
    build_marker_annotated_context,
    resolve_markers,
)
from app.services.course_content.context import (
    LessonContext,
    build_unit_lesson_contexts,
    collect_unit_chunk_ids,
)
from app.services.course_content.generators import (
    _usable_steps,
    generate_activities,
    generate_diagrams,
    generate_knowledge_checks,
    generate_lesson,
    generate_practical_tasks,
    propose_resource_candidates,
)
from app.services.course_content.resource_discovery import (
    validate_resource_candidates,
)
from app.services.course_content.video_discovery import discover_videos
from pydantic import ValidationError

logger = get_logger(__name__)

_ERROR_KEY = "course_content"


class CourseContentService:
    """Coordinates generation, review, and retrieval of course lessons."""

    def __init__(
        self,
        curriculum_repository: CurriculumRepository,
        chunk_repository: ChunkRepository,
        lesson_repository: LessonRepository,
        llm_provider: LLMProvider,
        settings: Settings | None = None,
        dependency_repository: DependencyRepository | None = None,
    ) -> None:
        self._curriculum_repository = curriculum_repository
        self._chunk_repository = chunk_repository
        self._lesson_repository = lesson_repository
        self._llm_provider = llm_provider
        self._settings = settings or get_settings()
        self._dependency_repository = dependency_repository

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    async def generate_week(
        self,
        curriculum_unit_id: uuid.UUID,
        *,
        preserve_existing: bool = False,
    ) -> dict[str, list]:
        """
        Generate lessons for one weekly unit of an approved curriculum.

          One lesson is generated per planned topic (bounded by
          ``CONTENT_MAX_LESSONS_PER_WEEK``). In resume mode, existing lessons
          are preserved and only topics without a lesson are generated.
          Explicit rebuild mode retains the approved-lesson protection.

        Returns ``{generated, skipped, errors}`` where ``skipped`` lists
        topics with no source grounding (never fabricated) and ``errors``
        lists topics whose lesson generation itself failed.
        """
        unit = await self._curriculum_repository.get_unit_with_lesson_context(
            curriculum_unit_id
        )
        if unit is None:
            raise CurriculumUnitNotFound(
                f"Curriculum unit {curriculum_unit_id} was not found."
            )

        existing = await self._lesson_repository.list_by_unit(curriculum_unit_id)
        preserved_topic_ids = {
            lesson.topic_id
            for lesson in existing
            if lesson.topic_id
            and (
                preserve_existing or lesson.status == LessonStatus.APPROVED
            )
        }

        chunk_ids = collect_unit_chunk_ids(unit)
        chunks = await self._chunk_repository.get_by_ids(chunk_ids)
        topic_ids = [
            link.topic.id
            for link in unit.topic_links
            if link.topic is not None
        ]
        prerequisites = (
            await self._dependency_repository.prerequisite_titles_by_topic(topic_ids)
            if self._dependency_repository is not None
            else {}
        )

        # Close the read transaction before any external (LLM/HTTP) call.
        await self._chunk_repository.commit()

        chunks_by_id = {chunk.id: chunk for chunk in chunks}
        contexts = build_unit_lesson_contexts(
            unit,
            chunks_by_id=chunks_by_id,
            max_chars=self._settings.ai_max_context_chars,
            max_lessons=self._settings.content_max_lessons_per_week,
            prerequisite_topics_by_topic_id=prerequisites,
        )

        generated: list[Lesson] = []
        errors: list[dict] = []
        skipped: list[dict] = []

        for context in contexts:
            if context.topic_id in preserved_topic_ids:
                skipped.append(
                    {
                        "topic_id": str(context.topic_id),
                        "topic_title": context.topic_title,
                        "reason": (
                            "A lesson already exists for this topic and was "
                            "preserved."
                        ),
                    }
                )
                continue
            if not context.annotated_text.strip():
                skipped.append(
                    {
                        "topic_id": str(context.topic_id),
                        "topic_title": context.topic_title,
                        "reason": (
                            "No source chunks support this topic; content was "
                            "not fabricated."
                        ),
                    }
                )
                continue

            lesson, failure = await self._generate_single_lesson(
                context, unit_title=unit.title
            )
            if lesson is not None:
                generated.append(lesson)
            else:
                errors.append(
                    {
                        "topic_id": str(context.topic_id),
                        "topic_title": context.topic_title,
                        "error": failure,
                    }
                )

        if not contexts:
            skipped.append(
                {
                    "topic_id": None,
                    "topic_title": unit.title,
                    "reason": "No planned topics in this unit.",
                }
            )

        if not preserve_existing:
            regenerated_topic_ids = {
                lesson.topic_id for lesson in generated if lesson.topic_id is not None
            }
            await self._lesson_repository.delete_not_approved_by_topics(
                curriculum_unit_id, regenerated_topic_ids
            )
        for lesson in generated:
            await self._lesson_repository.add(lesson)
            await self._lesson_repository.add_source_links(
                _dedupe_links(list(lesson.source_chunk_links))
            )
        await self._lesson_repository.commit()

        return {
            "generated": generated,
            "skipped": skipped,
            "errors": errors,
        }

    async def _generate_single_lesson(
        self, context: LessonContext, *, unit_title: str
    ) -> tuple[Lesson | None, str | None]:
        """
        Run every generator for one lesson context and build the Lesson
        ORM graph. Returns (lesson, None) on success — even with recorded
        per-component errors — and (None, error) when the core lesson
        generation itself failed.
        """
        settings = self._settings
        component_errors: list[dict] = []

        try:
            result = await generate_lesson(
                self._llm_provider,
                settings,
                topic_title=context.topic_title,
                learning_objectives=context.learning_objectives,
                week_title=unit_title,
                annotated_text=context.annotated_text,
                max_objectives=4,
                content_level=context.content_level,
                concept_names=context.concept_descriptions,
                prerequisite_topics=context.prerequisite_topics,
                neighboring_topics=context.neighboring_topics,
                week_number=context.week_number,
                lesson_position=context.order_index + 1,
            )
        except (AIProviderError, AIOutputValidationError, ValidationError) as exc:
            logger.warning(
                "Lesson generation failed topic=%r error=%s",
                context.topic_title,
                exc,
            )
            return None, str(exc)

        lesson = Lesson(
            curriculum_id=context.curriculum_id,
            curriculum_unit_id=context.curriculum_unit_id,
            topic_id=context.topic_id,
            week_number=context.week_number,
            order_index=context.order_index,
            title=result.lesson.title,
            description=result.lesson.description,
            learning_objectives=list(result.lesson.learning_objectives),
            estimated_workload_minutes=result.lesson.estimated_workload_minutes,
            status=LessonStatus.AWAITING_REVIEW,
            generation_errors=[],
        )

        block_index = 0
        blocks: list[LessonContentBlock] = []
        block_index = self._build_text_blocks(
            result, context, lesson=lesson, blocks=blocks, start_index=block_index
        )

        try:
            diagrams = await generate_diagrams(
                self._llm_provider,
                settings,
                lesson_title=lesson.title,
                annotated_text=context.annotated_text,
                max_diagrams=settings.content_max_diagrams,
            )
            block_index = self._append_diagram_blocks(
                diagrams, context, lesson, blocks, block_index
            )
        except (AIProviderError, AIOutputValidationError, ValidationError) as exc:
            component_errors.append({"component": "diagrams", "error": str(exc)})

        try:
            checks = await generate_knowledge_checks(
                self._llm_provider,
                settings,
                lesson_title=lesson.title,
                annotated_text=context.annotated_text,
                max_checks=settings.content_max_knowledge_checks,
            )
            block_index = self._append_knowledge_check_blocks(
                checks, context, lesson, blocks, block_index
            )
        except (AIProviderError, AIOutputValidationError, ValidationError) as exc:
            component_errors.append(
                {"component": "knowledge_checks", "error": str(exc)}
            )

        try:
            activities = await generate_activities(
                self._llm_provider,
                settings,
                lesson_title=lesson.title,
                annotated_text=context.annotated_text,
                max_activities=settings.content_max_activities,
            )
            block_index = self._append_activity_blocks(
                activities, context, lesson, blocks, block_index
            )
        except (AIProviderError, AIOutputValidationError, ValidationError) as exc:
            component_errors.append({"component": "activities", "error": str(exc)})

        if settings.content_max_practical_tasks > 0:
            try:
                practical_tasks = await generate_practical_tasks(
                    self._llm_provider,
                    settings,
                    lesson_title=lesson.title,
                    annotated_text=context.annotated_text,
                    max_tasks=settings.content_max_practical_tasks,
                )
                block_index = self._append_practical_task_blocks(
                    practical_tasks, context, lesson, blocks, block_index
                )
            except (
                AIProviderError,
                AIOutputValidationError,
                ValidationError,
            ) as exc:
                component_errors.append(
                    {"component": "practical_tasks", "error": str(exc)}
                )

        try:
            candidates = await propose_resource_candidates(
                self._llm_provider,
                settings,
                lesson_title=lesson.title,
                annotated_text=context.annotated_text,
                max_resources=settings.content_max_resources,
            )
            validated, dropped = await validate_resource_candidates(
                candidates.candidates,
                timeout_seconds=settings.content_resource_timeout_seconds,
            )
            for reason in dropped:
                component_errors.append(
                    {"component": "external_resources", "error": reason}
                )
            if validated:
                block_index = self._append_resource_blocks(
                    validated, context, lesson, blocks, block_index
                )
        except (AIProviderError, AIOutputValidationError, ValidationError) as exc:
            component_errors.append(
                {"component": "external_resources", "error": str(exc)}
            )

        video_result = await discover_videos(
            query=f"{lesson.title} {context.topic_title}",
            api_key=settings.youtube_api_key.get_secret_value(),
            max_results=1,
            timeout_seconds=settings.content_resource_timeout_seconds,
        )
        if video_result.disabled:
            component_errors.append(
                {
                    "component": "videos",
                    "error": video_result.error or "Disabled.",
                }
            )
        elif video_result.error:
            component_errors.append(
                {"component": "videos", "error": video_result.error}
            )
        elif video_result.videos:
            block_index = self._append_video_blocks(
                video_result.videos, lesson, blocks, block_index
            )

        lesson.content_blocks = blocks
        lesson.source_chunk_links = _dedupe_links(
            LessonSourceChunk(lesson_id=lesson.id, chunk_id=chunk_id)
            for block in blocks
            for chunk_id in _resolved_payload_chunk_ids(block)
        )
        lesson.generation_errors = component_errors
        return lesson, None

    # ------------------------------------------------------------------
    # Block assembly helpers
    # ------------------------------------------------------------------

    def _build_text_blocks(
        self,
        result: LessonGenerationResult,
        context: LessonContext,
        *,
        lesson: Lesson,
        blocks: list[LessonContentBlock],
        start_index: int,
    ) -> int:
        """Map the LLM lesson blocks to persisted content blocks."""
        index = start_index
        for llm_block in result.lesson.blocks:
            kind = llm_block.kind
            markers = _resolved(
                list(llm_block.source_chunk_markers), context.marker_map
            )
            if kind == "heading" and len(llm_block.content) > 300:
                # Preserve the full source-grounded text in the prose payload,
                # whose length limit supports paragraphs and explanations.
                kind = "text"
            if kind == "heading":
                payload = HeadingBlockPayload(
                    level=llm_block.heading_level or 2,
                    text=llm_block.content,
                    source_chunk_markers=markers,
                )
            elif kind == "text":
                payload = TextBlockPayload(
                    content=llm_block.content,
                    source_chunk_markers=markers,
                )
            elif llm_block.kind == "example":
                payload = ExampleBlockPayload(
                    title=llm_block.title or "Example",
                    content=llm_block.content,
                    source_chunk_markers=markers,
                )
            else:
                payload = SummaryBlockPayload(
                    content=llm_block.content,
                    source_chunk_markers=markers,
                )
            blocks.append(
                _block(
                    lesson_id=lesson.id,
                    block_type=_text_block_type(kind),
                    order_index=index,
                    title=llm_block.title,
                    payload=payload.model_dump(mode="json"),
                )
            )
            index += 1
        return index

    def _append_diagram_blocks(
        self,
        result: DiagramGenerationResult,
        context: LessonContext,
        lesson: Lesson,
        blocks: list[LessonContentBlock],
        start_index: int,
    ) -> int:
        index = start_index
        for diagram in result.diagrams:
            blocks.append(
                _block(
                    lesson_id=lesson.id,
                    block_type=LessonBlockType.DIAGRAM,
                    order_index=index,
                    title=diagram.title,
                    payload=DiagramBlockPayload(
                        diagram_type=_safe_diagram_type(diagram.diagram_type),
                        caption=diagram.caption,
                        nodes=[
                            DiagramNodePayload(id=n.id, label=n.label)
                            for n in diagram.nodes
                        ],
                        edges=[
                            DiagramEdgePayload(
                                source=e.source,
                                target=e.target,
                                label=e.label,
                            )
                            for e in diagram.edges
                        ],
                        source_chunk_markers=_resolved(
                            list(diagram.source_chunk_markers), context.marker_map
                        ),
                    ).model_dump(mode="json"),
                )
            )
            index += 1
        return index

    def _append_knowledge_check_blocks(
        self,
        result: KnowledgeCheckGenerationResult,
        context: LessonContext,
        lesson: Lesson,
        blocks: list[LessonContentBlock],
        start_index: int,
    ) -> int:
        index = start_index
        for check in result.checks:
            blocks.append(
                _block(
                    lesson_id=lesson.id,
                    block_type=LessonBlockType.KNOWLEDGE_CHECK,
                    order_index=index,
                    title=None,
                    payload=KnowledgeCheckPayload(
                        question=check.question,
                        options=[
                            KnowledgeCheckOptionPayload(id=o.id, text=o.text)
                            for o in check.options
                        ],
                        correct_option_id=check.correct_option_id,
                        explanation=check.explanation,
                        difficulty=_safe_difficulty(check.difficulty),
                        source_chunk_markers=_resolved(
                            list(check.source_chunk_markers), context.marker_map
                        ),
                    ).model_dump(mode="json"),
                )
            )
            index += 1
        return index

    def _append_activity_blocks(
        self,
        result: ActivityGenerationResult,
        context: LessonContext,
        lesson: Lesson,
        blocks: list[LessonContentBlock],
        start_index: int,
    ) -> int:
        index = start_index
        for activity in result.activities:
            blocks.append(
                _block(
                    lesson_id=lesson.id,
                    block_type=LessonBlockType.ACTIVITY,
                    order_index=index,
                    title=activity.title,
                    payload=ActivityPayload(
                        kind=_safe_activity_kind(activity.kind),
                        title=activity.title,
                        instructions=activity.instructions,
                        estimated_minutes=activity.estimated_minutes,
                        source_chunk_markers=_resolved(
                            list(activity.source_chunk_markers), context.marker_map
                        ),
                    ).model_dump(mode="json"),
                )
            )
            index += 1
        return index

    def _append_practical_task_blocks(
        self,
        result: PracticalTaskGenerationResult,
        context: LessonContext,
        lesson: Lesson,
        blocks: list[LessonContentBlock],
        start_index: int,
    ) -> int:
        index = start_index
        for task in result.tasks:
            blocks.append(
                _block(
                    lesson_id=lesson.id,
                    block_type=LessonBlockType.PRACTICAL_TASK,
                    order_index=index,
                    title=task.title,
                    payload=PracticalTaskPayload(
                        brief=task.brief,
                        scenario=task.scenario,
                        steps=_usable_steps(list(task.steps)),
                        deliverable=task.deliverable,
                        evidence=task.evidence,
                        difficulty=_safe_difficulty(task.difficulty),
                        estimated_minutes=task.estimated_minutes,
                        source_chunk_markers=_resolved(
                            list(task.source_chunk_markers), context.marker_map
                        ),
                    ).model_dump(mode="json"),
                )
            )
            index += 1
        return index

    def _append_resource_blocks(
        self,
        resources: list[ExternalResourcePayload],
        context: LessonContext,
        lesson: Lesson,
        blocks: list[LessonContentBlock],
        start_index: int,
    ) -> int:
        index = start_index
        for resource in resources:
            resource.source_chunk_markers = _resolved(
                list(resource.source_chunk_markers), context.marker_map
            )
            blocks.append(
                _block(
                    lesson_id=lesson.id,
                    block_type=LessonBlockType.EXTERNAL_RESOURCE,
                    order_index=index,
                    title=resource.title,
                    payload=resource.model_dump(mode="json"),
                )
            )
            index += 1
        return index

    def _append_video_blocks(
        self,
        videos: list[VideoPayload],
        lesson: Lesson,
        blocks: list[LessonContentBlock],
        start_index: int,
    ) -> int:
        index = start_index
        for video in videos:
            blocks.append(
                _block(
                    lesson_id=lesson.id,
                    block_type=LessonBlockType.VIDEO,
                    order_index=index,
                    title=video.title,
                    payload=video.model_dump(mode="json"),
                )
            )
            index += 1
        return index

    # ------------------------------------------------------------------
    # Lesson-level operations
    # ------------------------------------------------------------------

    async def list_lessons(self, curriculum_unit_id: uuid.UUID) -> list[Lesson]:
        """Return the lessons for a weekly unit, in reading order."""
        return await self._lesson_repository.list_by_unit(curriculum_unit_id)

    async def get_lesson(self, lesson_id: uuid.UUID) -> Lesson:
        """Fetch a lesson by id with its blocks."""
        lesson = await self._lesson_repository.get_by_id(lesson_id)
        if lesson is None:
            raise LessonNotFound(f"Lesson {lesson_id} was not found.")
        return lesson

    async def submit_for_review(self, lesson_id: uuid.UUID) -> Lesson:
        """Move a non-approved lesson into the lecturer review queue."""
        lesson = await self.get_lesson(lesson_id)
        if lesson.status not in (
            LessonStatus.DRAFT,
            LessonStatus.FAILED,
            LessonStatus.GENERATING,
        ):
            raise InvalidStateTransition(
                f"Lesson is {lesson.status.value} and cannot be submitted for review."
            )
        lesson.status = LessonStatus.AWAITING_REVIEW
        await self._lesson_repository.commit()
        return lesson

    async def review_lesson(
        self,
        lesson_id: uuid.UUID,
        *,
        decision: str,
        reviewer_name: str | None = None,
        comments: str | None = None,
    ) -> Lesson:
        """Record a lecturer decision on a lesson."""
        lesson = await self.get_lesson(lesson_id)
        if lesson.status != LessonStatus.AWAITING_REVIEW:
            raise InvalidStateTransition(
                f"Lesson is {lesson.status.value}; only AWAITING_REVIEW "
                "lessons can be reviewed."
            )
        lesson.status = (
            LessonStatus.APPROVED if decision == "approved" else LessonStatus.REJECTED
        )
        lesson.reviewer_name = reviewer_name
        lesson.review_comments = comments
        await self._lesson_repository.commit()
        logger.info(
            "Lesson reviewed lesson_id=%s decision=%s reviewer=%s",
            lesson_id,
            decision,
            reviewer_name,
        )
        return lesson

    async def review_block(
        self,
        block_id: uuid.UUID,
        *,
        review_status: str,
        comments: str | None = None,
    ) -> LessonContentBlock:
        """Record a lecturer decision on a single content block."""
        block = await self._lesson_repository.get_block_by_id(block_id)
        if block is None:
            raise LessonContentBlockNotFound(
                f"Lesson content block {block_id} was not found."
            )
        block.review_status = (
            BlockReviewStatus.APPROVED
            if review_status == "approved"
            else BlockReviewStatus.REJECTED
        )
        block.review_comments = comments
        await self._lesson_repository.commit()
        return block

    async def delete_block(self, block_id: uuid.UUID) -> None:
        """Delete a single content block."""
        block = await self._lesson_repository.get_block_by_id(block_id)
        if block is None:
            raise LessonContentBlockNotFound(
                f"Lesson content block {block_id} was not found."
            )
        await self._lesson_repository.delete_block(block)
        await self._lesson_repository.commit()

    # ------------------------------------------------------------------
    # Regeneration of a single block
    # ------------------------------------------------------------------

    async def regenerate_block(self, block_id: uuid.UUID) -> LessonContentBlock:
        """
        Regenerate a single content block using the lesson's own source
        grounding. Supports diagram, knowledge_check, activity,
        practical_task, external_resource, and video blocks; the prose
        block kinds (text/heading/example/summary) are regenerated as part
        of the full lesson and raise here.
        """
        block = await self._lesson_repository.get_block_by_id(block_id)
        if block is None:
            raise LessonContentBlockNotFound(
                f"Lesson content block {block_id} was not found."
            )
        if block.block_type in (
            LessonBlockType.TEXT,
            LessonBlockType.HEADING,
            LessonBlockType.EXAMPLE,
            LessonBlockType.SUMMARY,
        ):
            raise AIOutputValidationError(
                f"{block.block_type.value} blocks are generated as part of "
                "the full lesson; regenerate the lesson instead."
            )

        lesson = await self.get_lesson(block.lesson_id)
        chunks = await self._chunk_repository.get_by_ids(
            [link.chunk_id for link in lesson.source_chunk_links]
        )
        annotated_text, marker_map = build_marker_annotated_context(
            chunks, max_chars=self._settings.ai_max_context_chars
        )
        await self._chunk_repository.commit()

        new_title, new_payload = await self._regenerate_single(
            block.block_type,
            lesson,
            annotated_text,
            marker_map,
        )
        block.title = new_title
        block.payload = new_payload
        block.review_status = BlockReviewStatus.GENERATED
        block.review_comments = None
        await self._lesson_repository.commit()
        return block

    async def _regenerate_single(
        self,
        block_type: LessonBlockType,
        lesson: Lesson,
        annotated_text: str,
        marker_map: dict[str, uuid.UUID],
    ) -> tuple[str | None, dict]:
        """Regenerate one block of a given type (title, payload)."""
        settings = self._settings

        if block_type == LessonBlockType.DIAGRAM:
            result: DiagramGenerationResult = await generate_diagrams(
                self._llm_provider,
                settings,
                lesson_title=lesson.title,
                annotated_text=annotated_text,
                max_diagrams=1,
            )
            if not result.diagrams:
                raise AIOutputValidationError("Diagram generator returned no diagrams.")
            diagram: GeneratedDiagram = result.diagrams[0]
            return (
                diagram.title,
                DiagramBlockPayload(
                    diagram_type=_safe_diagram_type(diagram.diagram_type),
                    caption=diagram.caption,
                    nodes=[
                        DiagramNodePayload(id=n.id, label=n.label)
                        for n in diagram.nodes
                    ],
                    edges=[
                        DiagramEdgePayload(
                            source=e.source, target=e.target, label=e.label
                        )
                        for e in diagram.edges
                    ],
                    source_chunk_markers=_resolved(
                        list(diagram.source_chunk_markers), marker_map
                    ),
                ).model_dump(mode="json"),
            )

        if block_type == LessonBlockType.KNOWLEDGE_CHECK:
            checks: KnowledgeCheckGenerationResult = await generate_knowledge_checks(
                self._llm_provider,
                settings,
                lesson_title=lesson.title,
                annotated_text=annotated_text,
                max_checks=1,
            )
            if not checks.checks:
                raise AIOutputValidationError(
                    "Knowledge-check generator returned none."
                )
            check: GeneratedKnowledgeCheck = checks.checks[0]
            return (
                None,
                KnowledgeCheckPayload(
                    question=check.question,
                    options=[
                        KnowledgeCheckOptionPayload(id=o.id, text=o.text)
                        for o in check.options
                    ],
                    correct_option_id=check.correct_option_id,
                    explanation=check.explanation,
                    difficulty=_safe_difficulty(check.difficulty),
                    source_chunk_markers=_resolved(
                        list(check.source_chunk_markers), marker_map
                    ),
                ).model_dump(mode="json"),
            )

        if block_type == LessonBlockType.ACTIVITY:
            acts: ActivityGenerationResult = await generate_activities(
                self._llm_provider,
                settings,
                lesson_title=lesson.title,
                annotated_text=annotated_text,
                max_activities=1,
            )
            if not acts.activities:
                raise AIOutputValidationError("Activity generator returned none.")
            activity: GeneratedActivity = acts.activities[0]
            return (
                activity.title,
                ActivityPayload(
                    kind=_safe_activity_kind(activity.kind),
                    title=activity.title,
                    instructions=activity.instructions,
                    estimated_minutes=activity.estimated_minutes,
                    source_chunk_markers=_resolved(
                        list(activity.source_chunk_markers), marker_map
                    ),
                ).model_dump(mode="json"),
            )

        if block_type == LessonBlockType.PRACTICAL_TASK:
            tasks: PracticalTaskGenerationResult = await generate_practical_tasks(
                self._llm_provider,
                settings,
                lesson_title=lesson.title,
                annotated_text=annotated_text,
                max_tasks=1,
            )
            if not tasks.tasks:
                raise AIOutputValidationError(
                    "Practical-task generator returned none."
                )
            task: GeneratedPracticalTask = tasks.tasks[0]
            return (
                task.title,
                PracticalTaskPayload(
                    brief=task.brief,
                    scenario=task.scenario,
                    steps=_usable_steps(list(task.steps)),
                    deliverable=task.deliverable,
                    evidence=task.evidence,
                    difficulty=_safe_difficulty(task.difficulty),
                    estimated_minutes=task.estimated_minutes,
                    source_chunk_markers=_resolved(
                        list(task.source_chunk_markers), marker_map
                    ),
                ).model_dump(mode="json"),
            )

        if block_type == LessonBlockType.EXTERNAL_RESOURCE:
            candidates: ResourceCandidateResult = await propose_resource_candidates(
                self._llm_provider,
                settings,
                lesson_title=lesson.title,
                annotated_text=annotated_text,
                max_resources=1,
            )
            validated, _ = await validate_resource_candidates(
                candidates.candidates,
                timeout_seconds=settings.content_resource_timeout_seconds,
            )
            if not validated:
                raise AIOutputValidationError(
                    "Resource URL could not be validated; none kept."
                )
            resource: ExternalResourcePayload = validated[0]
            resource.source_chunk_markers = _resolved(
                list(resource.source_chunk_markers), marker_map
            )
            return resource.title, resource.model_dump(mode="json")

        raise AIOutputValidationError(
            f"Block type {block_type.value} cannot be regenerated individually."
        )

    # ------------------------------------------------------------------
    # Source maps
    # ------------------------------------------------------------------

    async def get_source_map(self, lesson_id: uuid.UUID) -> LessonSourceMapRead:
        """Return the provenance map of a lesson back to its source chunks."""
        lesson = await self.get_lesson(lesson_id)
        await self._lesson_repository.commit()

        chain = await self._lesson_repository.get_provenance_chain(lesson_id)

        blocks_by_chunk: dict[uuid.UUID, list[SourceMapBlockCitation]] = {}
        for block in lesson.content_blocks:
            for chunk_id in _resolved_payload_chunk_ids(block):
                blocks_by_chunk.setdefault(chunk_id, []).append(
                    SourceMapBlockCitation(
                        block_id=block.id,
                        block_type=block.block_type,
                        title=block.title,
                        order_index=block.order_index,
                    )
                )

        sources: list[SourceMapItem] = []
        for _, chunk, page in chain:
            sources.append(
                SourceMapItem(
                    chunk_id=chunk.id,
                    page_number=page.page_number if page is not None else None,
                    document_index=chunk.document_index,
                    content=chunk.content,
                    cited_by=blocks_by_chunk.get(chunk.id, []),
                )
            )

        return LessonSourceMapRead(lesson_id=lesson_id, sources=sources)


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------


def _resolved(markers: list[str], marker_map: dict[str, uuid.UUID]) -> list[str]:
    """
    Resolve LLM citation markers to real chunk ids and return them as
    UUID strings (the persisted citation format). Hallucinated markers
    are dropped — provenance is never fabricated.
    """
    resolved, dropped = resolve_markers(markers, marker_map)
    if dropped:
        logger.debug("Dropped hallucinated source markers: %s", dropped)
    return [str(chunk_id) for chunk_id in resolved]


def _resolved_payload_chunk_ids(block: LessonContentBlock) -> list[uuid.UUID]:
    """Read the resolved chunk ids stored on a block's payload."""
    markers = block.payload.get("source_chunk_markers") or []
    chunk_ids: list[uuid.UUID] = []
    for marker in markers:
        if isinstance(marker, str):
            try:
                chunk_ids.append(uuid.UUID(marker))
            except ValueError:
                continue
    return chunk_ids


def _dedupe_links(links) -> list[LessonSourceChunk]:
    """Deduplicate lesson->chunk provenance links (unique constraint)."""
    seen: set[uuid.UUID] = set()
    unique: list[LessonSourceChunk] = []
    for link in links:
        if link.chunk_id in seen:
            continue
        seen.add(link.chunk_id)
        unique.append(link)
    return unique


def _block(
    *,
    lesson_id: uuid.UUID,
    block_type: LessonBlockType,
    order_index: int,
    title: str | None,
    payload: dict,
) -> LessonContentBlock:
    return LessonContentBlock(
        lesson_id=lesson_id,
        block_type=block_type,
        order_index=order_index,
        title=title,
        payload=payload,
        review_status=BlockReviewStatus.GENERATED,
    )


def _text_block_type(kind: str) -> LessonBlockType:
    mapping = {
        "heading": LessonBlockType.HEADING,
        "text": LessonBlockType.TEXT,
        "example": LessonBlockType.EXAMPLE,
        "summary": LessonBlockType.SUMMARY,
    }
    if kind not in mapping:
        raise AIOutputValidationError(f"Unsupported generated block kind {kind!r}.")
    return mapping[kind]


def _safe_difficulty(value: str) -> str:
    if value in ("easy", "medium", "hard"):
        return value
    return "medium"


def _safe_diagram_type(value: str) -> str:
    if value in ("flowchart", "hierarchy", "concept_map", "comparison"):
        return value
    return "concept_map"


def _safe_activity_kind(value: str) -> str:
    if value in ("practice_exercise", "project", "discussion", "research"):
        return value
    return "practice_exercise"
