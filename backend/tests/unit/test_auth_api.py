"""Route-level tests for the authentication endpoints and route gating."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import httpx
import pytest
from app.api.v1.auth import get_auth_service
from app.core.dependencies import get_database_session
from app.main import create_application
from app.models.user import UserRole
from httpx import ASGITransport, AsyncClient
from tests.helpers import install_auth_override, make_test_user

LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"
DOCUMENTS_URL = "/api/v1/documents"


class _FakeAuthService:
    def __init__(self) -> None:
        self.user = make_test_user()
        self.user.id = uuid.uuid4()

    async def authenticate_user(self, email: str, password: str):
        if email == "admin@example.com" and password == "correct":
            return self.user
        return None

    def issue_token_payload(self, user):
        from app.core.security import create_access_token

        return {
            "access_token": create_access_token(str(user.id), user.role.value),
            "token_type": "bearer",
            "user": user,
        }

    async def create_user(self, **kwargs):
        return self.user


async def test_login_returns_token_and_profile(client: httpx.AsyncClient) -> None:
    fake = _FakeAuthService()
    client.app.dependency_overrides[get_auth_service] = lambda: fake

    response = await client.post(
        LOGIN_URL,
        json={"email": "admin@example.com", "password": "correct"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["role"] == "admin"


async def test_login_rejects_wrong_credentials(
    client: httpx.AsyncClient,
) -> None:
    fake = _FakeAuthService()
    client.app.dependency_overrides[get_auth_service] = lambda: fake

    response = await client.post(
        LOGIN_URL,
        json={"email": "admin@example.com", "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_login_rejects_missing_fields(
    client: httpx.AsyncClient,
) -> None:
    fake = _FakeAuthService()
    client.app.dependency_overrides[get_auth_service] = lambda: fake

    response = await client.post(LOGIN_URL, json={"email": "admin@example.com"})

    assert response.status_code == 422


async def test_me_returns_authenticated_profile(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(ME_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "admin@test.local"
    assert body["role"] == "admin"


async def test_admin_can_create_user(client: httpx.AsyncClient) -> None:
    fake = _FakeAuthService()
    client.app.dependency_overrides[get_auth_service] = lambda: fake

    response = await client.post(
        "/api/v1/auth/users",
        json={
            "email": "lecturer@example.com",
            "password": "lecture-password-123",
            "full_name": "Course Lecturer",
            "role": "lecturer",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "admin@test.local"


async def test_lecturer_cannot_create_user(client: httpx.AsyncClient) -> None:
    install_auth_override(client.app, role=UserRole.LECTURER)

    response = await client.post(
        "/api/v1/auth/users",
        json={
            "email": "lecturer@example.com",
            "password": "lecture-password-123",
            "full_name": "Course Lecturer",
            "role": "lecturer",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "authorization_error"


async def test_protected_route_requires_token() -> None:
    application = create_application()

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as anon:
        response = await anon.get(DOCUMENTS_URL)

    assert response.status_code == 401
    assert response.headers.get("www-authenticate", "").startswith("Bearer")


async def test_protected_route_rejects_garbage_token() -> None:
    from app.core.dependencies import get_database_session

    application = create_application()
    application.dependency_overrides[get_database_session] = lambda: AsyncMock()

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as anon:
        response = await anon.get(
            DOCUMENTS_URL,
            headers={"Authorization": "Bearer not-a-real-token"},
        )

    assert response.status_code == 401


async def test_health_stays_public() -> None:
    application = create_application()

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as anon:
        response = await anon.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Self-registration
# ---------------------------------------------------------------------------

REGISTER_URL = "/api/v1/auth/register"
METHODS_URL = "/api/v1/auth/methods"


class _RecordingAuthService(_FakeAuthService):
    def __init__(self) -> None:
        super().__init__()
        self.register_calls: list[dict] = []

    async def register_user(self, *, email, password, full_name):
        self.register_calls.append(
            {"email": email, "password": password, "full_name": full_name}
        )
        self.user.email = email
        self.user.full_name = full_name
        self.user.role = UserRole.LECTURER
        return self.user


async def test_register_returns_token_and_a_lecturer(
    client: httpx.AsyncClient,
) -> None:
    fake = _RecordingAuthService()
    client.app.dependency_overrides[get_auth_service] = lambda: fake

    response = await client.post(
        REGISTER_URL,
        json={
            "email": "Lecturer@Gmail.com",
            "password": "a-strong-password",
            "full_name": "Course Lecturer",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["access_token"]
    assert body["user"]["role"] == "lecturer"
    # Email is normalized before it reaches the service.
    assert fake.register_calls[0]["email"] == "lecturer@gmail.com"


async def test_register_rejects_a_short_password(
    client: httpx.AsyncClient,
) -> None:
    client.app.dependency_overrides[get_database_session] = lambda: AsyncMock()

    response = await client.post(
        REGISTER_URL,
        json={
            "email": "someone@gmail.com",
            "password": "short",
            "full_name": "Someone",
        },
    )

    assert response.status_code == 422


async def test_register_rejects_a_malformed_email(
    client: httpx.AsyncClient,
) -> None:
    client.app.dependency_overrides[get_database_session] = lambda: AsyncMock()

    response = await client.post(
        REGISTER_URL,
        json={
            "email": "not-an-email",
            "password": "a-strong-password",
            "full_name": "Someone",
        },
    )

    assert response.status_code == 422


async def test_register_cannot_escalate_to_admin(
    client: httpx.AsyncClient,
) -> None:
    """A self-registering caller must not be able to request a role."""
    fake = _RecordingAuthService()
    client.app.dependency_overrides[get_auth_service] = lambda: fake

    response = await client.post(
        REGISTER_URL,
        json={
            "email": "sneaky@gmail.com",
            "password": "a-strong-password",
            "full_name": "Sneaky",
            "role": "admin",
        },
    )

    # role is not part of RegisterRequest, so it is ignored rather than
    # honoured, and the resulting account is a lecturer.
    assert response.status_code == 201
    assert response.json()["user"]["role"] == "lecturer"
    assert "role" not in fake.register_calls[0]


async def test_auth_methods_reports_availability() -> None:
    application = create_application()

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as anon:
        response = await anon.get(METHODS_URL)

    assert response.status_code == 200
    body = response.json()
    # No Google credentials configured in the test environment.
    assert body["google_enabled"] is False
    assert body["allowed_domains"] == []


# ---------------------------------------------------------------------------
# OAuth one-time exchange codes
# ---------------------------------------------------------------------------


class _FakeRedis:
    """Minimal async Redis stand-in with TTL-free get/set/getdel."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def set(self, key, value, ex=None):
        self.store[key] = value
        return True

    async def get(self, key):
        return self.store.get(key)

    async def getdel(self, key):
        return self.store.pop(key, None)


async def test_exchange_code_is_single_use() -> None:
    from app.core.config import Settings
    from app.core.exceptions import AuthenticationError
    from app.services.auth.exchange_codes import issue_code, redeem_code

    redis = _FakeRedis()
    settings = Settings()
    user_id = uuid.uuid4()

    code = await issue_code(redis, user_id=user_id, settings=settings)
    assert await redeem_code(redis, code=code) == user_id

    # Replaying the same code must not mint a second session.
    with pytest.raises(AuthenticationError):
        await redeem_code(redis, code=code)


async def test_exchange_code_rejects_an_unknown_code() -> None:
    from app.core.exceptions import AuthenticationError
    from app.services.auth.exchange_codes import redeem_code

    with pytest.raises(AuthenticationError):
        await redeem_code(_FakeRedis(), code="never-issued")


async def test_google_start_refuses_when_not_configured() -> None:
    application = create_application()
    application.dependency_overrides[get_database_session] = lambda: AsyncMock()
    application.state.redis_client = _FakeRedis()

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as anon:
        response = await anon.get(
            "/api/v1/auth/google/start",
            follow_redirects=False,
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_error"
