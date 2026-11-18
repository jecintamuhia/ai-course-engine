"""Lecturer review service: learner progress and practical task grading."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.core.exceptions import (
    CourseNotFound,
    PracticalSubmissionNotFound,
)
from app.db.repositories.courses import CourseRepository
from app.db.repositories.learner_enrolments import LearnerEnrolmentRepository
from app.db.repositories.learner_milestones import LearnerMilestoneRepository
from app.db.repositories.lecturer_activities import LecturerActivityRepository
from app.db.repositories.lessons import LessonRepository
from app.db.repositories.practical_submissions import PracticalSubmissionRepository
from app.db.repositories.users import UserRepository
from app.models.lecturer_activity import LecturerActivity, LecturerActivityType
from app.models.lesson import LessonStatus
from app.models.practical_submission import PracticalSubmission, SubmissionStatus
from app.models.user import User


class LecturerReviewService:
    """
    Coordinates what a lecturer may review for a published course.

    Lecturers only ever see the courses they staff, and the learner
    records attached to them. Marks, feedback and activity stay in this
    application; Moodle remains the delivery surface for content.
    """

    def __init__(
        self,
        course_repository: CourseRepository,
        enrolment_repository: LearnerEnrolmentRepository,
        milestone_repository: LearnerMilestoneRepository,
        submission_repository: PracticalSubmissionRepository,
        activity_repository: LecturerActivityRepository,
        lesson_repository: LessonRepository,
        user_repository: UserRepository,
    ) -> None:
        self._course_repository = course_repository
        self._enrolment_repository = enrolment_repository
        self._milestone_repository = milestone_repository
        self._submission_repository = submission_repository
        self._activity_repository = activity_repository
        self._lesson_repository = lesson_repository
        self._user_repository = user_repository

    async def list_submissions(self, course_id: uuid.UUID) -> list[dict]:
        """Return every submission made towards a course, newest first."""
        await self._require_course(course_id)
        submissions = await self._submission_repository.list_by_course(course_id)
        return [self._submission_row(submission) for submission in submissions]

    async def list_pending_submissions(self, course_id: uuid.UUID) -> list[dict]:
        """Return the submissions of a course that still await review."""
        await self._require_course(course_id)
        submissions = await self._submission_repository.list_pending_by_course(
            course_id
        )
        return [self._submission_row(submission) for submission in submissions]

    async def list_activities(
        self,
        course_id: uuid.UUID,
        limit: int = 50,
    ) -> list[LecturerActivity]:
        """Return the most recent activity recorded for a course."""
        await self._require_course(course_id)
        return await self._activity_repository.list_by_course(course_id, limit=limit)

    async def list_learner_progress(self, course_id: uuid.UUID) -> list[dict]:
        """
        Return the enrolled learners of a course with their progress.

        Progress is derived from lesson milestones: a learner has
        completed a lesson once its milestone exists.
        """
        course = await self._require_course(course_id)
        lessons = await self._lesson_repository.list_by_curriculum(course.curriculum_id)
        total_lessons = len(
            [lesson for lesson in lessons if lesson.status == LessonStatus.APPROVED]
        )

        enrolments = await self._enrolment_repository.list_active_by_course(course_id)
        users = await self._user_repository.list_by_ids(
            [enrolment.user_id for enrolment in enrolments]
        )
        users_by_id = {user.id: user for user in users}

        rows: list[dict] = []
        for enrolment in enrolments:
            learner = users_by_id.get(enrolment.user_id)
            milestones = await self._milestone_repository.list_for_enrolment(
                enrolment.id
            )
            submissions = await self._submission_repository.list_for_enrolment(
                enrolment.id
            )
            completed = len(milestones)
            rows.append(
                {
                    "enrolment_id": enrolment.id,
                    "user_id": enrolment.user_id,
                    "full_name": learner.full_name if learner else "",
                    "email": learner.email if learner else "",
                    "enrolled_at": enrolment.created_at,
                    "completed_lessons": completed,
                    "total_lessons": total_lessons,
                    "percentage": int((completed / total_lessons) * 100)
                    if total_lessons
                    else 0,
                    "submission_count": len(submissions),
                }
            )
        return rows

    async def grade_submission(
        self,
        submission_id: uuid.UUID,
        grader: User,
        grade: int | None,
        feedback: str | None,
    ) -> PracticalSubmission:
        """
        Grade a practical task submission.

        A grade without feedback is allowed, but feedback without a grade
        means the work is returned for revision instead of marked.
        """
        submission = await self._require_submission(submission_id)
        submission.status = SubmissionStatus.GRADED
        submission.grade = grade
        submission.feedback = feedback
        submission.graded_at = datetime.now(UTC)
        submission.graded_by_id = grader.id
        await self._submission_repository.commit()

        await self._record_submission_activity(
            submission=submission,
            grader=grader,
            event_type=LecturerActivityType.SUBMISSION_GRADED,
            summary=f"{grader.full_name} graded a practical task",
            details={"submission_id": str(submission.id), "grade": grade},
        )
        return submission

    async def return_submission(
        self,
        submission_id: uuid.UUID,
        grader: User,
        feedback: str | None,
    ) -> PracticalSubmission:
        """Return a submission to the learner for revision."""
        submission = await self._require_submission(submission_id)
        submission.status = SubmissionStatus.NEEDS_REVISION
        submission.grade = None
        submission.feedback = feedback
        submission.graded_at = datetime.now(UTC)
        submission.graded_by_id = grader.id
        await self._submission_repository.commit()

        await self._record_submission_activity(
            submission=submission,
            grader=grader,
            event_type=LecturerActivityType.SUBMISSION_RETURNED,
            summary=f"{grader.full_name} returned a practical task for revision",
            details={"submission_id": str(submission.id)},
        )
        return submission

    async def _require_course(self, course_id: uuid.UUID):
        course = await self._course_repository.get_by_id(course_id)
        if not course:
            raise CourseNotFound("Course not found.")
        return course

    async def _require_submission(
        self, submission_id: uuid.UUID
    ) -> PracticalSubmission:
        submission = await self._submission_repository.get_by_id(submission_id)
        if not submission:
            raise PracticalSubmissionNotFound("Submission not found.")
        return submission

    def _submission_row(self, submission: PracticalSubmission) -> dict:
        return {
            "id": submission.id,
            "enrolment_id": submission.enrolment_id,
            "block_id": submission.block_id,
            "lesson_id": submission.lesson_id,
            "content": submission.content,
            "status": submission.status,
            "grade": submission.grade,
            "feedback": submission.feedback,
            "submitted_at": submission.submitted_at,
            "graded_at": submission.graded_at,
            "graded_by_id": submission.graded_by_id,
        }

    async def _record_submission_activity(
        self,
        submission: PracticalSubmission,
        grader: User,
        event_type: LecturerActivityType,
        summary: str,
        details: dict,
    ) -> None:
        enrolment = await self._enrolment_repository.get_by_id(submission.enrolment_id)
        course_id = enrolment.course_id if enrolment else None
        if course_id is None:
            return
        await self._activity_repository.add(
            LecturerActivity(
                course_id=course_id,
                actor_user_id=grader.id,
                subject_user_id=enrolment.user_id if enrolment else None,
                event_type=event_type,
                summary=summary,
                details=details,
            )
        )
        await self._activity_repository.commit()
