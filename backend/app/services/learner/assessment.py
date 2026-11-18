"""Learner assessment and certificate service.

Certification rules (client-approved defaults, recorded in the audit):

* pass mark: 70% of auto-gradable final-assessment items;
* certificate: every approved lesson completed AND one passing attempt.

Objective items (multiple choice, true/false, and short answer with a
stored ``correct_answer``) are scored automatically. Open-ended items
(scenario, practical, coding, matching) are preserved in the feedback
but excluded from the score, because the platform has no lecturer
marking step for final assessments yet. A submission is rejected when
the assessment has no auto-gradable items, rather than pretending to
score it.
"""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import UTC, datetime

from app.core.exceptions import (
    AssessmentNotAvailableError,
    AssessmentSubmissionError,
    CertificateNotEligibleError,
    CertificateNotFound,
    CourseNotFound,
    NotEnrolledError,
)
from app.db.repositories.assessment_attempts import AssessmentAttemptRepository
from app.db.repositories.assessments import AssessmentRepository
from app.db.repositories.certificates import CertificateRepository
from app.db.repositories.courses import CourseRepository
from app.db.repositories.learner_enrolments import LearnerEnrolmentRepository
from app.db.repositories.learner_milestones import LearnerMilestoneRepository
from app.db.repositories.lessons import LessonRepository
from app.models.assessment import Assessment, AssessmentStatus, AssessmentType
from app.models.assessment_attempt import AssessmentAttempt
from app.models.certificate import Certificate
from app.models.learner_enrolment import LearnerEnrolment
from app.models.user import User
from app.schemas.assessment import AssessmentItem
from app.schemas.learner_assessment import (
    AssessmentAnswer,
    AssessmentAttemptRead,
    AssessmentAttemptSummary,
    AssessmentItemResult,
    AssessmentQuestionRead,
    AssessmentSubmitRequest,
    CertificateCourseRead,
    CertificateRead,
    CertificateSummary,
    FinalAssessmentRead,
)
from sqlalchemy.exc import IntegrityError

AUTO_GRADABLE_MC = {"multiple_choice", "true_false"}
AUTO_GRADABLE_TEXT = {"short_answer"}
OPEN_ENDED_KINDS = {"scenario", "practical", "coding", "matching"}


def _normalise(value: str | None) -> str:
    """Normalise free text for tolerant exact-answer comparison."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip().lower().rstrip(".;,")


class LearnerAssessmentService:
    """Take final assessments and issue verifiable certificates."""

    def __init__(
        self,
        course_repository: CourseRepository,
        enrolment_repository: LearnerEnrolmentRepository,
        milestone_repository: LearnerMilestoneRepository,
        lesson_repository: LessonRepository,
        assessment_repository: AssessmentRepository,
        attempt_repository: AssessmentAttemptRepository,
        certificate_repository: CertificateRepository,
        *,
        pass_percent: int = 70,
    ) -> None:
        self._courses = course_repository
        self._enrolments = enrolment_repository
        self._milestones = milestone_repository
        self._lessons = lesson_repository
        self._assessments = assessment_repository
        self._attempts = attempt_repository
        self._certificates = certificate_repository
        self._pass_percent = pass_percent

    async def get_final_assessment(
        self,
        user: User,
        course_id: uuid.UUID,
    ) -> FinalAssessmentRead:
        """Return the sanitised final assessment plus progress context."""
        assessment, enrolment = await self._require_final_assessment(user, course_id)
        items = self._validated_items(assessment)
        progress = await self._lesson_progress(course_id, enrolment.id)
        attempts = await self._attempts.list_for_enrolment(
            assessment.id, enrolment.id
        )
        best = await self._attempts.best_passing(assessment.id, enrolment.id)
        certificate = await self._certificates.get_for_learner_course(
            user.id, course_id
        )

        return FinalAssessmentRead(
            assessment_id=assessment.id,
            title=assessment.title,
            description=assessment.description,
            estimated_minutes=assessment.estimated_minutes,
            pass_percent=self._pass_percent,
            questions=[
                self._question_view(index, item) for index, item in items
            ],
            auto_gradable_count=self._auto_gradable_count(items),
            total_items=len(items),
            completed_lessons=progress["completed"],
            total_lessons=progress["total"],
            all_lessons_completed=progress["complete"],
            attempts=[
                AssessmentAttemptSummary(
                    id=attempt.id,
                    attempt_number=attempt.attempt_number,
                    score_percent=attempt.score_percent,
                    correct_count=attempt.correct_count,
                    auto_gradable_count=attempt.auto_gradable_count,
                    passed=attempt.passed,
                    submitted_at=attempt.submitted_at,
                )
                for attempt in attempts
            ],
            best_score_percent=best.score_percent if best else None,
            best_attempt_id=best.id if best else None,
            passed=best is not None,
            certificate=(
                CertificateSummary(
                    reference=certificate.reference,
                    issued_at=certificate.issued_at,
                    score_percent=certificate.score_percent,
                )
                if certificate
                else None
            ),
        )

    async def submit_attempt(
        self,
        user: User,
        course_id: uuid.UUID,
        payload: AssessmentSubmitRequest,
    ) -> AssessmentAttemptRead:
        """Grade and persist a complete answer sheet."""
        assessment, enrolment = await self._require_final_assessment(user, course_id)
        items = self._validated_items(assessment)
        if not items:
            raise AssessmentSubmissionError(
                "This assessment has no questions to grade."
            )

        answers = self._validate_answers(payload.answers, items)
        results, correct, gradable = self._score(items, answers)
        if gradable == 0:
            raise AssessmentSubmissionError(
                "This assessment has no automatically gradable questions yet."
            )

        score = round(correct * 100 / gradable)
        passed = score >= self._pass_percent
        attempt_number = (
            await self._attempts.count_for_enrolment(assessment.id, enrolment.id)
        ) + 1

        attempt = AssessmentAttempt(
            assessment_id=assessment.id,
            enrolment_id=enrolment.id,
            user_id=user.id,
            attempt_number=attempt_number,
            answers=[answer.model_dump(mode="json") for answer in payload.answers],
            results=[result.model_dump(mode="json") for result in results],
            correct_count=correct,
            auto_gradable_count=gradable,
            score_percent=score,
            passed=passed,
            submitted_at=datetime.now(UTC),
        )
        try:
            await self._attempts.add(attempt)
            await self._attempts.commit()
        except IntegrityError:
            await self._attempts.rollback()
            raise AssessmentSubmissionError(
                "This attempt was already saved by another request. "
                "Refresh the page to see your result."
            ) from None

        return self._attempt_read(attempt, assessment.id, results)

    async def list_attempts(
        self,
        user: User,
        course_id: uuid.UUID,
    ) -> list[AssessmentAttemptRead]:
        """Return the caller's attempt history for the course assessment."""
        assessment, enrolment = await self._require_final_assessment(user, course_id)
        attempts = await self._attempts.list_for_enrolment(
            assessment.id, enrolment.id
        )
        return [self._stored_attempt_read(attempt) for attempt in attempts]

    async def issue_certificate(
        self,
        user: User,
        course_id: uuid.UUID,
    ) -> CertificateCourseRead:
        """
        Issue (or return) the learner's course certificate.

        Issuance is idempotent: asking twice returns the same reference.
        A certificate is only issued after every approved lesson is
        completed and a passing attempt exists.
        """
        assessment, enrolment = await self._require_final_assessment(user, course_id)

        existing = await self._certificates.get_for_learner_course(
            user.id, course_id
        )
        if existing:
            return self._certificate_read(existing)

        progress = await self._lesson_progress(course_id, enrolment.id)
        if not progress["complete"]:
            missing = progress["total"] - progress["completed"]
            raise CertificateNotEligibleError(
                "Complete every lesson before requesting a certificate.",
                details={"remaining_lessons": max(missing, 0)},
            )

        best = await self._attempts.best_passing(assessment.id, enrolment.id)
        if best is None:
            raise CertificateNotEligibleError(
                f"Pass the final assessment with at least "
                f"{self._pass_percent}% before requesting a certificate.",
                details={"pass_percent": self._pass_percent},
            )

        course = await self._courses.get_by_id(course_id)
        if not course:
            raise CourseNotFound("Course not found.")

        certificate = Certificate(
            user_id=user.id,
            course_id=course_id,
            enrolment_id=enrolment.id,
            assessment_id=assessment.id,
            attempt_id=best.id,
            reference=self._new_reference(),
            learner_name=user.full_name,
            course_title=course.title,
            score_percent=best.score_percent,
            completed_lessons=progress["completed"],
            total_lessons=progress["total"],
            issued_at=datetime.now(UTC),
        )
        try:
            await self._certificates.add(certificate)
            await self._certificates.commit()
        except IntegrityError:
            await self._certificates.rollback()
            existing = await self._certificates.get_for_learner_course(
                user.id, course_id
            )
            if existing:
                return self._certificate_read(existing)
            raise

        return self._certificate_read(certificate)

    async def list_certificates(self, user: User) -> list[CertificateCourseRead]:
        """Return every certificate the learner has earned."""
        certificates = await self._certificates.list_for_user(user.id)
        return [self._certificate_read(certificate) for certificate in certificates]

    async def verify_certificate(self, reference: str) -> CertificateRead:
        """Publicly verify a certificate by its reference."""
        certificate = await self._certificates.get_by_reference(reference.strip())
        if not certificate:
            raise CertificateNotFound("No certificate matches that reference.")
        return CertificateRead.model_validate(certificate)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _require_final_assessment(
        self,
        user: User,
        course_id: uuid.UUID,
    ) -> tuple[Assessment, LearnerEnrolment]:
        course = await self._courses.get_by_id(course_id)
        if not course:
            raise CourseNotFound("Course not found.")
        enrolment = await self._enrolments.get_active(user.id, course_id)
        if not enrolment:
            raise NotEnrolledError("Enrol in this course to take its assessment.")

        assessments = await self._assessments.list_by_curriculum(course.curriculum_id)
        finals = [
            assessment
            for assessment in assessments
            if assessment.assessment_type == AssessmentType.FINAL
            and assessment.status == AssessmentStatus.APPROVED
        ]
        if not finals:
            raise AssessmentNotAvailableError(
                "This course does not have an approved final assessment yet."
            )
        return finals[-1], enrolment

    def _validated_items(
        self, assessment: Assessment
    ) -> list[tuple[int, AssessmentItem]]:
        """Validate stored items, preserving their original indexes."""
        items: list[tuple[int, AssessmentItem]] = []
        for index, raw in enumerate(assessment.items or []):
            try:
                items.append((index, AssessmentItem.model_validate(raw)))
            except (TypeError, ValueError):
                continue
        return items

    def _question_view(
        self, index: int, item: AssessmentItem
    ) -> AssessmentQuestionRead:
        return AssessmentQuestionRead(
            item_index=index,
            kind=item.kind,
            prompt=item.prompt,
            learning_objective=item.learning_objective,
            difficulty=item.difficulty,
            options=item.options,
            auto_gradable=self._is_auto_gradable(item),
        )

    def _is_auto_gradable(self, item: AssessmentItem) -> bool:
        if item.kind in AUTO_GRADABLE_MC:
            return bool(item.correct_option_id or item.correct_answer)
        if item.kind in AUTO_GRADABLE_TEXT:
            return bool(item.correct_answer)
        return False

    def _auto_gradable_count(self, items: list[tuple[int, AssessmentItem]]) -> int:
        return sum(1 for _, item in items if self._is_auto_gradable(item))

    def _validate_answers(
        self,
        answers: list[AssessmentAnswer],
        items: list[tuple[int, AssessmentItem]],
    ) -> dict[int, AssessmentAnswer]:
        by_index = {index: item for index, item in items}
        supplied: dict[int, AssessmentAnswer] = {}
        for answer in answers:
            if answer.item_index in supplied:
                raise AssessmentSubmissionError(
                    "Each question may be answered only once.",
                    details={"item_index": answer.item_index},
                )
            item = by_index.get(answer.item_index)
            if item is None:
                raise AssessmentSubmissionError(
                    "Answer refers to a question that is not on this assessment.",
                    details={"item_index": answer.item_index},
                )
            if answer.option_id is not None:
                option_ids = {option.id for option in item.options}
                if answer.option_id not in option_ids:
                    raise AssessmentSubmissionError(
                        "Answer refers to an option that is not offered.",
                        details={"item_index": answer.item_index},
                    )
            supplied[answer.item_index] = answer

        missing = [
            index
            for index, item in items
            if self._is_auto_gradable(item)
            and (
                supplied.get(index) is None
                or not (
                    supplied[index].option_id
                    or (supplied[index].answer or "").strip()
                )
            )
        ]
        if missing:
            raise AssessmentSubmissionError(
                "Answer every gradable question before submitting.",
                details={"missing_item_indexes": missing},
            )
        return supplied

    def _score(
        self,
        items: list[tuple[int, AssessmentItem]],
        answers: dict[int, AssessmentAnswer],
    ) -> tuple[list[AssessmentItemResult], int, int]:
        results: list[AssessmentItemResult] = []
        correct = 0
        gradable = 0

        for index, item in items:
            answer = answers.get(index)
            answered = bool(
                answer
                and (
                    answer.option_id
                    or (answer.answer and answer.answer.strip())
                )
            )
            auto = self._is_auto_gradable(item)
            is_correct: bool | None = None

            if auto:
                gradable += 1
                is_correct = self._grade_item(item, answer)
                if is_correct:
                    correct += 1

            results.append(
                AssessmentItemResult(
                    item_index=index,
                    kind=item.kind,
                    prompt=item.prompt,
                    answered=answered,
                    auto_graded=auto,
                    correct=is_correct,
                    submitted_option_id=answer.option_id if answer else None,
                    submitted_answer=answer.answer if answer else None,
                    correct_option_id=item.correct_option_id,
                    correct_answer=item.correct_answer,
                    explanation=item.explanation,
                )
            )

        return results, correct, gradable

    def _grade_item(
        self,
        item: AssessmentItem,
        answer: AssessmentAnswer | None,
    ) -> bool:
        if not answer:
            return False

        expected_option = item.correct_option_id
        expected_text = item.correct_answer

        if item.kind in AUTO_GRADABLE_MC:
            if answer.option_id:
                if expected_option:
                    return answer.option_id == expected_option
                if expected_text:
                    selected = next(
                        (
                            option.text
                            for option in item.options
                            if option.id == answer.option_id
                        ),
                        None,
                    )
                    return _normalise(selected) == _normalise(expected_text)
                return False
            if answer.answer and expected_text:
                return _normalise(answer.answer) == _normalise(expected_text)
            return False

        if item.kind in AUTO_GRADABLE_TEXT and expected_text:
            return _normalise(answer.answer) == _normalise(expected_text)

        return False

    async def _lesson_progress(
        self,
        course_id: uuid.UUID,
        enrolment_id: uuid.UUID,
    ) -> dict[str, int | bool]:
        course = await self._courses.get_by_id(course_id)
        if not course:
            raise CourseNotFound("Course not found.")
        lessons = await self._lessons.list_publishable_by_curriculum(
            course.curriculum_id
        )
        approved_ids = {lesson.id for lesson in lessons}
        milestones = await self._milestones.list_for_enrolment(enrolment_id)
        completed_ids = {
            milestone.lesson_id
            for milestone in milestones
            if milestone.lesson_id in approved_ids
        }
        total = len(approved_ids)
        completed = len(completed_ids)
        return {
            "total": total,
            "completed": completed,
            "complete": total > 0 and completed >= total,
        }

    def _attempt_read(
        self,
        attempt: AssessmentAttempt,
        assessment_id: uuid.UUID,
        results: list[AssessmentItemResult],
    ) -> AssessmentAttemptRead:
        return AssessmentAttemptRead(
            id=attempt.id,
            assessment_id=assessment_id,
            attempt_number=attempt.attempt_number,
            score_percent=attempt.score_percent,
            correct_count=attempt.correct_count,
            auto_gradable_count=attempt.auto_gradable_count,
            passed=attempt.passed,
            submitted_at=attempt.submitted_at,
            results=results,
        )

    def _stored_attempt_read(self, attempt: AssessmentAttempt) -> AssessmentAttemptRead:
        results = [
            AssessmentItemResult.model_validate(result)
            for result in (attempt.results or [])
            if isinstance(result, dict)
        ]
        return self._attempt_read(attempt, attempt.assessment_id, results)

    def _certificate_read(self, certificate: Certificate) -> CertificateCourseRead:
        return CertificateCourseRead(
            reference=certificate.reference,
            learner_name=certificate.learner_name,
            course_title=certificate.course_title,
            score_percent=certificate.score_percent,
            completed_lessons=certificate.completed_lessons,
            total_lessons=certificate.total_lessons,
            issued_at=certificate.issued_at,
            course_id=certificate.course_id,
        )

    def _new_reference(self) -> str:
        year = datetime.now(UTC).year
        return f"SKU-{year}-{secrets.token_hex(6).upper()}"
