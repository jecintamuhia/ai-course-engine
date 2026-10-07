"""Curriculum service: generates and manages curricula from extracted topics."""

from __future__ import annotations

import uuid
from datetime import date

from app.core.exceptions import (
    CurriculumNotFound,
    CurriculumValidationError,
    DocumentNotFound,
)
from app.core.logging import get_logger
from app.db.repositories.curriculum import CurriculumRepository
from app.db.repositories.dependencies import DependencyRepository
from app.db.repositories.documents import DocumentRepository
from app.db.repositories.topics import TopicRepository
from app.models.curriculum import Curriculum, CurriculumStatus
from app.models.curriculum_review import CurriculumReview, ReviewDecision
from app.models.curriculum_unit import CurriculumUnit
from app.models.curriculum_unit_topic import CurriculumUnitTopic
from app.models.topic import Topic
from app.services.moodle.export import build_curriculum_export
from app.services.planner.four_month_planner import (
    FourMonthPlanner,
    PlanningConfig,
    WeekPlan,
)
from app.services.topics.canonicalization import apply_canonicalization

logger = get_logger(__name__)


class CurriculumService:
    """Coordinates generation, review, and retrieval of curricula."""

    def __init__(
        self,
        document_repository: DocumentRepository,
        topic_repository: TopicRepository,
        dependency_repository: DependencyRepository,
        curriculum_repository: CurriculumRepository,
        planner: FourMonthPlanner | None = None,
    ) -> None:
        self._document_repository = document_repository
        self._topic_repository = topic_repository
        self._dependency_repository = dependency_repository
        self._curriculum_repository = curriculum_repository
        self._planner = planner or FourMonthPlanner()

    async def generate_curriculum(
        self,
        document_id: uuid.UUID,
        *,
        total_weeks: int = 16,
        learning_days_per_week: int = 5,
        hours_per_day: int = 4,
        start_date: date | None = None,
        title: str | None = None,
        description: str | None = None,
    ) -> Curriculum:
        """
        Deterministically generate a curriculum for a document from its
        extracted topics and resolved dependencies.

        Each call creates a new Curriculum version (prior latest
        versions are marked superseded); generation is deliberately
        incremental so lecturers can compare drafts.
        """
        document = await self._document_repository.get_by_id(document_id)

        if document is None:
            raise DocumentNotFound(f"Document {document_id} was not found.")

        topics = await self._topic_repository.list_flat_by_document(document_id)

        if not topics:
            raise CurriculumValidationError(
                f"Document {document_id} has no extracted topics. "
                "Run topic analysis before generating a curriculum.",
            )

        # Canonicalize before planning: assign canonical identity and
        # importance, and merge safe exact-normalized-title duplicates so
        # the course never contains accidental topic repetition. Merges
        # flag duplicate rows (duplicate_of_id); nothing is deleted.
        # Skipped when the repository returns non-Topic objects (e.g.
        # test doubles) — it is defined over the persisted Topic model.
        if topics and all(isinstance(topic, Topic) for topic in topics):
            canonicalization = apply_canonicalization(topics)
            await self._topic_repository.commit()
            if canonicalization.clusters:
                logger.info(
                    "Canonicalized topics before planning document_id=%s "
                    "clusters=%s duplicates=%s",
                    document_id,
                    canonicalization.clusters,
                    canonicalization.duplicates_flagged,
                )
            topics = await self._topic_repository.list_flat_by_document(
                document_id, exclude_duplicates=True
            )
            if not topics:
                raise CurriculumValidationError(
                    f"Document {document_id} has topics, but every one of them "
                    "was flagged as a duplicate of another canonical topic. "
                    "There is no canonical (non-duplicate) topic inventory to "
                    "plan a curriculum from.",
                )

        dependencies = await self._dependency_repository.list_by_document(document_id)

        max_weekly_minutes = learning_days_per_week * hours_per_day * 60

        config = PlanningConfig(
            total_weeks=total_weeks,
            max_weekly_workload_minutes=max_weekly_minutes,
            min_topic_allocation_minutes=60,
            max_topic_allocation_minutes=max_weekly_minutes,
        )

        try:
            week_plans = self._planner.plan(topics, dependencies, config)
        except ValueError as exc:
            raise CurriculumValidationError(str(exc)) from exc

        if not week_plans:
            raise CurriculumValidationError(
                f"No topics could be scheduled for document {document_id}.",
            )

        if len(week_plans) != total_weeks:
            raise CurriculumValidationError(
                f"Planned weeks ({len(week_plans)}) do not match the "
                f"requested course length ({total_weeks} weeks).",
            )

        if title and title.strip():
            title = title.strip()
        else:
            title = _strip_extension(document.original_filename) or "Untitled course"
        version_number = (
            await self._curriculum_repository.latest_version_number(document_id) + 1
        )

        for older in await self._curriculum_repository.list_latest_by_document(
            document_id
        ):
            await self._curriculum_repository.mark_superseded(older)

        curriculum = _build_curriculum(
            document_id=document_id,
            title=title,
            description=description,
            version_number=version_number,
            week_plans=week_plans,
            topics_by_id={topic.id: topic for topic in topics},
            total_weeks=total_weeks,
            start_date=start_date,
            learning_days_per_week=learning_days_per_week,
            hours_per_day=hours_per_day,
            max_weekly_minutes=max_weekly_minutes,
        )

        await self._curriculum_repository.add(curriculum)
        await self._curriculum_repository.commit()

        logger.info(
            "Generated curriculum curriculum_id=%s document_id=%s weeks=%s version=%s",
            curriculum.id,
            document_id,
            len(week_plans),
            version_number,
        )

        return curriculum

    async def get_by_id(self, curriculum_id: uuid.UUID) -> Curriculum:
        """Fetch a curriculum by ID, with units and reviews loaded."""
        curriculum = await self._curriculum_repository.get_by_id(curriculum_id)

        if curriculum is None:
            raise CurriculumNotFound(f"Curriculum {curriculum_id} was not found.")

        return curriculum

    async def list_latest_by_document(self, document_id: uuid.UUID) -> list[Curriculum]:
        """Return latest-version curricula for a document."""
        return await self._curriculum_repository.list_latest_by_document(document_id)

    async def export_payload(self, curriculum_id: uuid.UUID) -> dict:
        """
        Build the Moodle-ready curriculum export for a curriculum.

        Pure read: fetches the curriculum and its source document to
        attach provenance, then serializes the plan via the export
        service. The export is a reference document, never a Moodle
        backup, and does not modify any records.
        """
        curriculum = await self.get_by_id(curriculum_id)
        await self._curriculum_repository.commit()

        document = await self._document_repository.get_by_id(curriculum.document_id)
        await self._document_repository.commit()
        return build_curriculum_export(curriculum, document=document)

    async def submit_for_review(self, curriculum_id: uuid.UUID) -> Curriculum:
        """Move a DRAFT curriculum into the review queue."""
        curriculum = await self.get_by_id(curriculum_id)

        if curriculum.status != CurriculumStatus.DRAFT:
            raise CurriculumValidationError(
                "Only DRAFT curricula can be submitted for review.",
                details={"current_status": curriculum.status.value},
            )

        curriculum.status = CurriculumStatus.AWAITING_REVIEW
        await self._curriculum_repository.commit()
        return curriculum

    async def review(
        self,
        curriculum_id: uuid.UUID,
        *,
        decision: ReviewDecision,
        reviewer_name: str | None = None,
        comments: str | None = None,
    ) -> Curriculum:
        """Record a lecturer decision and move the curriculum accordingly."""
        curriculum = await self.get_by_id(curriculum_id)

        if curriculum.status != CurriculumStatus.AWAITING_REVIEW:
            raise CurriculumValidationError(
                "Only AWAITING_REVIEW curricula can be reviewed.",
                details={"current_status": curriculum.status.value},
            )

        review = CurriculumReview(
            curriculum_id=curriculum.id,
            reviewer_name=reviewer_name,
            decision=decision,
            comments=comments,
        )

        if decision == ReviewDecision.APPROVED:
            curriculum.status = CurriculumStatus.APPROVED
        else:
            curriculum.status = CurriculumStatus.REJECTED

        await self._curriculum_repository.add_review(review)
        await self._curriculum_repository.commit()

        logger.info(
            "Curriculum reviewed curriculum_id=%s decision=%s reviewer=%s",
            curriculum.id,
            decision.value,
            reviewer_name,
        )

        return curriculum


def _strip_extension(filename: str) -> str:
    """Strip a trailing file extension from a filename for display."""
    if "." not in filename:
        return filename
    stem, extension = filename.rsplit(".", 1)
    return stem if extension else filename


def _build_curriculum(
    *,
    document_id: uuid.UUID,
    title: str,
    description: str | None,
    version_number: int,
    week_plans: list[WeekPlan],
    topics_by_id: dict[uuid.UUID, Topic],
    total_weeks: int,
    start_date: date | None,
    learning_days_per_week: int,
    hours_per_day: int,
    max_weekly_minutes: int,
) -> Curriculum:
    """Construct a Curriculum ORM graph (units + topic links) from week plans."""
    curriculum = Curriculum(
        document_id=document_id,
        title=title,
        description=description,
        status=CurriculumStatus.DRAFT,
        total_weeks=total_weeks,
        start_date=start_date,
        learning_days_per_week=learning_days_per_week,
        hours_per_day=hours_per_day,
        max_weekly_workload_minutes=max_weekly_minutes,
        min_topic_allocation_minutes=60,
        max_topic_allocation_minutes=max_weekly_minutes,
        version_number=version_number,
        is_latest_version=True,
    )

    for week in week_plans:
        unit = CurriculumUnit(
            curriculum=curriculum,
            week_number=week.week_number,
            title=week.title,
            description=week.description,
            learning_objectives=list(week.learning_objectives),
            estimated_workload_minutes=week.total_minutes,
            order_index=week.week_number,
        )
        for plan_index, allocation in enumerate(week.allocations):
            topic = topics_by_id.get(allocation.topic_id)
            unit.topic_links.append(
                CurriculumUnitTopic(
                    topic=topic,
                    topic_id=None if topic is not None else allocation.topic_id,
                    order_index=plan_index,
                )
            )

    return curriculum
