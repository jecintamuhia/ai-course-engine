"""Authentication endpoints: login, registration, and Google sign-in."""

from __future__ import annotations

from urllib.parse import urlencode

from app.core.config import Settings
from app.core.dependencies import (
    get_app_settings,
    get_current_user,
    get_database_session,
    get_redis_client,
    require_admin,
)
from app.core.exceptions import AuthenticationError, InvalidCredentialsError
from app.core.logging import get_logger
from app.db.repositories.users import UserRepository
from app.models.user import User
from app.schemas.auth import (
    GoogleAuthStatus,
    GoogleExchangeRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserCreate,
    UserRead,
)
from app.services.auth.exchange_codes import issue_code, redeem_code
from app.services.auth.google import GoogleOAuthProvider, new_state
from app.services.auth.service import AuthService
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_STATE_KEY = "auth:oauth:state:"
_STATE_TTL_SECONDS = 600


def _redirect_with_error(frontend: str, message: str) -> RedirectResponse:
    """Bounce the browser back to the SPA with a human-readable failure.

    The message is surfaced as a query parameter rather than an HTTP error
    because the user arrived here via a Google redirect, so a JSON body
    would render as a blank page.
    """
    query = urlencode({"auth_error": message})
    return RedirectResponse(f"{frontend}?{query}", status_code=302)


def get_auth_service(
    session: AsyncSession = Depends(get_database_session),
    settings: Settings = Depends(get_app_settings),
) -> AuthService:
    """Construct a request-scoped authentication service."""
    return AuthService(UserRepository(session), settings)


def get_google_provider(
    settings: Settings = Depends(get_app_settings),
) -> GoogleOAuthProvider:
    """Construct a request-scoped Sign in with Google provider."""
    return GoogleOAuthProvider(settings)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    settings=Depends(get_app_settings),
    service=Depends(get_auth_service),
) -> TokenResponse:
    """
    Authenticate an administrator or lecturer.

    Returns a signed JWT access token. Credential failures receive a
    generic 401 so the endpoint never reveals which field was wrong.
    """
    user = await service.authenticate_user(
        payload.normalized_email(),
        payload.password,
    )

    if user is None:
        raise InvalidCredentialsError("Invalid email or password.")

    token_payload = service.issue_token_payload(user)

    return TokenResponse(
        access_token=token_payload["access_token"],
        token_type=token_payload["token_type"],
        user=UserRead.model_validate(token_payload["user"]),
    )


@router.get("/methods", response_model=GoogleAuthStatus)
async def get_auth_methods(
    settings: Settings = Depends(get_app_settings),
) -> GoogleAuthStatus:
    """
    Report which sign-in methods are available.

    Public so the sign-in page can hide options the server has not
    configured, instead of offering a button that would fail.
    """
    return GoogleAuthStatus(
        google_enabled=settings.google_oauth_enabled,
        registration_enabled=settings.auth_registration_enabled,
        allowed_domains=[
            domain.strip().lower().lstrip("@")
            for domain in settings.auth_registration_allowed_domains
            if domain.strip()
        ],
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    service=Depends(get_auth_service),
) -> TokenResponse:
    """
    Self-register a lecturer account and sign in immediately.

    Always creates a lecturer — there is no way to self-assign admin
    rights through this endpoint. A duplicate email receives a 409 rather
    than revealing whether that account exists beyond the obvious.
    """
    user = await service.register_user(
        email=payload.normalized_email(),
        password=payload.password,
        full_name=payload.full_name,
    )

    token_payload = service.issue_token_payload(user)

    return TokenResponse(
        access_token=token_payload["access_token"],
        token_type=token_payload["token_type"],
        user=UserRead.model_validate(token_payload["user"]),
    )


@router.get("/google/start")
async def google_start(
    settings: Settings = Depends(get_app_settings),
    redis_client: Redis = Depends(get_redis_client),
    provider: GoogleOAuthProvider = Depends(get_google_provider),
) -> RedirectResponse:
    """
    Begin Sign in with Google.

    Issues a single-use CSRF ``state`` value in Redis and redirects the
    browser to Google's consent screen.
    """
    state = new_state()
    await redis_client.set(f"{_STATE_KEY}{state}", "1", ex=_STATE_TTL_SECONDS)

    return RedirectResponse(
        provider.authorization_url(
            state=state,
            redirect_uri=settings.effective_google_redirect_uri,
        ),
        status_code=302,
    )


@router.get("/google/callback")
async def google_callback(
    code: str = "",
    state: str = "",
    error: str = "",
    settings: Settings = Depends(get_app_settings),
    redis_client: Redis = Depends(get_redis_client),
    provider: GoogleOAuthProvider = Depends(get_google_provider),
    service=Depends(get_auth_service),
) -> RedirectResponse:
    """
    Complete Sign in with Google, then hand the SPA a one-time code.

    The long-lived JWT is deliberately *not* placed in the redirect URL.
    Instead a short-lived single-use code is stored against the user id
    and the browser is sent to the frontend with only that code, which the
    SPA exchanges over POST (see ``/google/exchange``).
    """
    frontend = settings.google_oauth_frontend_redirect or "/login"

    if error:
        logger.info("Google sign-in declined error=%s", error)
        return _redirect_with_error(frontend, "Google sign-in was cancelled.")

    expected = await redis_client.getdel(f"{_STATE_KEY}{state}")
    if expected is None:
        return _redirect_with_error(frontend, "Sign-in expired. Please try again.")

    profile = await provider.exchange(
        code=code,
        state=state,
        redirect_uri=settings.effective_google_redirect_uri,
    )

    if not profile.email_verified:
        logger.warning(
            "Rejected sign-in for an unverified Google email domain=%s",
            profile.email.partition("@")[2],
        )
        return _redirect_with_error(
            frontend, "Your Google email address is not verified."
        )

    user = await service.get_or_create_external_user(
        email=profile.email,
        full_name=profile.full_name,
    )

    exchange_code = await issue_code(redis_client, user_id=user.id, settings=settings)

    logger.info("Google sign-in succeeded user_id=%s", user.id)

    return RedirectResponse(
        f"{frontend}?{urlencode({'code': exchange_code})}",
        status_code=302,
    )


@router.post("/google/exchange", response_model=TokenResponse)
async def google_exchange(
    payload: GoogleExchangeRequest,
    session: AsyncSession = Depends(get_database_session),
    redis_client: Redis = Depends(get_redis_client),
) -> TokenResponse:
    """
    Exchange a one-time sign-in code for an access token.

    The code is single-use: redeeming it deletes it, so a replayed link
    cannot mint a second session.
    """
    user_id = await redeem_code(redis_client, code=payload.code)

    user = await UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("The account is inactive or no longer exists.")

    token = AuthService(UserRepository(session)).issue_token_payload(user)

    return TokenResponse(
        access_token=token["access_token"],
        token_type=token["token_type"],
        user=UserRead.model_validate(user),
    )


@router.get("/me", response_model=UserRead)
async def get_me(
    user: User = Depends(get_current_user),
) -> UserRead:
    """Return the currently authenticated user's profile."""
    return UserRead.model_validate(user)


@router.post("/users", response_model=UserRead, status_code=201)
async def create_user(
    payload: UserCreate,
    _admin: User = Depends(require_admin),
    service=Depends(get_auth_service),
) -> UserRead:
    """Create a new user account (administrator-only)."""
    user = await service.create_user(
        email=payload.normalized_email(),
        password=payload.password,
        full_name=payload.full_name,
        role=payload.role,
    )

    return UserRead.model_validate(user)
