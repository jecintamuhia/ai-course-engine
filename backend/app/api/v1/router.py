"""Version 1 API router."""

from app.api.v1.courses import router as courses_router
from app.api.v1.curriculum import router as curriculum_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.ingestion import router as ingestion_router
from app.api.v1.moodle import router as moodle_router
from app.api.v1.overview import router as overview_router
from app.api.v1.topics import router as topics_router
from app.api.v1.topics import topic_router
from fastapi import APIRouter

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(documents_router)
api_router.include_router(overview_router)
api_router.include_router(ingestion_router)
api_router.include_router(topics_router)
api_router.include_router(topic_router)
api_router.include_router(curriculum_router)
api_router.include_router(courses_router)
api_router.include_router(moodle_router)
