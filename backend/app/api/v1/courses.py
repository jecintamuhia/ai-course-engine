"""Published course (Moodle) listing endpoints."""

from __future__ import annotations

import uuid

from app.core.dependencies import get_database_session
from app.core.exceptions import CourseNotFound
from app.db.repositories.courses import CourseRepository
from app.schemas.moodle import MoodleCourseListResponse, MoodleCourseRead
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/courses", tags=["moodle"])


@router.get("", response_model=MoodleCourseListResponse)
async def list_courses(
    session: AsyncSession = Depends(get_database_session),
) -> MoodleCourseListResponse:
    """List all course records published to Moodle, newest first."""
    repository = CourseRepository(session)
    courses = await repository.list_all()
    return MoodleCourseListResponse(
        courses=[MoodleCourseRead.model_validate(course) for course in courses]
    )


@router.get("/{course_id}", response_model=MoodleCourseRead)
async def get_course(
    course_id: uuid.UUID,
    session: AsyncSession = Depends(get_database_session),
) -> MoodleCourseRead:
    """Fetch a single published course record by ID."""
    repository = CourseRepository(session)
    course = await repository.get_by_id(course_id)

    if course is None:
        raise CourseNotFound(f"Course {course_id} was not found.")

    return MoodleCourseRead.model_validate(course)
