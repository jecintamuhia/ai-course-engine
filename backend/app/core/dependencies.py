"""FastAPI dependency providers."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.db.repositories.users import UserRepository
from app.models.user import User, UserRole
from app.services.ai.base import LLMProvider
from app.services.moodle.client import MoodleClient
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.services.moodle.content import MoodleCourseContentService

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_app_settings() -> Settings:
    """Return application configuration."""
    return get_settings()


async def get_database_session(
    request: Request,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a request-scoped database session.

    The session factory is created during application startup and attached
    to application state.
    """
    session_factory = request.app.state.session_factory

    async with session_factory() as session:
        yield session


def get_redis_client(request: Request) -> Redis:
    """
    Provide the shared Redis client.

    The client is created during application startup and attached to
    application state; it is not request-scoped (a single connection
    pool is reused across requests).
    """
    return request.app.state.redis_client


def get_llm_provider(request: Request) -> LLMProvider:
    """
    Provide the shared LLM provider.

    Created once during application startup and attached to application
    state, matching the redis_client pattern.
    """
    return request.app.state.llm_provider


def get_moodle_client(request: Request) -> MoodleClient:
    """
    Provide the shared Moodle client.

    May be None on application state when Moodle is not configured; API
    routes must translate that into a 5xx configuration error.
    """
    client = request.app.state.moodle_client
    if client is None:
        from app.core.exceptions import ConfigurationError

        raise ConfigurationError(
            "Moodle integration is not configured. Set MOODLE_URL and "
            "MOODLE_TOKEN in the environment."
        )
    return client


def get_moodle_content_service(
    session: AsyncSession = Depends(get_database_session),
    client: MoodleClient = Depends(get_moodle_client),
) -> MoodleCourseContentService:
    """
    Provide a request-scoped Moodle course-content service.

    Resolves internal course/lesson identifiers to the matching published
    Moodle records and retrieves curriculum structure and lesson content
    through read-only Moodle web service calls only.
    """
    from app.db.repositories.courses import CourseRepository
    from app.db.repositories.lessons import LessonRepository
    from app.services.moodle.content import MoodleCourseContentService

    return MoodleCourseContentService(
        client, CourseRepository(session), LessonRepository(session)
    )


async def get_current_user(
    token: str = Depends(_oauth2_scheme),
    session: AsyncSession = Depends(get_database_session),
) -> User:
    """
    Resolve the ``Authorization: Bearer <jwt>`` header to a database user.

    Raises a 401 when the token is missing, invalid, expired, or refers to
    a user that no longer exists or has been deactivated.
    """
    from app.core.security import decode_access_token

    payload = decode_access_token(token)

    subject = payload.get("sub")
    if not subject:
        raise AuthenticationError("Access token is missing a subject claim.")

    try:
        user_id = uuid.UUID(str(subject))
    except (ValueError, TypeError):
        raise AuthenticationError("Access token subject claim is invalid.") from None

    user = await UserRepository(session).get_by_id(user_id)

    if user is None or not user.is_active:
        raise AuthenticationError("The account is inactive or no longer exists.")

    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Authorize only administrators for an endpoint."""
    if user.role != UserRole.ADMIN:
        raise AuthorizationError("Administrator role is required.")

    return user


def require_staff(user: User = Depends(get_current_user)) -> User:
    """
    Require an authoring role (administrator or lecturer).

    Learner accounts must never reach workspace endpoints.
    """
    from app.services.auth.routing import is_staff

    if not is_staff(user.role):
        raise AuthorizationError(
            "This account does not have access to the authoring workspace."
        )

    return user


def require_learner(user: User = Depends(get_current_user)) -> User:
    """
    Authorize the learner portal surface.

    Learner accounts are the intended audience, and every response on
    this surface is scoped to the caller's own records. Authoring roles
    are admitted too, so a lecturer can preview exactly what a learner
    sees; because the data is self-scoped that exposes nothing of
    anyone else's. Any role that is neither a learner nor authoring
    staff is rejected.
    """
    from app.services.auth.routing import is_learner, is_staff

    if not (is_learner(user.role) or is_staff(user.role)):
        raise AuthorizationError(
            "This account does not have access to the learner portal."
        )

    return user
