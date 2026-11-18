"""Pydantic schemas for the learner portal surface."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.models.course import CourseStatus
from app.models.lecturer_activity import LecturerActivityType
from app.models.lesson import LessonStatus
from app.models.lesson_content_block import BlockReviewStatus, LessonBlockType
from app.models.practical_submission import SubmissionStatus
from app.models.user import UserRole
from pydantic import BaseModel, ConfigDict, Field


class LearnerProfileRead(BaseModel):
    """
    The signed-in learner's own profile.

    This is always the caller's own record — the learner surface never
    exposes another account's data.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class LearnerCourseRead(BaseModel):
    """
    A published course a learner can open in Moodle.

    The Moodle URL is the delivery surface for the course content; the
    learner's progress, attempts and certificates stay in this
    application.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    fullname: str
    shortname: str
    moodle_course_id: int | None
    moodle_url: str | None
    status: CourseStatus
    sections_published: int
    resources_published: int
    last_sync_at: datetime | None


class LearnerCourseListResponse(BaseModel):
    """Published courses available to the signed-in learner."""

    courses: list[LearnerCourseRead]


class EnrolRequest(BaseModel):
    """Request body for self-enrolment (optional)."""

    course_id: uuid.UUID | None = None


class EnrolResponse(BaseModel):
    """Result of an enrol/withdraw action."""

    enrolled: bool
    enrolment_id: uuid.UUID | None = None


class LearnerMilestoneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    enrolment_id: uuid.UUID
    lesson_id: uuid.UUID
    completed_at: datetime


class MilestoneListResponse(BaseModel):
    milestones: list[LearnerMilestoneRead]


class LessonCompletionRequest(BaseModel):
    """Optional body for marking a lesson complete."""

    completed: bool = True


class LessonCompletionResponse(BaseModel):
    completed: bool
    milestone_id: uuid.UUID | None = None


class PracticalSubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    enrolment_id: uuid.UUID
    block_id: uuid.UUID
    lesson_id: uuid.UUID
    content: str
    status: SubmissionStatus
    grade: int | None = None
    feedback: str | None = None
    submitted_at: datetime
    graded_at: datetime | None = None
    graded_by_id: uuid.UUID | None = None


class PracticalSubmissionRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20000)


class PracticalSubmissionResponse(BaseModel):
    submission: PracticalSubmissionRead


class GradeSubmissionRequest(BaseModel):
    grade: int | None = Field(default=None, ge=0, le=100)
    feedback: str | None = Field(default=None, max_length=5000)


class LecturerActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    actor_user_id: uuid.UUID | None = None
    subject_user_id: uuid.UUID | None = None
    event_type: LecturerActivityType
    summary: str
    details: dict
    created_at: datetime


class LessonBlockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lesson_id: uuid.UUID
    block_type: LessonBlockType
    order_index: int
    title: str | None = None
    payload: dict
    review_status: BlockReviewStatus
    submission: PracticalSubmissionRead | None = None


class LessonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    curriculum_id: uuid.UUID
    curriculum_unit_id: uuid.UUID
    week_number: int
    order_index: int
    title: str
    description: str
    learning_objectives: list[str]
    estimated_workload_minutes: int
    status: LessonStatus
    blocks: list[LessonBlockRead] = []
    completed: bool = False


class ProgressSummary(BaseModel):
    total_lessons: int
    completed_lessons: int
    percentage: int


class CourseDetailRead(BaseModel):
    course: LearnerCourseRead
    lessons: list[LessonRead]
    milestones: list[LearnerMilestoneRead]
    progress: ProgressSummary
    enrolled: bool = True
