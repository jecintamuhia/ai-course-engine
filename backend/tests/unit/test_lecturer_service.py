"""Unit tests for the lecturer review service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.exceptions import CourseNotFound, PracticalSubmissionNotFound
from app.models.course import Course, CourseStatus
from app.models.learner_enrolment import EnrolmentStatus, LearnerEnrolment
from app.models.learner_milestone import LearnerMilestone
from app.models.lesson import Lesson, LessonStatus
from app.models.practical_submission import PracticalSubmission, SubmissionStatus
from app.models.user import User, UserRole
from app.services.lecturer.service import LecturerReviewService


def _user(role: UserRole = UserRole.LECTURER) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email="lecturer@example.com",
        password_hash="_",
        full_name="Dr. Lecturer",
        role=role,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _course() -> Course:
    now = datetime.now(UTC)
    return Course(
        id=uuid.uuid4(),
        curriculum_id=uuid.uuid4(),
        title="Intro to Statistics",
        fullname="Intro to Statistics",
        shortname="Stats",
        idnumber="ai-ece-1",
        moodle_course_id=7,
        moodle_url="https://elearning.skillupafrica.co.ke/course/view.php?id=7",
        status=CourseStatus.SYNCED,
        sections_published=4,
        resources_published=12,
        last_sync_at=now,
        sync_error=None,
        created_at=now,
        updated_at=now,
    )


def _lesson() -> Lesson:
    now = datetime.now(UTC)
    lesson = Lesson(
        id=uuid.uuid4(),
        curriculum_id=uuid.uuid4(),
        curriculum_unit_id=uuid.uuid4(),
        week_number=1,
        order_index=0,
        title="Describing Data",
        description="How to describe a dataset.",
        learning_objectives=["Summarise a dataset."],
        estimated_workload_minutes=45,
        status=LessonStatus.APPROVED,
        generation_errors=[],
    )
    lesson.created_at = now
    lesson.updated_at = now
    return lesson


def _service(
    *,
    course: Course | None = None,
    submission: PracticalSubmission | None = None,
    enrolment: LearnerEnrolment | None = None,
    milestones: list[LearnerMilestone] | None = None,
    users: list[User] | None = None,
):
    """Build a lecturer review service backed by mocked repositories."""
    course_repository = MagicMock()
    course_repository.get_by_id = AsyncMock(return_value=course)

    enrolment_repository = MagicMock()
    enrolment_repository.get_by_id = AsyncMock(return_value=enrolment)
    enrolment_repository.list_active_by_course = AsyncMock(
        return_value=[enrolment] if enrolment else []
    )

    milestone_repository = MagicMock()
    milestone_repository.list_for_enrolment = AsyncMock(return_value=milestones or [])

    submission_repository = MagicMock()
    submission_repository.get_by_id = AsyncMock(return_value=submission)
    submission_repository.list_by_course = AsyncMock(
        return_value=[submission] if submission else []
    )
    submission_repository.list_pending_by_course = AsyncMock(
        return_value=[submission] if submission else []
    )
    submission_repository.list_for_enrolment = AsyncMock(
        return_value=[submission] if submission else []
    )
    submission_repository.commit = AsyncMock()

    activity_repository = MagicMock()
    activity_repository.add = AsyncMock(side_effect=lambda item: item)
    activity_repository.commit = AsyncMock()
    activity_repository.list_by_course = AsyncMock(return_value=[])

    lesson_repository = MagicMock()
    lesson_repository.list_by_curriculum = AsyncMock(return_value=[_lesson()])

    user_repository = MagicMock()
    user_repository.list_by_ids = AsyncMock(return_value=users or [])

    service = LecturerReviewService(
        course_repository,
        enrolment_repository,
        milestone_repository,
        submission_repository,
        activity_repository,
        lesson_repository,
        user_repository,
    )
    return service, {
        "course": course_repository,
        "enrolment": enrolment_repository,
        "milestone": milestone_repository,
        "submission": submission_repository,
        "activity": activity_repository,
        "lesson": lesson_repository,
        "user": user_repository,
    }


async def test_listing_submissions_requires_a_known_course() -> None:
    service, _ = _service(course=None)

    with pytest.raises(CourseNotFound):
        await service.list_submissions(uuid.uuid4())


async def test_listing_submissions_returns_the_course_hand_ins() -> None:
    course = _course()
    submission = PracticalSubmission(
        id=uuid.uuid4(),
        enrolment_id=uuid.uuid4(),
        block_id=uuid.uuid4(),
        lesson_id=uuid.uuid4(),
        content="# Answer",
        status=SubmissionStatus.SUBMITTED,
        grade=None,
        feedback=None,
        submitted_at=datetime.now(UTC),
        graded_at=None,
        graded_by_id=None,
    )
    service, _ = _service(course=course, submission=submission)

    rows = await service.list_submissions(course.id)

    assert len(rows) == 1
    assert rows[0]["content"] == "# Answer"
    assert rows[0]["status"] == "submitted"


async def test_grading_stores_the_mark_and_the_grader() -> None:
    course = _course()
    grader = _user()
    submission = PracticalSubmission(
        id=uuid.uuid4(),
        enrolment_id=uuid.uuid4(),
        block_id=uuid.uuid4(),
        lesson_id=uuid.uuid4(),
        content="# Answer",
        status=SubmissionStatus.SUBMITTED,
        grade=None,
        feedback=None,
        submitted_at=datetime.now(UTC),
        graded_at=None,
        graded_by_id=None,
    )
    service, _ = _service(course=course, submission=submission)

    graded = await service.grade_submission(submission.id, grader, 88, "Nice work")

    assert graded.status == SubmissionStatus.GRADED
    assert graded.grade == 88
    assert graded.feedback == "Nice work"
    assert graded.graded_by_id == grader.id
    assert graded.graded_at is not None


async def test_grading_an_unknown_submission_is_refused() -> None:
    service, _ = _service(course=_course())

    with pytest.raises(PracticalSubmissionNotFound):
        await service.grade_submission(uuid.uuid4(), _user(), 50, None)


async def test_returning_a_submission_clears_the_grade() -> None:
    course = _course()
    submission = PracticalSubmission(
        id=uuid.uuid4(),
        enrolment_id=uuid.uuid4(),
        block_id=uuid.uuid4(),
        lesson_id=uuid.uuid4(),
        content="# Answer",
        status=SubmissionStatus.GRADED,
        grade=70,
        feedback="Fine",
        submitted_at=datetime.now(UTC),
        graded_at=datetime.now(UTC),
        graded_by_id=uuid.uuid4(),
    )
    service, _ = _service(course=course, submission=submission)

    returned = await service.return_submission(
        submission.id,
        _user(),
        "Please add detail",
    )

    assert returned.status == SubmissionStatus.NEEDS_REVISION
    assert returned.grade is None
    assert returned.feedback == "Please add detail"


async def test_learner_progress_reports_completed_lessons() -> None:
    course = _course()
    learner = _user(role=UserRole.STUDENT)
    enrolment = LearnerEnrolment(
        id=uuid.uuid4(),
        user_id=learner.id,
        course_id=course.id,
        status=EnrolmentStatus.ACTIVE,
    )
    milestone = LearnerMilestone(
        id=uuid.uuid4(),
        enrolment_id=enrolment.id,
        lesson_id=uuid.uuid4(),
        completed_at=datetime.now(UTC),
    )
    service, _ = _service(
        course=course,
        enrolment=enrolment,
        milestones=[milestone],
        users=[learner],
    )

    rows = await service.list_learner_progress(course.id)

    assert len(rows) == 1
    assert rows[0]["email"] == learner.email
    assert rows[0]["completed_lessons"] == 1
    assert rows[0]["total_lessons"] == 1
    assert rows[0]["percentage"] == 100
