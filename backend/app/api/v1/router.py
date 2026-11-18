"""Version 1 API router."""

from app.api.v1.assessments import curriculum_assessment_router
from app.api.v1.assessments import router as assessments_router
from app.api.v1.auth import router as auth_router
from app.api.v1.certificates import router as certificates_router
from app.api.v1.course_content import router as course_content_router
from app.api.v1.courses import router as courses_router
from app.api.v1.curriculum import router as curriculum_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.ingestion import router as ingestion_router
from app.api.v1.learner import router as learner_router
from app.api.v1.lecturer import router as lecturer_router
from app.api.v1.moodle import router as moodle_router
from app.api.v1.overview import router as overview_router
from app.api.v1.topics import router as topics_router
from app.api.v1.topics import topic_router
from app.core.dependencies import require_staff
from fastapi import APIRouter, Depends

api_router = APIRouter()

for _router in (health_router, auth_router, certificates_router):
    api_router.include_router(_router)

# The learner portal is not staff-gated: each of its endpoints authorizes
# the caller itself (see ``require_learner``) and returns only that
# account's own records.
api_router.include_router(learner_router)

for _router in (
    documents_router,
    overview_router,
    ingestion_router,
    topics_router,
    topic_router,
    curriculum_router,
    curriculum_assessment_router,
    courses_router,
    moodle_router,
    assessments_router,
    course_content_router,
    lecturer_router,
):
    api_router.include_router(
        _router,
        dependencies=[Depends(require_staff)],
    )
