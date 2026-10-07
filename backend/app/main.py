import time
from contextlib import asynccontextmanager
from pathlib import Path

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.logging import (
    configure_logging,
    get_logger,
    set_request_id,
)
from app.core.redis import create_redis_client
from app.core.security import generate_request_id
from app.db.database import create_database_engine
from app.db.session import create_session_factory
from app.services.ai.factory import create_llm_provider
from app.services.moodle.client import create_moodle_client
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """
    Manage application-wide resources.

    Database and Redis resources are initialized before serving requests
    and disposed during graceful shutdown.
    """
    settings: Settings = application.state.settings

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    redis_client = create_redis_client(settings)
    llm_provider = create_llm_provider(settings)
    moodle_client = create_moodle_client(settings)

    application.state.engine = engine
    application.state.session_factory = session_factory
    application.state.redis_client = redis_client
    application.state.llm_provider = llm_provider
    application.state.moodle_client = moodle_client

    logger.info(
        "Application startup environment=%s version=%s",
        settings.environment,
        settings.app_version,
    )

    try:
        yield
    finally:
        logger.info("Application shutdown")

        await redis_client.aclose()

        if moodle_client is not None:
            await moodle_client.aclose()

        await engine.dispose()


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    configure_logging(settings)

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Production backend for AI-powered educational content "
            "ingestion and curriculum planning."
        ),
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url=(
            f"{settings.api_v1_prefix}/openapi.json"
            if not settings.is_production
            else None
        ),
        lifespan=lifespan,
    )

    application.state.settings = settings

    @application.middleware("http")
    async def request_context_middleware(
        request: Request,
        call_next,
    ):
        """Attach correlation ID and request timing to every request."""
        request_id = request.headers.get(
            "X-Request-ID",
            generate_request_id(),
        )

        set_request_id(request_id)

        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled request exception method=%s path=%s",
                request.method,
                request.url.path,
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000

        response.headers["X-Request-ID"] = request_id

        logger.info(
            "HTTP request completed method=%s path=%s status=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        return response

    @application.exception_handler(AppError)
    async def app_error_handler(
        request: Request,
        exc: AppError,
    ) -> JSONResponse:
        """Convert known application exceptions into safe API responses."""
        logger.warning(
            "Application error code=%s path=%s message=%s",
            exc.error_code,
            request.url.path,
            exc.message,
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                },
                "request_id": request.headers.get(
                    "X-Request-ID",
                    "-",
                ),
            },
        )

    application.include_router(
        api_router,
        prefix=settings.api_v1_prefix,
    )

    frontend_dir = Path(settings.frontend_dir)
    dist_dir = frontend_dir / "dist"
    serve_dir = dist_dir if dist_dir.is_dir() else frontend_dir
    if serve_dir.is_dir():
        application.mount(
            "/",
            SpaStaticFiles(directory=str(serve_dir), html=True),
            name="frontend",
        )
        logger.info("Serving frontend from %s", serve_dir)

    return application


class SpaStaticFiles(StaticFiles):
    """StaticFiles that falls back to index.html (hash-routed SPA)."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except Exception:
            index_path = Path(self.directory) / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            raise


app = create_application()
