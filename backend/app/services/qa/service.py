"""Content-QA service: assemble the inspection surface, run rules, persist.

This service is deliberately independent of Moodle publishing and
SSE/HTTP concerns. It expects injected repositories (matching the rest
of the service layer) and provides:

- :func:`run_curriculum_qa` — runs every QA rule over a curriculum,
  computes the verdict + area summary + summary, persists a
  ``QualityReport``, and returns it (plus whether the verdict blocks);
- :func:`build_coverage_report` — a read-only textbook coverage report
  (mapped topics, lesson coverage, blocked duplicates, resource/video
  counts) for the lecturer/review UI;
- :func:`get_latest_report` — the latest persisted report for a
  curriculum.

The verdict contract is enforced at the route layer: ``fail`` verdicts
raise ``ContentQAError`` before curriculum approval or Moodle
publishing proceeds (see ``app.api.v1``).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.config import Settings
from app.core.exceptions import (
    ContentQAError,
    CurriculumNotFound,
    DocumentNotFound,
    QualityReportNotFound,
)
from app.core.logging import get_logger
from app.db.repositories.assessments import AssessmentRepository
from app.db.repositories.courses import CourseRepository
from app.db.repositories.curriculum import CurriculumRepository
from app.db.repositories.dependencies import DependencyRepository
from app.db.repositories.documents import DocumentRepository
from app.db.repositories.lessons import LessonRepository
from app.db.repositories.quality_reports import QualityReportRepository
from app.db.repositories.structure import StructureRepository
from app.db.repositories.topics import TopicRepository
from app.models.curriculum import Curriculum, CurriculumStatus
from app.models.quality_report import QualityReport
from app.schemas.qa import (
    CoverageReportRead,
    QAAreaStatus,
    QAFinding,
    QAReportRead,
    QAReportResponse,
    TopicCoverageItem,
)
from app.services.qa.rules import QAData, run_all_rules

logger = get_logger(__name__)

_AREA_ORDER = (
    "coverage",
    "duplication",
    "provenance",
    "quality",
    "learning_design",
    "moodle",
)
_SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


@dataclass
class QADependencies:
    """Repository bundle the QA service operates on."""

    curriculum: CurriculumRepository
    dependencies: DependencyRepository
    topics: TopicRepository
    lessons: LessonRepository
    structure: StructureRepository
    documents: DocumentRepository
    quality_reports: QualityReportRepository
    assessments: AssessmentRepository
    courses: CourseRepository


def verdict_for_findings(findings: list[QAFinding]) -> str:
    """Derive the report verdict from findings by strictest severity."""
    if any(f.severity == "error" for f in findings):
        return "fail"
    if any(f.severity == "warning" for f in findings):
        return "warning"
    return "pass"


def area_status(findings: list[QAFinding]) -> QAAreaStatus:
    return QAAreaStatus(
        status=verdict_for_findings(findings),
        findings=len(findings),
    )


class QAService:
    """Runs content-QA over curricula and builds coverage reports."""

    def __init__(
        self,
        deps: QADependencies,
        settings: Settings,
    ) -> None:
        self._deps = deps
        self._settings = settings

    async def _load_qadata(self, curriculum_id: uuid.UUID) -> tuple[Curriculum, QAData]:
        curriculum = await self._deps.curriculum.get_by_id(curriculum_id)
        if curriculum is None:
            raise CurriculumNotFound(f"Curriculum {curriculum_id} was not found.")

        topics = await self._deps.topics.list_flat_by_document(curriculum.document_id)
        dependencies = await self._deps.dependencies.list_by_document(
            curriculum.document_id
        )
        lessons = await self._deps.lessons.list_by_curriculum(curriculum_id)
        assessments = await self._deps.assessments.list_by_curriculum(curriculum_id)
        chapters = await self._deps.structure.list_chapters_by_document(
            curriculum.document_id
        )
        course = await self._deps.courses.get_by_curriculum(curriculum_id)

        data = QAData(
            curriculum=curriculum,
            topics=topics,
            lessons=lessons,
            assessments=assessments,
            chapters=chapters,
            course=course,
            dependencies=dependencies,
            min_major_prose_chars=self._settings.qa_min_major_prose_chars,
            min_supporting_prose_chars=self._settings.qa_min_supporting_prose_chars,
            duplicate_title_similarity=self._settings.qa_duplicate_title_similarity,
        )
        return curriculum, data

    async def get_latest_report(self, curriculum_id: uuid.UUID) -> QualityReport:
        report = await self._deps.quality_reports.get_latest_by_curriculum(
            curriculum_id
        )
        if report is None:
            raise QualityReportNotFound(
                f"No content-QA report exists for curriculum {curriculum_id}."
            )
        return report

    async def run_curriculum_qa(self, curriculum_id: uuid.UUID) -> QAReportResponse:
        """
        Run every QA rule, persist a QualityReport, and return the
        response. ``blocked`` is True when the verdict is ``fail``.
        """
        curriculum, data = await self._load_qadata(curriculum_id)

        domains = run_all_rules(data)
        findings = [
            finding
            for domain in _AREA_ORDER
            for finding in sorted(
                domains[domain],
                key=lambda f: _SEVERITY_ORDER.get(f.severity, 9),
            )
        ]
        verdict = verdict_for_findings(findings)

        if verdict == "fail" and curriculum.status == CurriculumStatus.PUBLISHED:
            # The already-synced Moodle course remains available, but this
            # curriculum revision is no longer eligible to claim PUBLISHED.
            # Keep its prior lecturer approval so incomplete lessons can be
            # resumed, then reviewed and published again after QA passes.
            curriculum.status = CurriculumStatus.APPROVED
            logger.warning(
                "Demoted curriculum after blocking QA findings "
                "curriculum_id=%s moodle_course_id=%s",
                curriculum.id,
                data.course.moodle_course_id if data.course else None,
            )

        version_number = 1
        existing = await self._deps.quality_reports.get_latest_by_curriculum(
            curriculum_id
        )
        if existing is not None:
            version_number = existing.version_number + 1

        report = QualityReport(
            curriculum_id=curriculum_id,
            version_number=version_number,
            verdict=verdict,
            areas={
                domain: area_status(domains[domain]).model_dump(mode="json")
                for domain in _AREA_ORDER
            },
            findings=[f.model_dump(mode="json") for f in findings],
            summary={domain: len(domains[domain]) for domain in _AREA_ORDER},
        )
        await self._deps.quality_reports.add(report)
        await self._deps.quality_reports.commit()

        logger.info(
            "QA run curriculum_id=%s version=%s verdict=%s findings=%s",
            curriculum_id,
            version_number,
            verdict,
            len(findings),
        )

        read = QAReportRead(
            id=report.id,
            curriculum_id=report.curriculum_id,
            version_number=report.version_number,
            verdict=report.verdict,
            areas=report.areas,
            findings=report.findings,
            summary=report.summary,
            checked_at=report.checked_at,
        )
        return QAReportResponse(report=read, blocked=verdict == "fail")

    async def assert_qa_pass(self, curriculum_id: uuid.UUID) -> None:
        """Raise ContentQAError unless the latest QA verdict is not fail."""
        response = await self.run_curriculum_qa(curriculum_id)
        if response.blocked:
            raise ContentQAError(
                "Curriculum failed content-QA; resolve the findings before "
                "approving or publishing.",
                details={
                    "curriculum_id": str(curriculum_id),
                    "report_id": str(response.report.id),
                    "verdict": response.report.verdict,
                    "findings": [
                        f.model_dump(mode="json") for f in response.report.findings
                    ],
                },
            )

    async def build_coverage_report(
        self,
        curriculum_id: uuid.UUID | None,
        document_id: uuid.UUID | None = None,
    ) -> CoverageReportRead:
        """Build the textbook coverage report for a document/curriculum."""
        if document_id is None and curriculum_id is not None:
            curriculum = await self._deps.curriculum.get_by_id(curriculum_id)
            if curriculum is None:
                raise CurriculumNotFound(f"Curriculum {curriculum_id} was not found.")
            document_id = curriculum.document_id

        if document_id is None:
            raise CurriculumNotFound(
                "Cannot build a coverage report without a document id."
            )

        document = await self._deps.documents.get_by_id(document_id)
        if document is None:
            raise DocumentNotFound(f"Document {document_id} was not found.")

        topics = await self._deps.topics.list_flat_by_document(document_id)
        chapters = await self._deps.structure.list_chapters_by_document(document_id)
        chapters_by_id = {chapter.id: chapter for chapter in chapters}

        curriculum = None
        if curriculum_id is not None:
            curriculum = await self._deps.curriculum.get_by_id(curriculum_id)

        lessons = []
        if curriculum is not None:
            lessons = await self._deps.lessons.list_by_curriculum(curriculum.id)

        mapped_topic_ids: set[uuid.UUID] = set()
        if curriculum is not None:
            mapped_topic_ids = {
                link.topic_id
                for unit in curriculum.units
                for link in unit.topic_links
                if link.topic_id is not None
            }

        lesson_topic_ids = {lesson.topic_id for lesson in lessons if lesson.topic_id}
        non_duplicate_topics = [
            topic for topic in topics if topic.duplicate_of_id is None
        ]
        duplicates_removed = sum(
            1 for topic in topics if topic.duplicate_of_id is not None
        )

        importance_counts: dict[str, int] = {}
        for topic in non_duplicate_topics:
            importance = topic.importance or ""
            importance_counts[importance] = importance_counts.get(importance, 0) + 1

        item_rows: list[TopicCoverageItem] = []
        for topic in non_duplicate_topics:
            chapter = chapters_by_id.get(topic.chapter_id) if topic.chapter_id else None
            item_rows.append(
                TopicCoverageItem(
                    topic_id=topic.id,
                    title=topic.title,
                    chapter_id=topic.chapter_id,
                    chapter_title=chapter.title if chapter else None,
                    importance=topic.importance,
                    workload_minutes=topic.estimated_workload_minutes or 0,
                    sources_chapters=1 if topic.chapter_id else 0,
                    mapped=topic.id in mapped_topic_ids,
                    has_lesson=topic.id in lesson_topic_ids,
                )
            )

        sections = sum(len(chapter.sections) for chapter in chapters)

        resource_count = sum(
            1
            for lesson in lessons
            for block in lesson.content_blocks
            if block.block_type.value == "external_resource"
        )
        video_count = sum(
            1
            for lesson in lessons
            for block in lesson.content_blocks
            if block.block_type.value == "video"
        )
        activity_count = sum(
            1
            for lesson in lessons
            for block in lesson.content_blocks
            if block.block_type.value == "activity"
        )
        knowledge_check_count = sum(
            1
            for lesson in lessons
            for block in lesson.content_blocks
            if block.block_type.value == "knowledge_check"
        )
        diagram_count = sum(
            1
            for lesson in lessons
            for block in lesson.content_blocks
            if block.block_type.value == "diagram"
        )

        mapped_ids_for_percent = len(mapped_topic_ids) if curriculum else 0
        coverage_percent = (
            round(mapped_ids_for_percent / len(non_duplicate_topics) * 100, 1)
            if non_duplicate_topics
            else 0.0
        )

        return CoverageReportRead(
            document_id=document_id,
            document_title=document.original_filename or document.title,
            curriculum_id=curriculum.id if curriculum else None,
            chapters=len(chapters),
            sections=sections,
            topic_count=len(non_duplicate_topics),
            importance_counts=importance_counts,
            mapped_topic_count=mapped_ids_for_percent,
            lesson_count=len(lessons),
            coverage_percent=coverage_percent,
            duplicate_topics_removed=duplicates_removed,
            unresolved_topic_count=0,
            unresolved_topics=[],
            resource_count=resource_count,
            video_count=video_count,
            activity_count=activity_count,
            knowledge_check_count=knowledge_check_count,
            diagram_count=diagram_count,
            topics=item_rows,
        )
