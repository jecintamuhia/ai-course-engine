"""Unit tests for final-assessment scoring and certificate issuance."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.core.exceptions import (
    AssessmentNotAvailableError,
    AssessmentSubmissionError,
    CertificateNotEligibleError,
    CertificateNotFound,
    NotEnrolledError,
)
from app.models.assessment import Assessment, AssessmentStatus, AssessmentType
from app.models.course import Course, CourseStatus
from app.models.learner_enrolment import EnrolmentStatus, LearnerEnrolment
from app.models.learner_milestone import LearnerMilestone
from app.models.lesson import Lesson, LessonStatus
from app.models.user import User, UserRole
from app.schemas.learner_assessment import AssessmentAnswer, AssessmentSubmitRequest
from app.services.learner.assessment import LearnerAssessmentService


class FakeCourseRepository:
    def __init__(self, course: Course | None):
        self.course = course

    async def get_by_id(self, course_id):
        return self.course if self.course and self.course.id == course_id else None


class FakeEnrolmentRepository:
    def __init__(self, enrolment: LearnerEnrolment | None):
        self.enrolment = enrolment

    async def get_active(self, user_id, course_id):
        if (
            self.enrolment
            and self.enrolment.user_id == user_id
            and self.enrolment.course_id == course_id
            and self.enrolment.status == EnrolmentStatus.ACTIVE
        ):
            return self.enrolment
        return None


class FakeMilestoneRepository:
    def __init__(self, lesson_ids: list[uuid.UUID]):
        self.lesson_ids = lesson_ids

    async def list_for_enrolment(self, enrolment_id):
        return [
            LearnerMilestone(
                id=uuid.uuid4(),
                enrolment_id=enrolment_id,
                lesson_id=lesson_id,
                completed_at=datetime.now(UTC),
            )
            for lesson_id in self.lesson_ids
        ]


class FakeLessonRepository:
    def __init__(self, lessons: list[Lesson]):
        self.lessons = lessons

    async def list_publishable_by_curriculum(self, curriculum_id):
        return [
            lesson
            for lesson in self.lessons
            if lesson.curriculum_id == curriculum_id
            and lesson.status == LessonStatus.APPROVED
        ]


class FakeAssessmentRepository:
    def __init__(self, assessments: list[Assessment]):
        self.assessments = assessments

    async def list_by_curriculum(self, curriculum_id):
        return [
            assessment
            for assessment in self.assessments
            if assessment.curriculum_id == curriculum_id
        ]


class FakeAttemptRepository:
    def __init__(self):
        self.rows: list = []

    async def add(self, attempt):
        attempt.id = attempt.id or uuid.uuid4()
        self.rows.append(attempt)
        return attempt

    async def list_for_enrolment(self, assessment_id, enrolment_id):
        return [
            row
            for row in self.rows
            if row.assessment_id == assessment_id
            and row.enrolment_id == enrolment_id
        ]

    async def count_for_enrolment(self, assessment_id, enrolment_id):
        return len(await self.list_for_enrolment(assessment_id, enrolment_id))

    async def best_passing(self, assessment_id, enrolment_id):
        passing = [
            row
            for row in await self.list_for_enrolment(assessment_id, enrolment_id)
            if row.passed
        ]
        if not passing:
            return None
        return sorted(
            passing, key=lambda row: (-row.score_percent, row.attempt_number)
        )[0]

    async def commit(self):
        return None

    async def rollback(self):
        return None


class FakeCertificateRepository:
    def __init__(self):
        self.rows: list = []

    async def add(self, certificate):
        self.rows.append(certificate)
        return certificate

    async def get_for_learner_course(self, user_id, course_id):
        for row in self.rows:
            if row.user_id == user_id and row.course_id == course_id:
                return row
        return None

    async def list_for_user(self, user_id):
        return [row for row in self.rows if row.user_id == user_id]

    async def get_by_reference(self, reference):
        for row in self.rows:
            if row.reference == reference:
                return row
        return None

    async def commit(self):
        return None

    async def rollback(self):
        return None


def _user(full_name: str = "Ama Mensah") -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
        full_name=full_name,
        role=UserRole.STUDENT,
        is_active=True,
    )


def _course(curriculum_id: uuid.UUID) -> Course:
    now = datetime.now(UTC)
    return Course(
        id=uuid.uuid4(),
        curriculum_id=curriculum_id,
        title="Introduction to Agribusiness",
        fullname="Introduction to Agribusiness",
        shortname="agri101",
        idnumber=f"ai-ece-{uuid.uuid4()}",
        status=CourseStatus.SYNCED,
        sections_published=1,
        resources_published=1,
        created_at=now,
        updated_at=now,
    )


def _lesson(curriculum_id: uuid.UUID) -> Lesson:
    lesson = Lesson(
        id=uuid.uuid4(),
        curriculum_id=curriculum_id,
        curriculum_unit_id=uuid.uuid4(),
        week_number=1,
        order_index=0,
        title="Market research",
        description="",
        learning_objectives=[],
        estimated_workload_minutes=30,
        status=LessonStatus.APPROVED,
        generation_errors=[],
    )
    lesson.created_at = datetime.now(UTC)
    lesson.updated_at = datetime.now(UTC)
    return lesson


def _items() -> list[dict]:
    return [
        {
            "kind": "multiple_choice",
            "prompt": "Which record keeps stock counts?",
            "learning_objective": "Track inventory",
            "difficulty": "easy",
            "options": [
                {"id": "a", "text": "Inventory ledger"},
                {"id": "b", "text": "Payroll sheet"},
            ],
            "correct_option_id": "a",
            "correct_answer": "Inventory ledger",
            "explanation": "An inventory ledger records stock movements.",
        },
        {
            "kind": "true_false",
            "prompt": "Cash flow and profit are the same thing.",
            "learning_objective": "Read financial statements",
            "difficulty": "medium",
            "options": [
                {"id": "true", "text": "True"},
                {"id": "false", "text": "False"},
            ],
            "correct_option_id": "false",
            "explanation": "Profit is accrual-based; cash flow is movement of cash.",
        },
        {
            "kind": "short_answer",
            "prompt": "Name the document that lists money owed to you.",
            "learning_objective": "Manage receivables",
            "difficulty": "hard",
            "correct_answer": "accounts receivable ledger",
            "explanation": "",
        },
        {
            "kind": "scenario",
            "prompt": "Explain how you would price a new product.",
            "learning_objective": "Price products",
            "difficulty": "hard",
            "rubric": "Mentions cost, competition and value.",
        },
    ]


def _assessment(curriculum_id: uuid.UUID) -> Assessment:
    now = datetime.now(UTC)
    return Assessment(
        id=uuid.uuid4(),
        curriculum_id=curriculum_id,
        curriculum_unit_id=None,
        week_number=None,
        title="Final assessment",
        description="Covers the whole course.",
        assessment_type=AssessmentType.FINAL,
        learning_objectives=[],
        estimated_minutes=60,
        items=_items(),
        alignment=[],
        status=AssessmentStatus.APPROVED,
        generation_errors=[],
        created_at=now,
        updated_at=now,
    )


def _service(
    *,
    completed_lessons: int = 1,
    lessons: int = 1,
    assessment: Assessment | None = None,
) -> tuple[
    LearnerAssessmentService,
    User,
    Course,
    FakeAttemptRepository,
    FakeCertificateRepository,
]:
    user = _user()
    course = _course(uuid.uuid4())
    enrollment = LearnerEnrolment(
        id=uuid.uuid4(),
        user_id=user.id,
        course_id=course.id,
        status=EnrolmentStatus.ACTIVE,
    )
    enrollment.created_at = datetime.now(UTC)
    enrollment.updated_at = datetime.now(UTC)
    course_lessons = [_lesson(course.curriculum_id) for _ in range(lessons)]
    final = assessment or _assessment(course.curriculum_id)
    attempts = FakeAttemptRepository()
    certificates = FakeCertificateRepository()
    service = LearnerAssessmentService(
        FakeCourseRepository(course),
        FakeEnrolmentRepository(enrollment),
        FakeMilestoneRepository(
            [lesson.id for lesson in course_lessons[:completed_lessons]]
        ),
        FakeLessonRepository(course_lessons),
        FakeAssessmentRepository([final]),
        attempts,
        certificates,
        pass_percent=70,
    )
    return service, user, course, attempts, certificates


def _answers(*, include_short: bool = True) -> AssessmentSubmitRequest:
    answers = [
        AssessmentAnswer(item_index=0, option_id="a"),
        AssessmentAnswer(item_index=1, option_id="false"),
    ]
    if include_short:
        answers.append(
            AssessmentAnswer(item_index=2, answer="  Accounts   Receivable Ledger. ")
        )
    return AssessmentSubmitRequest(answers=answers)


@pytest.mark.asyncio
async def test_final_assessment_hides_answers_and_reports_progress():
    service, user, course, _, _ = _service(completed_lessons=1, lessons=1)

    view = await service.get_final_assessment(user, course.id)

    assert view.pass_percent == 70
    assert view.auto_gradable_count == 3
    assert view.total_items == 4
    assert view.all_lessons_completed is True
    assert view.passed is False
    assert view.certificate is None
    assert view.questions[0].options[0].text == "Inventory ledger"
    assert not hasattr(view.questions[0], "correct_option_id")
    serialized = view.model_dump_json()
    assert "Inventory ledger records" not in serialized
    assert "accounts receivable ledger" not in serialized.lower()


@pytest.mark.asyncio
async def test_submit_scores_objective_items_and_ignores_open_ended():
    service, user, course, attempts, _ = _service()

    result = await service.submit_attempt(user, course.id, _answers())

    assert result.attempt_number == 1
    assert result.auto_gradable_count == 3
    assert result.correct_count == 3
    assert result.score_percent == 100
    assert result.passed is True
    assert attempts.rows[0].answers[0]["item_index"] == 0
    open_ended = next(item for item in result.results if item.kind == "scenario")
    assert open_ended.auto_graded is False
    assert open_ended.correct is None


@pytest.mark.asyncio
async def test_submit_fails_below_pass_mark():
    service, user, course, _, _ = _service()

    result = await service.submit_attempt(
        user,
        course.id,
        AssessmentSubmitRequest(
            answers=[
                AssessmentAnswer(item_index=0, option_id="b"),
                AssessmentAnswer(item_index=1, option_id="false"),
                AssessmentAnswer(item_index=2, answer="wrong"),
            ]
        ),
    )

    assert result.correct_count == 1
    assert result.score_percent == 33
    assert result.passed is False


@pytest.mark.asyncio
async def test_submit_rejects_missing_gradable_answer():
    service, user, course, _, _ = _service()

    with pytest.raises(AssessmentSubmissionError) as excinfo:
        await service.submit_attempt(
            user,
            course.id,
            AssessmentSubmitRequest(
                answers=[AssessmentAnswer(item_index=0, option_id="a")]
            ),
        )

    assert excinfo.value.details == {"missing_item_indexes": [1, 2]}


@pytest.mark.asyncio
async def test_submit_rejects_duplicate_and_unknown_indexes():
    service, user, course, _, _ = _service()

    with pytest.raises(AssessmentSubmissionError):
        await service.submit_attempt(
            user,
            course.id,
            AssessmentSubmitRequest(
                answers=[
                    AssessmentAnswer(item_index=0, option_id="a"),
                    AssessmentAnswer(item_index=0, option_id="a"),
                ]
            ),
        )

    with pytest.raises(AssessmentSubmissionError):
        await service.submit_attempt(
            user,
            course.id,
            AssessmentSubmitRequest(
                answers=[AssessmentAnswer(item_index=99, option_id="a")]
            ),
        )


@pytest.mark.asyncio
async def test_retry_records_a_new_attempt_and_keeps_best():
    service, user, course, attempts, _ = _service()

    first = await service.submit_attempt(
        user,
        course.id,
        AssessmentSubmitRequest(
            answers=[
                AssessmentAnswer(item_index=0, option_id="b"),
                AssessmentAnswer(item_index=1, option_id="true"),
                AssessmentAnswer(item_index=2, answer="wrong"),
            ]
        ),
    )
    second = await service.submit_attempt(user, course.id, _answers())

    assert first.attempt_number == 1
    assert second.attempt_number == 2
    assert len(attempts.rows) == 2
    view = await service.get_final_assessment(user, course.id)
    assert view.passed is True
    assert view.best_score_percent == 100
    assert view.best_attempt_id == second.id
    assert [attempt.attempt_number for attempt in view.attempts] == [1, 2]


@pytest.mark.asyncio
async def test_certificate_requires_every_lesson_complete():
    service, user, course, _, _ = _service(completed_lessons=1, lessons=2)
    await service.submit_attempt(user, course.id, _answers())

    with pytest.raises(CertificateNotEligibleError) as excinfo:
        await service.issue_certificate(user, course.id)

    assert excinfo.value.details == {"remaining_lessons": 1}


@pytest.mark.asyncio
async def test_certificate_requires_passing_attempt():
    service, user, course, _, _ = _service()

    with pytest.raises(CertificateNotEligibleError):
        await service.issue_certificate(user, course.id)


@pytest.mark.asyncio
async def test_certificate_issued_once_and_verifiable():
    service, user, course, _, certificates = _service()
    await service.submit_attempt(user, course.id, _answers())

    first = await service.issue_certificate(user, course.id)
    second = await service.issue_certificate(user, course.id)

    assert first.reference == second.reference
    assert first.reference.startswith("SKU-")
    assert first.learner_name == user.full_name
    assert first.course_title == course.title
    assert first.score_percent == 100
    assert len(certificates.rows) == 1

    verified = await service.verify_certificate(first.reference)
    assert verified.reference == first.reference
    assert verified.completed_lessons == 1
    assert verified.total_lessons == 1

    listed = await service.list_certificates(user)
    assert [certificate.reference for certificate in listed] == [first.reference]


@pytest.mark.asyncio
async def test_verify_unknown_reference_raises():
    service, _, _, _, _ = _service()

    with pytest.raises(CertificateNotFound):
        await service.verify_certificate("SKU-2026-NOPE")


@pytest.mark.asyncio
async def test_requires_active_enrolment():
    service, user, course, _, _ = _service()
    service._enrolments.enrolment.status = EnrolmentStatus.WITHDRAWN

    with pytest.raises(NotEnrolledError):
        await service.get_final_assessment(user, course.id)


@pytest.mark.asyncio
async def test_missing_approved_final_assessment_blocks_access():
    service, user, course, _, _ = _service(
        assessment=_assessment(course_id := uuid.uuid4())
    )
    service._courses.course.curriculum_id = course_id
    service._assessments.assessments = []

    with pytest.raises(AssessmentNotAvailableError):
        await service.get_final_assessment(user, course.id)
