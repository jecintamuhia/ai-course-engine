"""Lecturer endpoints for learner progress and practical task review."""

from __future__ import annotations

import uuid

from app.core.dependencies import (
    get_database_session,
    get_moodle_content_service,
    require_staff,
)
from app.db.repositories.courses import CourseRepository
from app.db.repositories.learner_enrolments import LearnerEnrolmentRepository
from app.db.repositories.learner_milestones import LearnerMilestoneRepository
from app.db.repositories.lecturer_activities import LecturerActivityRepository
from app.db.repositories.lessons import LessonRepository
from app.db.repositories.practical_submissions import PracticalSubmissionRepository
from app.db.repositories.users import UserRepository
from app.models.user import User
from app.schemas.learner_portal import (
    GradeSubmissionRequest,
    LecturerActivityRead,
    PracticalSubmissionRead,
)
from app.schemas.moodle import (
    MoodleCourseStructureRead,
    MoodleLessonContentRead,
)
from app.services.lecturer.service import LecturerReviewService
from app.services.moodle.content import MoodleCourseContentService
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/lecturer", tags=["lecturer"])


def get_lecturer_review_service(
    session: AsyncSession = Depends(get_database_session),
) -> LecturerReviewService:
    """Construct a request-scoped lecturer review service."""
    return LecturerReviewService(
        CourseRepository(session),
        LearnerEnrolmentRepository(session),
        LearnerMilestoneRepository(session),
        PracticalSubmissionRepository(session),
        LecturerActivityRepository(session),
        LessonRepository(session),
        UserRepository(session),
    )


@router.get("/courses/{course_id}/submissions")
async def list_submissions(
    course_id: uuid.UUID,
    user: User = Depends(require_staff),
    service: LecturerReviewService = Depends(get_lecturer_review_service),
) -> list[dict]:
    """List every practical task submission made towards a course."""
    return await service.list_submissions(course_id)


@router.get("/courses/{course_id}/submissions/pending")
async def list_pending_submissions(
    course_id: uuid.UUID,
    user: User = Depends(require_staff),
    service: LecturerReviewService = Depends(get_lecturer_review_service),
) -> list[dict]:
    """List the submissions of a course that still await review."""
    return await service.list_pending_submissions(course_id)


@router.get(
    "/courses/{course_id}/activities", response_model=list[LecturerActivityRead]
)
async def list_activities(
    course_id: uuid.UUID,
    user: User = Depends(require_staff),
    service: LecturerReviewService = Depends(get_lecturer_review_service),
) -> list[LecturerActivityRead]:
    """List the recent learner activity recorded for a course."""
    activities = await service.list_activities(course_id)
    return [LecturerActivityRead.model_validate(item) for item in activities]


@router.get("/courses/{course_id}/learners")
async def list_learner_progress(
    course_id: uuid.UUID,
    user: User = Depends(require_staff),
    service: LecturerReviewService = Depends(get_lecturer_review_service),
) -> list[dict]:
    """List the enrolled learners of a course with their progress."""
    return await service.list_learner_progress(course_id)


@router.get(
    "/courses/{course_id}/content", response_model=MoodleCourseStructureRead
)
async def lecturer_course_content(
    course_id: uuid.UUID,
    user: User = Depends(require_staff),
    content_service: MoodleCourseContentService = Depends(
        get_moodle_content_service
    ),
) -> MoodleCourseStructureRead:
    """Return the published Moodle course structure for a staff-reviewed course.

    Lecturers (and administrators) may open the curriculum of any published
    course they are authorized to review. The Moodle web-service token is
    never exposed to the browser.
    """
    return await content_service.get_course_structure(course_id)


@router.get(
    "/courses/{course_id}/lessons/{lesson_id}/content",
    response_model=MoodleLessonContentRead,
)
async def lecturer_lesson_content(
    course_id: uuid.UUID,
    lesson_id: uuid.UUID,
    user: User = Depends(require_staff),
    content_service: MoodleCourseContentService = Depends(
        get_moodle_content_service
    ),
) -> MoodleLessonContentRead:
    """Return the published Moodle page content for one lesson (staff)."""
    return await content_service.get_lesson_content(course_id, lesson_id)


@router.post(
    "/submissions/{submission_id}/grade", response_model=PracticalSubmissionRead
)
async def grade_submission(
    submission_id: uuid.UUID,
    body: GradeSubmissionRequest,
    user: User = Depends(require_staff),
    service: LecturerReviewService = Depends(get_lecturer_review_service),
) -> PracticalSubmissionRead:
    """Grade a practical task submission."""
    submission = await service.grade_submission(
        submission_id,
        user,
        body.grade,
        body.feedback,
    )
    return PracticalSubmissionRead.model_validate(submission)


@router.post(
    "/submissions/{submission_id}/return", response_model=PracticalSubmissionRead
)
async def return_submission(
    submission_id: uuid.UUID,
    body: GradeSubmissionRequest,
    user: User = Depends(require_staff),
    service: LecturerReviewService = Depends(get_lecturer_review_service),
) -> PracticalSubmissionRead:
    """Return a submission to the learner for revision."""
    submission = await service.return_submission(
        submission_id,
        user,
        body.feedback,
    )
    return PracticalSubmissionRead.model_validate(submission)
