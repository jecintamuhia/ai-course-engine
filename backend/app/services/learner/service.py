"""Learner portal service: enrolment, milestones and practical submissions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.core.exceptions import (
    CourseNotEnrollableError,
    CourseNotFound,
    EnrolmentNotFound,
    LessonNotFound,
    NotEnrolledError,
    SubmissionNotAllowedError,
)
from app.db.repositories.courses import CourseRepository
from app.db.repositories.learner_enrolments import LearnerEnrolmentRepository
from app.db.repositories.learner_milestones import LearnerMilestoneRepository
from app.db.repositories.lecturer_activities import LecturerActivityRepository
from app.db.repositories.lessons import LessonRepository
from app.db.repositories.practical_submissions import PracticalSubmissionRepository
from app.models.course import Course, CourseStatus
from app.models.learner_enrolment import EnrolmentStatus, LearnerEnrolment
from app.models.learner_milestone import LearnerMilestone
from app.models.lecturer_activity import LecturerActivity, LecturerActivityType
from app.models.lesson import Lesson, LessonStatus
from app.models.lesson_content_block import LessonBlockType
from app.models.practical_submission import PracticalSubmission, SubmissionStatus
from app.models.user import User


class LearnerPortalService:
    """
    Coordinates what a learner may do with a published course.

    Everything here is scoped to the calling account: the service never
    accepts another learner's identity, so a caller can only see and
    change their own enrolments, milestones and submissions.
    """

    def __init__(
        self,
        course_repository: CourseRepository,
        enrolment_repository: LearnerEnrolmentRepository,
        milestone_repository: LearnerMilestoneRepository,
        submission_repository: PracticalSubmissionRepository,
        lesson_repository: LessonRepository,
        activity_repository: LecturerActivityRepository,
    ) -> None:
        self._course_repository = course_repository
        self._enrolment_repository = enrolment_repository
        self._milestone_repository = milestone_repository
        self._submission_repository = submission_repository
        self._lesson_repository = lesson_repository
        self._activity_repository = activity_repository

    async def list_catalog(self) -> list[Course]:
        """Return the published courses a learner may enrol in."""
        return await self._course_repository.list_published()

    async def list_enrolled_courses(self, user: User) -> list[Course]:
        """
        Return the published courses the learner is actively enrolled in.

        Enrolment is what gates course content, so an unenrolled course
        never appears here even when it is published.
        """
        enrolments = await self._enrolment_repository.list_active_by_user(user.id)
        courses: list[Course] = []
        for enrolment in enrolments:
            course = await self._course_repository.get_by_id(enrolment.course_id)
            if course and course.status == CourseStatus.SYNCED:
                courses.append(course)
        return courses

    async def enrol(self, user: User, course_id: uuid.UUID) -> LearnerEnrolment:
        """
        Enrol the learner in a published course.

        Enrolment is idempotent: an already active enrolment is returned
        unchanged, and a withdrawn enrolment is reactivated so that the
        learner's milestones and submissions survive.
        """
        course = await self._course_repository.get_by_id(course_id)
        if not course:
            raise CourseNotFound("Course not found.")
        if course.status != CourseStatus.SYNCED:
            raise CourseNotEnrollableError("Course not available for enrolment.")

        existing = await self._enrolment_repository.get(user.id, course_id)
        if existing and existing.status == EnrolmentStatus.ACTIVE:
            return existing

        if existing:
            existing.status = EnrolmentStatus.ACTIVE
        else:
            existing = LearnerEnrolment(
                user_id=user.id,
                course_id=course_id,
                status=EnrolmentStatus.ACTIVE,
            )
            await self._enrolment_repository.add(existing)

        await self._enrolment_repository.commit()
        await self._record_activity(
            course_id=course_id,
            user=user,
            event_type=LecturerActivityType.ENROLLED,
            summary=f"{user.full_name} enrolled",
            details={"email": user.email},
        )
        return existing

    async def withdraw(self, user: User, course_id: uuid.UUID) -> LearnerEnrolment:
        """
        Withdraw the learner from a course.

        The enrolment row is kept so that progress history is not lost.
        """
        enrolment = await self._enrolment_repository.get_active(user.id, course_id)
        if not enrolment:
            raise EnrolmentNotFound("You are not actively enrolled in this course.")
        enrolment.status = EnrolmentStatus.WITHDRAWN
        await self._enrolment_repository.commit()
        await self._record_activity(
            course_id=course_id,
            user=user,
            event_type=LecturerActivityType.WITHDREW,
            summary=f"{user.full_name} withdrew",
            details={"email": user.email},
        )
        return enrolment

    async def get_course_detail(
        self,
        user: User,
        course_id: uuid.UUID,
    ) -> tuple[Course, list[Lesson], list[LearnerMilestone], list[dict]]:
        """
        Return a course with its lessons, the caller's milestones and the
        caller's submissions per block.

        Raises ``NotEnrolledError`` when the caller is not actively
        enrolled: course content is only opened to enrolled learners.
        """
        enrolment = await self._enrolment_repository.get_active(user.id, course_id)
        if not enrolment:
            raise NotEnrolledError("Enrol in this course to view its content.")

        course = await self._course_repository.get_by_id(course_id)
        if not course:
            raise CourseNotFound("Course not found.")

        lessons = [
            lesson
            for lesson in await self._lesson_repository.list_by_curriculum(
                course.curriculum_id
            )
            if lesson.status == LessonStatus.APPROVED
        ]
        milestones = await self._milestone_repository.list_for_enrolment(enrolment.id)
        submissions = await self._submission_repository.list_for_enrolment(enrolment.id)
        submissions_by_block = {
            submission.block_id: submission for submission in submissions
        }
        return course, lessons, milestones, submissions_by_block

    async def complete_lesson(
        self,
        user: User,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> LearnerMilestone:
        """Mark a lesson complete; completing twice keeps the first record."""
        enrolment = await self._require_active_enrolment(user, course_id)
        await self._require_course_lesson(course_id, lesson_id)

        existing = await self._milestone_repository.get(enrolment.id, lesson_id)
        if existing:
            return existing

        milestone = LearnerMilestone(
            enrolment_id=enrolment.id,
            lesson_id=lesson_id,
            completed_at=datetime.now(UTC),
        )
        await self._milestone_repository.add(milestone)
        await self._milestone_repository.commit()
        await self._record_activity(
            course_id=course_id,
            user=user,
            event_type=LecturerActivityType.LESSON_COMPLETED,
            summary=f"{user.full_name} completed a lesson",
            details={"lesson_id": str(lesson_id)},
        )
        return milestone

    async def undo_lesson_completion(
        self,
        user: User,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> bool:
        """Remove a lesson completion; returns whether one was removed."""
        enrolment = await self._require_active_enrolment(user, course_id)
        existing = await self._milestone_repository.get(enrolment.id, lesson_id)
        if not existing:
            return False
        await self._milestone_repository.delete(existing)
        await self._milestone_repository.commit()
        return True

    async def submit_practical_task(
        self,
        user: User,
        course_id: uuid.UUID,
        block_id: uuid.UUID,
        content: str,
    ) -> PracticalSubmission:
        """
        Submit a text/markdown hand-in for a practical task block.

        A learner may have one submission per practical block: re-submitting
        replaces the previous answer and clears any earlier grade, so the
        learner always sees the status of their latest work.
        """
        enrolment = await self._require_active_enrolment(user, course_id)

        block = await self._lesson_repository.get_block_by_id(block_id)
        if not block or block.block_type != LessonBlockType.PRACTICAL_TASK:
            raise SubmissionNotAllowedError(
                "This block does not accept practical task submissions."
            )
        try:
            await self._require_course_lesson(course_id, block.lesson_id)
        except LessonNotFound as exc:
            raise SubmissionNotAllowedError(
                "This block does not belong to this course."
            ) from exc

        now = datetime.now(UTC)
        existing = await self._submission_repository.get(enrolment.id, block_id)
        if existing:
            existing.content = content
            existing.status = SubmissionStatus.SUBMITTED
            existing.feedback = None
            existing.grade = None
            existing.graded_at = None
            existing.graded_by_id = None
            existing.submitted_at = now
            await self._submission_repository.commit()
            await self._record_activity(
                course_id=course_id,
                user=user,
                event_type=LecturerActivityType.SUBMISSION_RECEIVED,
                summary=f"{user.full_name} resubmitted a practical task",
                details={"block_id": str(block_id), "lesson_id": str(block.lesson_id)},
            )
            return existing

        submission = PracticalSubmission(
            enrolment_id=enrolment.id,
            block_id=block_id,
            lesson_id=block.lesson_id,
            content=content,
            status=SubmissionStatus.SUBMITTED,
            submitted_at=now,
        )
        await self._submission_repository.add(submission)
        await self._submission_repository.commit()
        await self._record_activity(
            course_id=course_id,
            user=user,
            event_type=LecturerActivityType.SUBMISSION_RECEIVED,
            summary=f"{user.full_name} submitted a practical task",
            details={"block_id": str(block_id), "lesson_id": str(block.lesson_id)},
        )
        return submission

    async def list_my_submissions(self, user: User) -> list[PracticalSubmission]:
        """Return every submission the learner has made, newest first."""
        submissions: list[PracticalSubmission] = []
        for enrolment in await self._enrolment_repository.list_by_user(user.id):
            submissions.extend(
                await self._submission_repository.list_for_enrolment(enrolment.id)
            )
        submissions.sort(key=lambda item: item.submitted_at, reverse=True)
        return submissions

    async def require_enrolment(
        self, user: User, course_id: uuid.UUID
    ) -> None:
        """Require that the caller is actively enrolled in a course.

        Raises ``NotEnrolledError`` when the caller has no active
        enrolment, and ``CourseNotFound`` when the course does not exist.
        Course content is only opened to enrolled learners.
        """
        enrolment = await self._enrolment_repository.get_active(user.id, course_id)
        if not enrolment:
            raise NotEnrolledError("Enrol in this course to view its content.")
        course = await self._course_repository.get_by_id(course_id)
        if not course:
            raise CourseNotFound("Course not found.")

    async def _require_active_enrolment(
        self,
        user: User,
        course_id: uuid.UUID,
    ) -> LearnerEnrolment:
        enrolment = await self._enrolment_repository.get_active(user.id, course_id)
        if not enrolment:
            raise NotEnrolledError("Enrol in this course to continue.")
        return enrolment

    async def _require_course_lesson(
        self,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> Lesson:
        """
        Return an approved lesson of the given course.

        A learner may only act on content that belongs to the course they
        enrolled in, so a lesson from another curriculum (or one that is
        still in review) is reported as missing rather than accepted.
        """
        course = await self._course_repository.get_by_id(course_id)
        if not course:
            raise CourseNotFound("Course not found.")

        lesson = await self._lesson_repository.get_by_id(lesson_id)
        if (
            not lesson
            or lesson.curriculum_id != course.curriculum_id
            or lesson.status != LessonStatus.APPROVED
        ):
            raise LessonNotFound("Lesson not found in this course.")
        return lesson

    async def _record_activity(
        self,
        course_id: uuid.UUID,
        user: User,
        event_type: LecturerActivityType,
        summary: str,
        details: dict,
    ) -> None:
        """Append an entry to the lecturer activity feed."""
        await self._activity_repository.add(
            LecturerActivity(
                course_id=course_id,
                actor_user_id=user.id,
                subject_user_id=user.id,
                event_type=event_type,
                summary=summary,
                details=details,
            )
        )
        await self._activity_repository.commit()
