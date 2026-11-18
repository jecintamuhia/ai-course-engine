"""Learner portal endpoints.

The learner portal is the surface a signed-up learner uses: their own
account, the courses they enrolled in, their lesson milestones and their
practical task submissions. Every response here is scoped to the calling
account.
"""

from __future__ import annotations

import uuid

from app.core.config import Settings
from app.core.dependencies import (
    get_app_settings,
    get_database_session,
    get_moodle_content_service,
    require_learner,
)
from app.db.repositories.assessment_attempts import AssessmentAttemptRepository
from app.db.repositories.assessments import AssessmentRepository
from app.db.repositories.certificates import CertificateRepository
from app.db.repositories.courses import CourseRepository
from app.db.repositories.learner_enrolments import LearnerEnrolmentRepository
from app.db.repositories.learner_milestones import LearnerMilestoneRepository
from app.db.repositories.lecturer_activities import LecturerActivityRepository
from app.db.repositories.lessons import LessonRepository
from app.db.repositories.practical_submissions import PracticalSubmissionRepository
from app.models.lesson import Lesson
from app.models.lesson_content_block import LessonBlockType
from app.models.practical_submission import PracticalSubmission
from app.models.user import User
from app.schemas.learner_assessment import (
    AssessmentAttemptListResponse,
    AssessmentAttemptRead,
    AssessmentSubmitRequest,
    CertificateCourseRead,
    CertificateListResponse,
    FinalAssessmentRead,
)
from app.schemas.learner_portal import (
    CourseDetailRead,
    EnrolResponse,
    LearnerCourseListResponse,
    LearnerCourseRead,
    LearnerMilestoneRead,
    LearnerProfileRead,
    LessonBlockRead,
    LessonCompletionResponse,
    LessonRead,
    PracticalSubmissionRead,
    PracticalSubmissionRequest,
    PracticalSubmissionResponse,
    ProgressSummary,
)
from app.schemas.moodle import (
    MoodleCourseStructureRead,
    MoodleLessonContentRead,
)
from app.services.learner.assessment import LearnerAssessmentService
from app.services.learner.service import LearnerPortalService
from app.services.moodle.content import MoodleCourseContentService
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/learner", tags=["learner"])


def get_learner_portal_service(
    session: AsyncSession = Depends(get_database_session),
) -> LearnerPortalService:
    """Construct a request-scoped learner portal service."""
    return LearnerPortalService(
        CourseRepository(session),
        LearnerEnrolmentRepository(session),
        LearnerMilestoneRepository(session),
        PracticalSubmissionRepository(session),
        LessonRepository(session),
        LecturerActivityRepository(session),
    )


def get_learner_assessment_service(
    session: AsyncSession = Depends(get_database_session),
    settings: Settings = Depends(get_app_settings),
) -> LearnerAssessmentService:
    """Construct a request-scoped assessment and certificate service."""
    return LearnerAssessmentService(
        CourseRepository(session),
        LearnerEnrolmentRepository(session),
        LearnerMilestoneRepository(session),
        LessonRepository(session),
        AssessmentRepository(session),
        AssessmentAttemptRepository(session),
        CertificateRepository(session),
        pass_percent=settings.assessment_pass_percent,
    )


@router.get("/profile", response_model=LearnerProfileRead)
async def get_profile(
    user: User = Depends(require_learner),
) -> LearnerProfileRead:
    """Return the signed-in learner's own profile."""
    return LearnerProfileRead.model_validate(user)


@router.get("/courses", response_model=LearnerCourseListResponse)
async def list_learner_courses(
    user: User = Depends(require_learner),
    service: LearnerPortalService = Depends(get_learner_portal_service),
) -> LearnerCourseListResponse:
    """List the courses the signed-in learner is actively enrolled in."""
    courses = await service.list_enrolled_courses(user)
    return LearnerCourseListResponse(
        courses=[LearnerCourseRead.model_validate(course) for course in courses]
    )


@router.get("/catalog", response_model=LearnerCourseListResponse)
async def list_catalog(
    user: User = Depends(require_learner),
    service: LearnerPortalService = Depends(get_learner_portal_service),
) -> LearnerCourseListResponse:
    """List the published courses available for self-enrolment."""
    courses = await service.list_catalog()
    return LearnerCourseListResponse(
        courses=[LearnerCourseRead.model_validate(course) for course in courses]
    )


@router.post("/courses/{course_id}/enrol", response_model=EnrolResponse)
async def enrol_in_course(
    course_id: uuid.UUID,
    user: User = Depends(require_learner),
    service: LearnerPortalService = Depends(get_learner_portal_service),
) -> EnrolResponse:
    """Enrol the signed-in learner in a published course."""
    enrolment = await service.enrol(user, course_id)
    return EnrolResponse(enrolled=True, enrolment_id=enrolment.id)


@router.delete("/courses/{course_id}/enrol", response_model=EnrolResponse)
async def withdraw_from_course(
    course_id: uuid.UUID,
    user: User = Depends(require_learner),
    service: LearnerPortalService = Depends(get_learner_portal_service),
) -> EnrolResponse:
    """Withdraw the signed-in learner from a course."""
    enrolment = await service.withdraw(user, course_id)
    return EnrolResponse(enrolled=False, enrolment_id=enrolment.id)


@router.get("/courses/{course_id}", response_model=CourseDetailRead)
async def get_course_detail(
    course_id: uuid.UUID,
    user: User = Depends(require_learner),
    service: LearnerPortalService = Depends(get_learner_portal_service),
) -> CourseDetailRead:
    """Return a course with its lessons and the caller's own progress."""
    course, lessons, milestones, submissions = await service.get_course_detail(
        user,
        course_id,
    )
    completed_ids = {milestone.lesson_id for milestone in milestones}
    lesson_reads = [
        _lesson_read(lesson, completed_ids, submissions) for lesson in lessons
    ]
    total = len(lessons)
    done = len(completed_ids & {lesson.id for lesson in lessons})
    progress = ProgressSummary(
        total_lessons=total,
        completed_lessons=done,
        percentage=int((done / total) * 100) if total else 0,
    )
    return CourseDetailRead(
        course=LearnerCourseRead.model_validate(course),
        lessons=lesson_reads,
        milestones=[LearnerMilestoneRead.model_validate(m) for m in milestones],
        progress=progress,
        enrolled=True,
    )


@router.get(
    "/courses/{course_id}/content", response_model=MoodleCourseStructureRead
)
async def get_course_content(
    course_id: uuid.UUID,
    user: User = Depends(require_learner),
    service: LearnerPortalService = Depends(get_learner_portal_service),
    content_service: MoodleCourseContentService = Depends(
        get_moodle_content_service
    ),
) -> MoodleCourseStructureRead:
    """Return the published Moodle course structure for an enrolled course.

    Resolves the internal course record to its Moodle course id and reads
    the published sections (weeks) and page modules (lessons) from Moodle.
    The caller must be actively enrolled; Moodle secrets never leave the
    server.
    """
    await service.require_enrolment(user, course_id)
    return await content_service.get_course_structure(course_id)


@router.get(
    "/courses/{course_id}/lessons/{lesson_id}/content",
    response_model=MoodleLessonContentRead,
)
async def get_lesson_content(
    course_id: uuid.UUID,
    lesson_id: uuid.UUID,
    user: User = Depends(require_learner),
    service: LearnerPortalService = Depends(get_learner_portal_service),
    content_service: MoodleCourseContentService = Depends(
        get_moodle_content_service
    ),
) -> MoodleLessonContentRead:
    """Return the published Moodle page content for one lesson.

    The caller must be actively enrolled and the lesson must belong to the
    course's curriculum. If the lesson was not published to Moodle as a
    Page activity, a 404 is returned rather than fabricating content.
    """
    await service.require_enrolment(user, course_id)
    return await content_service.get_lesson_content(course_id, lesson_id)


@router.post(
    "/courses/{course_id}/lessons/{lesson_id}/complete",
    response_model=LessonCompletionResponse,
)
async def complete_lesson(
    course_id: uuid.UUID,
    lesson_id: uuid.UUID,
    user: User = Depends(require_learner),
    service: LearnerPortalService = Depends(get_learner_portal_service),
) -> LessonCompletionResponse:
    """Mark a lesson complete for the signed-in learner."""
    milestone = await service.complete_lesson(user, course_id, lesson_id)
    return LessonCompletionResponse(completed=True, milestone_id=milestone.id)


@router.delete(
    "/courses/{course_id}/lessons/{lesson_id}/complete",
    response_model=LessonCompletionResponse,
)
async def undo_lesson_completion(
    course_id: uuid.UUID,
    lesson_id: uuid.UUID,
    user: User = Depends(require_learner),
    service: LearnerPortalService = Depends(get_learner_portal_service),
) -> LessonCompletionResponse:
    """Undo the signed-in learner's completion of a lesson."""
    await service.undo_lesson_completion(user, course_id, lesson_id)
    return LessonCompletionResponse(completed=False, milestone_id=None)


@router.post(
    "/courses/{course_id}/blocks/{block_id}/submit",
    response_model=PracticalSubmissionResponse,
)
async def submit_practical_task(
    course_id: uuid.UUID,
    block_id: uuid.UUID,
    body: PracticalSubmissionRequest,
    user: User = Depends(require_learner),
    service: LearnerPortalService = Depends(get_learner_portal_service),
) -> PracticalSubmissionResponse:
    """Submit a text/markdown hand-in for a practical task block."""
    submission = await service.submit_practical_task(
        user,
        course_id,
        block_id,
        body.content,
    )
    return PracticalSubmissionResponse(
        submission=PracticalSubmissionRead.model_validate(submission)
    )


@router.get("/submissions", response_model=list[PracticalSubmissionRead])
async def list_my_submissions(
    user: User = Depends(require_learner),
    service: LearnerPortalService = Depends(get_learner_portal_service),
) -> list[PracticalSubmissionRead]:
    """List every submission the signed-in learner has made."""
    submissions = await service.list_my_submissions(user)
    return [PracticalSubmissionRead.model_validate(item) for item in submissions]


@router.get(
    "/courses/{course_id}/final-assessment",
    response_model=FinalAssessmentRead,
)
async def get_final_assessment(
    course_id: uuid.UUID,
    user: User = Depends(require_learner),
    service: LearnerAssessmentService = Depends(get_learner_assessment_service),
) -> FinalAssessmentRead:
    """Return the course's final assessment without revealing answers."""
    return await service.get_final_assessment(user, course_id)


@router.post(
    "/courses/{course_id}/final-assessment/attempts",
    response_model=AssessmentAttemptRead,
)
async def submit_final_assessment(
    course_id: uuid.UUID,
    body: AssessmentSubmitRequest,
    user: User = Depends(require_learner),
    service: LearnerAssessmentService = Depends(get_learner_assessment_service),
) -> AssessmentAttemptRead:
    """Grade and store one attempt at the final assessment."""
    return await service.submit_attempt(user, course_id, body)


@router.get(
    "/courses/{course_id}/final-assessment/attempts",
    response_model=AssessmentAttemptListResponse,
)
async def list_final_assessment_attempts(
    course_id: uuid.UUID,
    user: User = Depends(require_learner),
    service: LearnerAssessmentService = Depends(get_learner_assessment_service),
) -> AssessmentAttemptListResponse:
    """Return the caller's own attempts at the final assessment."""
    attempts = await service.list_attempts(user, course_id)
    return AssessmentAttemptListResponse(attempts=attempts)


@router.post(
    "/courses/{course_id}/certificate",
    response_model=CertificateCourseRead,
)
async def request_certificate(
    course_id: uuid.UUID,
    user: User = Depends(require_learner),
    service: LearnerAssessmentService = Depends(get_learner_assessment_service),
) -> CertificateCourseRead:
    """Issue the caller's certificate once all requirements are met."""
    return await service.issue_certificate(user, course_id)


@router.get("/certificates", response_model=CertificateListResponse)
async def list_my_certificates(
    user: User = Depends(require_learner),
    service: LearnerAssessmentService = Depends(get_learner_assessment_service),
) -> CertificateListResponse:
    """List every certificate the signed-in learner has earned."""
    certificates = await service.list_certificates(user)
    return CertificateListResponse(certificates=certificates)


def _lesson_read(
    lesson: Lesson,
    completed_ids: set[uuid.UUID],
    submissions: dict[uuid.UUID, PracticalSubmission],
) -> LessonRead:
    """Build the learner-facing view of a lesson and its blocks."""
    block_reads: list[LessonBlockRead] = []
    for block in sorted(lesson.content_blocks, key=lambda item: item.order_index):
        submission = None
        if block.block_type == LessonBlockType.PRACTICAL_TASK:
            found = submissions.get(block.id)
            if found:
                submission = PracticalSubmissionRead.model_validate(found)
        block_reads.append(
            LessonBlockRead(
                id=block.id,
                lesson_id=block.lesson_id,
                block_type=block.block_type,
                order_index=block.order_index,
                title=block.title,
                payload=block.payload,
                review_status=block.review_status,
                submission=submission,
            )
        )
    return LessonRead(
        id=lesson.id,
        curriculum_id=lesson.curriculum_id,
        curriculum_unit_id=lesson.curriculum_unit_id,
        week_number=lesson.week_number,
        order_index=lesson.order_index,
        title=lesson.title,
        description=lesson.description,
        learning_objectives=lesson.learning_objectives,
        estimated_workload_minutes=lesson.estimated_workload_minutes,
        status=lesson.status,
        blocks=block_reads,
        completed=lesson.id in completed_ids,
    )
