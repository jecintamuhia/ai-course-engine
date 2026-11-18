"""Unit tests for the learner portal service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.exceptions import (
    CourseNotEnrollableError,
    CourseNotFound,
    EnrolmentNotFound,
    LessonNotFound,
    NotEnrolledError,
    SubmissionNotAllowedError,
)
from app.models.course import Course, CourseStatus
from app.models.learner_enrolment import EnrolmentStatus, LearnerEnrolment
from app.models.learner_milestone import LearnerMilestone
from app.models.lesson import Lesson, LessonStatus
from app.models.lesson_content_block import (
    BlockReviewStatus,
    LessonBlockType,
    LessonContentBlock,
)
from app.models.practical_submission import PracticalSubmission, SubmissionStatus
from app.models.user import User, UserRole
from app.services.learner.service import LearnerPortalService


def _user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email="learner@example.com",
        password_hash="_",
        full_name="Ada Learner",
        role=UserRole.STUDENT,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _course(status: CourseStatus = CourseStatus.SYNCED) -> Course:
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
        status=status,
        sections_published=4,
        resources_published=12,
        last_sync_at=now,
        sync_error=None,
        created_at=now,
        updated_at=now,
    )


def _lesson(
    block_type: LessonBlockType = LessonBlockType.PRACTICAL_TASK,
    status: LessonStatus = LessonStatus.APPROVED,
) -> Lesson:
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
        status=status,
        generation_errors=[],
    )
    lesson.created_at = now
    lesson.updated_at = now
    block = LessonContentBlock(
        id=uuid.uuid4(),
        lesson_id=lesson.id,
        block_type=block_type,
        order_index=0,
        title="Practical task",
        payload={"prompt": "Summarise the data."},
        review_status=BlockReviewStatus.APPROVED,
    )
    block.created_at = now
    block.updated_at = now
    lesson.content_blocks = [block]
    return lesson


def _service(
    *,
    course: Course | None = None,
    enrolment: LearnerEnrolment | None = None,
    lesson: Lesson | None = None,
    align_lesson: bool = True,
):
    """Build a learner portal service backed by mocked repositories."""
    course_repository = MagicMock()
    course_repository.get_by_id = AsyncMock(return_value=course)
    course_repository.list_published = AsyncMock(
        return_value=[course] if course else []
    )

    enrolment_repository = MagicMock()
    enrolment_repository.get = AsyncMock(return_value=enrolment)
    enrolment_repository.get_active = AsyncMock(return_value=enrolment)
    enrolment_repository.list_active_by_user = AsyncMock(
        return_value=[enrolment] if enrolment else []
    )
    enrolment_repository.list_by_user = AsyncMock(
        return_value=[enrolment] if enrolment else []
    )
    enrolment_repository.add = AsyncMock(side_effect=lambda item: item)
    enrolment_repository.commit = AsyncMock()

    milestone_repository = MagicMock()
    milestone_repository.get = AsyncMock(return_value=None)
    milestone_repository.list_for_enrolment = AsyncMock(return_value=[])
    milestone_repository.add = AsyncMock(side_effect=lambda item: item)
    milestone_repository.delete = AsyncMock()
    milestone_repository.commit = AsyncMock()

    submission_repository = MagicMock()
    submission_repository.get = AsyncMock(return_value=None)
    submission_repository.list_for_enrolment = AsyncMock(return_value=[])
    submission_repository.add = AsyncMock(side_effect=lambda item: item)
    submission_repository.commit = AsyncMock()

    lesson_repository = MagicMock()
    if align_lesson and course is not None and lesson is not None:
        lesson.curriculum_id = course.curriculum_id
    lesson_repository.list_by_curriculum = AsyncMock(
        return_value=[lesson] if lesson else []
    )
    lesson_repository.get_by_id = AsyncMock(return_value=lesson)
    lesson_repository.get_block_by_id = AsyncMock(
        return_value=lesson.content_blocks[0] if lesson else None
    )

    activity_repository = MagicMock()
    activity_repository.add = AsyncMock(side_effect=lambda item: item)
    activity_repository.commit = AsyncMock()

    service = LearnerPortalService(
        course_repository,
        enrolment_repository,
        milestone_repository,
        submission_repository,
        lesson_repository,
        activity_repository,
    )
    return service, {
        "course": course_repository,
        "enrolment": enrolment_repository,
        "milestone": milestone_repository,
        "submission": submission_repository,
        "lesson": lesson_repository,
        "activity": activity_repository,
    }


async def test_enrol_creates_an_active_enrolment() -> None:
    course = _course()
    service, repos = _service(course=course)

    enrolment = await service.enrol(_user(), course.id)

    assert enrolment.status == EnrolmentStatus.ACTIVE
    assert enrolment.course_id == course.id
    repos["enrolment"].commit.assert_awaited()


async def test_enrol_records_activity_for_the_lecturer_feed() -> None:
    course = _course()
    service, repos = _service(course=course)

    await service.enrol(_user(), course.id)

    repos["activity"].add.assert_awaited_once()
    activity = repos["activity"].add.await_args.args[0]
    assert activity.event_type.value == "enrolled"


async def test_enrol_is_idempotent_for_an_active_enrolment() -> None:
    course = _course()
    existing = LearnerEnrolment(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        course_id=course.id,
        status=EnrolmentStatus.ACTIVE,
    )
    service, repos = _service(course=course, enrolment=existing)

    enrolment = await service.enrol(_user(), course.id)

    assert enrolment is existing
    repos["enrolment"].add.assert_not_awaited()


async def test_enrol_reactivates_a_withdrawn_enrolment() -> None:
    course = _course()
    existing = LearnerEnrolment(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        course_id=course.id,
        status=EnrolmentStatus.WITHDRAWN,
    )
    service, repos = _service(course=course, enrolment=existing)

    enrolment = await service.enrol(_user(), course.id)

    assert enrolment.status == EnrolmentStatus.ACTIVE
    repos["enrolment"].add.assert_not_awaited()


async def test_enrol_rejects_an_unknown_course() -> None:
    service, _ = _service(course=None)

    with pytest.raises(CourseNotFound):
        await service.enrol(_user(), uuid.uuid4())


async def test_enrol_rejects_a_course_that_never_reached_moodle() -> None:
    course = _course(status=CourseStatus.SYNC_FAILED)
    service, _ = _service(course=course)

    with pytest.raises(CourseNotEnrollableError):
        await service.enrol(_user(), course.id)


async def test_withdraw_keeps_the_enrolment_record() -> None:
    course = _course()
    enrolment = LearnerEnrolment(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        course_id=course.id,
        status=EnrolmentStatus.ACTIVE,
    )
    service, repos = _service(course=course, enrolment=enrolment)

    result = await service.withdraw(_user(), course.id)

    assert result.status == EnrolmentStatus.WITHDRAWN
    repos["activity"].add.assert_awaited_once()


async def test_withdraw_requires_an_active_enrolment() -> None:
    service, _ = _service(course=_course())

    with pytest.raises(EnrolmentNotFound):
        await service.withdraw(_user(), uuid.uuid4())


async def test_course_detail_requires_an_enrolment() -> None:
    service, _ = _service(course=_course())

    with pytest.raises(NotEnrolledError):
        await service.get_course_detail(_user(), uuid.uuid4())


async def test_course_detail_returns_lessons_and_milestones() -> None:
    course = _course()
    lesson = _lesson()
    enrolment = LearnerEnrolment(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        course_id=course.id,
        status=EnrolmentStatus.ACTIVE,
    )
    milestone = LearnerMilestone(
        id=uuid.uuid4(),
        enrolment_id=enrolment.id,
        lesson_id=lesson.id,
        completed_at=datetime.now(UTC),
    )
    service, repos = _service(course=course, enrolment=enrolment, lesson=lesson)
    repos["milestone"].list_for_enrolment = AsyncMock(return_value=[milestone])

    returned_course, lessons, milestones, submissions = await service.get_course_detail(
        _user(),
        course.id,
    )

    assert returned_course.id == course.id
    assert [item.id for item in lessons] == [lesson.id]
    assert [item.id for item in milestones] == [milestone.id]
    assert submissions == {}


async def test_course_detail_hides_lessons_that_are_not_approved() -> None:
    course = _course()
    lesson = _lesson(status=LessonStatus.DRAFT)
    enrolment = LearnerEnrolment(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        course_id=course.id,
        status=EnrolmentStatus.ACTIVE,
    )
    service, _ = _service(course=course, enrolment=enrolment, lesson=lesson)

    _, lessons, _, _ = await service.get_course_detail(_user(), course.id)

    assert lessons == []


async def test_completing_a_lesson_records_one_milestone() -> None:
    course = _course()
    lesson = _lesson()
    enrolment = LearnerEnrolment(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        course_id=course.id,
        status=EnrolmentStatus.ACTIVE,
    )
    service, repos = _service(course=course, enrolment=enrolment, lesson=lesson)

    milestone = await service.complete_lesson(_user(), course.id, lesson.id)

    assert isinstance(milestone, LearnerMilestone)
    assert milestone.enrolment_id == enrolment.id
    assert milestone.lesson_id == lesson.id
    repos["milestone"].add.assert_awaited_once()


async def test_completing_a_lesson_twice_keeps_the_first_record() -> None:
    course = _course()
    lesson = _lesson()
    enrolment = LearnerEnrolment(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        course_id=course.id,
        status=EnrolmentStatus.ACTIVE,
    )
    existing = LearnerMilestone(
        id=uuid.uuid4(),
        enrolment_id=enrolment.id,
        lesson_id=lesson.id,
        completed_at=datetime.now(UTC),
    )
    service, repos = _service(course=course, enrolment=enrolment, lesson=lesson)
    repos["milestone"].get = AsyncMock(return_value=existing)

    milestone = await service.complete_lesson(_user(), course.id, existing.lesson_id)

    assert milestone is existing
    repos["milestone"].add.assert_not_awaited()


async def test_completing_a_lesson_from_another_course_is_refused() -> None:
    course = _course()
    lesson = _lesson()
    enrolment = LearnerEnrolment(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        course_id=course.id,
        status=EnrolmentStatus.ACTIVE,
    )
    service, repos = _service(
        course=course,
        enrolment=enrolment,
        lesson=lesson,
        align_lesson=False,
    )

    with pytest.raises(LessonNotFound):
        await service.complete_lesson(_user(), course.id, lesson.id)
    repos["milestone"].add.assert_not_awaited()


async def test_completing_a_lesson_that_is_not_approved_is_refused() -> None:
    course = _course()
    lesson = _lesson(status=LessonStatus.DRAFT)
    enrolment = LearnerEnrolment(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        course_id=course.id,
        status=EnrolmentStatus.ACTIVE,
    )
    service, repos = _service(course=course, enrolment=enrolment, lesson=lesson)

    with pytest.raises(LessonNotFound):
        await service.complete_lesson(_user(), course.id, lesson.id)
    repos["milestone"].add.assert_not_awaited()


async def test_completing_a_lesson_requires_an_enrolment() -> None:
    service, _ = _service(course=_course())

    with pytest.raises(NotEnrolledError):
        await service.complete_lesson(_user(), uuid.uuid4(), uuid.uuid4())


async def test_undoing_a_completion_removes_the_milestone() -> None:
    course = _course()
    enrolment = LearnerEnrolment(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        course_id=course.id,
        status=EnrolmentStatus.ACTIVE,
    )
    existing = LearnerMilestone(
        id=uuid.uuid4(),
        enrolment_id=enrolment.id,
        lesson_id=uuid.uuid4(),
        completed_at=datetime.now(UTC),
    )
    service, repos = _service(course=course, enrolment=enrolment)
    repos["milestone"].get = AsyncMock(return_value=existing)

    removed = await service.undo_lesson_completion(
        _user(), course.id, existing.lesson_id
    )

    assert removed is True
    repos["milestone"].delete.assert_awaited_once()


async def test_submitting_a_practical_task_stores_the_content() -> None:
    course = _course()
    lesson = _lesson()
    enrolment = LearnerEnrolment(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        course_id=course.id,
        status=EnrolmentStatus.ACTIVE,
    )
    service, repos = _service(course=course, enrolment=enrolment, lesson=lesson)

    submission = await service.submit_practical_task(
        _user(),
        course.id,
        lesson.content_blocks[0].id,
        "# My answer",
    )

    assert isinstance(submission, PracticalSubmission)
    assert submission.content == "# My answer"
    assert submission.status == SubmissionStatus.SUBMITTED
    repos["submission"].add.assert_awaited_once()


async def test_resubmitting_replaces_the_previous_answer() -> None:
    course = _course()
    lesson = _lesson()
    enrolment = LearnerEnrolment(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        course_id=course.id,
        status=EnrolmentStatus.ACTIVE,
    )
    existing = PracticalSubmission(
        id=uuid.uuid4(),
        enrolment_id=enrolment.id,
        block_id=lesson.content_blocks[0].id,
        lesson_id=lesson.id,
        content="Old answer",
        status=SubmissionStatus.GRADED,
        grade=70,
        feedback="Fine",
        submitted_at=datetime.now(UTC),
        graded_at=datetime.now(UTC),
        graded_by_id=uuid.uuid4(),
    )
    service, repos = _service(course=course, enrolment=enrolment, lesson=lesson)
    repos["submission"].get = AsyncMock(return_value=existing)

    submission = await service.submit_practical_task(
        _user(),
        course.id,
        lesson.content_blocks[0].id,
        "New answer",
    )

    assert submission.content == "New answer"
    assert submission.grade is None
    assert submission.feedback is None
    assert submission.status == SubmissionStatus.SUBMITTED
    repos["submission"].add.assert_not_awaited()


async def test_submitting_to_a_non_practical_block_is_refused() -> None:
    course = _course()
    lesson = _lesson(block_type=LessonBlockType.TEXT)
    enrolment = LearnerEnrolment(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        course_id=course.id,
        status=EnrolmentStatus.ACTIVE,
    )
    service, _ = _service(course=course, enrolment=enrolment, lesson=lesson)

    with pytest.raises(SubmissionNotAllowedError):
        await service.submit_practical_task(
            _user(),
            course.id,
            lesson.content_blocks[0].id,
            "Answer",
        )


async def test_submitting_to_a_block_from_another_course_is_refused() -> None:
    course = _course()
    lesson = _lesson()
    enrolment = LearnerEnrolment(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        course_id=course.id,
        status=EnrolmentStatus.ACTIVE,
    )
    service, repos = _service(
        course=course,
        enrolment=enrolment,
        lesson=lesson,
        align_lesson=False,
    )

    with pytest.raises(SubmissionNotAllowedError):
        await service.submit_practical_task(
            _user(),
            course.id,
            lesson.content_blocks[0].id,
            "Answer",
        )
    repos["submission"].add.assert_not_awaited()


async def test_submitting_requires_an_enrolment() -> None:
    service, _ = _service(course=_course())

    with pytest.raises(NotEnrolledError):
        await service.submit_practical_task(
            _user(), uuid.uuid4(), uuid.uuid4(), "Answer"
        )
