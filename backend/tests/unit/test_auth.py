"""Unit tests for password hashing, JWT issuance, and the AuthService."""

from __future__ import annotations

import uuid
from datetime import UTC
from unittest.mock import AsyncMock

import pytest
from app.core.config import Settings, get_settings
from app.core.exceptions import (
    AuthenticationError,
    EmailAlreadyRegisteredError,
    RegistrationDisabledError,
    RegistrationDomainNotAllowedError,
)
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.user import UserRole
from app.services.auth.service import AuthService, unusable_password_hash
from pydantic import SecretStr
from tests.helpers import make_test_user


def test_hash_password_argon2_and_verify_roundtrip() -> None:
    hashed = hash_password("correct horse battery staple")

    assert hashed.startswith("$argon2id$")
    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("right-password")

    assert verify_password("wrong-password", hashed) is False


def test_hash_password_rejects_empty() -> None:
    with pytest.raises(ValueError):
        hash_password("")


def test_verify_password_returns_false_on_invalid_hash_inputs() -> None:
    assert verify_password("", "anything") is False
    assert verify_password("pw", "not-an-argon2-hash") is False


def test_access_token_round_trips_payload() -> None:
    token = create_access_token(str(uuid.uuid4()), "admin")

    payload = decode_access_token(token)

    assert payload["sub"]
    assert payload["role"] == "admin"
    assert payload["iat"] and payload["exp"] > payload["iat"]


def test_access_token_rejects_garbage_decoding() -> None:
    with pytest.raises(AuthenticationError):
        decode_access_token("not.a.jwt")


def test_access_token_rejects_tampered_token() -> None:
    token = create_access_token(str(uuid.uuid4()), "lecturer")

    with pytest.raises(AuthenticationError):
        decode_access_token(token[:-2] + "xx")


def test_access_token_rejects_expired_token() -> None:
    from datetime import datetime, timedelta

    import jwt as _jwt

    settings = get_settings()
    user_id = uuid.uuid4()

    expired = _jwt.encode(
        {
            "sub": str(user_id),
            "role": "admin",
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        settings.secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(AuthenticationError):
        decode_access_token(expired)


@pytest.mark.anyio
async def test_authenticate_user_success() -> None:
    repository = AsyncMock()
    hashed = hash_password("secret-password")
    user = make_test_user(role=UserRole.ADMIN)
    repository.get_by_email = AsyncMock(return_value=user)
    user.password_hash = hashed

    result = await AuthService(repository).authenticate_user(
        "Admin@Example.com ", "secret-password"
    )

    assert result is user
    repository.get_by_email.assert_awaited_once_with("admin@example.com")


@pytest.mark.anyio
async def test_authenticate_user_fails_when_password_wrong() -> None:
    repository = AsyncMock()
    user = make_test_user()
    user.password_hash = hash_password("right")
    repository.get_by_email = AsyncMock(return_value=user)

    result = await AuthService(repository).authenticate_user(
        "admin@example.com", "wrong"
    )

    assert result is None


@pytest.mark.anyio
async def test_authenticate_user_fails_when_inactive() -> None:
    repository = AsyncMock()
    user = make_test_user()
    user.password_hash = hash_password("secret-password")
    user.is_active = False
    repository.get_by_email = AsyncMock(return_value=user)

    result = await AuthService(repository).authenticate_user(
        "admin@example.com", "secret-password"
    )

    assert result is None


@pytest.mark.anyio
async def test_authenticate_user_fails_when_missing() -> None:
    repository = AsyncMock()
    repository.get_by_email = AsyncMock(return_value=None)

    result = await AuthService(repository).authenticate_user(
        "nobody@example.com", "whatever"
    )

    assert result is None


@pytest.mark.anyio
async def test_create_user_normalizes_email_and_hashes_password() -> None:
    repository = AsyncMock()

    user = await AuthService(repository).create_user(
        email="  Lecturer@Example.com ",
        password="lecture-password-123",
        full_name="  Course Lecturer ",
        role=UserRole.LECTURER,
    )

    assert user.email == "lecturer@example.com"
    assert user.full_name == "Course Lecturer"
    assert user.role == UserRole.LECTURER
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password("lecture-password-123", user.password_hash)
    repository.add.assert_awaited_once_with(user)
    repository.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_issue_token_payload_returns_signed_token() -> None:
    repository = AsyncMock()
    user = make_test_user(role=UserRole.ADMIN)
    user.id = uuid.uuid4()

    payload = AuthService(repository).issue_token_payload(user)

    assert payload["token_type"] == "bearer"
    assert payload["user"] is user
    decoded = decode_access_token(payload["access_token"])
    assert decoded["sub"] == str(user.id)
    assert decoded["role"] == "admin"


# ---------------------------------------------------------------------------
# Self-registration
# ---------------------------------------------------------------------------


def _registration_settings(**overrides) -> Settings:
    defaults = {
        "secret_key": SecretStr("test-secret-key-for-registration"),
        "auth_registration_enabled": True,
        "auth_registration_allowed_domains": [],
    }
    return Settings(**{**defaults, **overrides})


@pytest.mark.anyio
async def test_register_user_always_creates_a_lecturer() -> None:
    repository = AsyncMock()
    repository.get_by_email.return_value = None

    user = await AuthService(repository, _registration_settings()).register_user(
        email="  New.Lecturer@Example.com ",
        password="a-strong-password",
        full_name="  New Lecturer ",
    )

    assert user.email == "new.lecturer@example.com"
    assert user.full_name == "New Lecturer"
    # Self-registration can never mint an administrator.
    assert user.role == UserRole.LECTURER
    assert user.is_active is True
    assert verify_password("a-strong-password", user.password_hash)


@pytest.mark.anyio
async def test_register_user_rejects_duplicate_email() -> None:
    repository = AsyncMock()
    repository.get_by_email.return_value = make_test_user()

    with pytest.raises(EmailAlreadyRegisteredError):
        await AuthService(repository, _registration_settings()).register_user(
            email="taken@example.com",
            password="a-strong-password",
            full_name="Taken",
        )

    repository.add.assert_not_awaited()


@pytest.mark.anyio
async def test_register_user_respects_disabled_registration() -> None:
    repository = AsyncMock()
    settings = _registration_settings(auth_registration_enabled=False)

    with pytest.raises(RegistrationDisabledError):
        await AuthService(repository, settings).register_user(
            email="someone@example.com",
            password="a-strong-password",
            full_name="Someone",
        )

    repository.add.assert_not_awaited()


@pytest.mark.anyio
async def test_register_user_enforces_domain_allowlist() -> None:
    repository = AsyncMock()
    repository.get_by_email.return_value = None
    settings = _registration_settings(auth_registration_allowed_domains=["gmail.com"])

    with pytest.raises(RegistrationDomainNotAllowedError):
        await AuthService(repository, settings).register_user(
            email="student@university.edu",
            password="a-strong-password",
            full_name="Student",
        )

    repository.add.assert_not_awaited()

    allowed = await AuthService(repository, settings).register_user(
        email="student@gmail.com",
        password="a-strong-password",
        full_name="Student",
    )
    assert allowed.role == UserRole.LECTURER


# ---------------------------------------------------------------------------
# External identity provider sign-in
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_external_signin_creates_a_lecturer_on_first_use() -> None:
    repository = AsyncMock()
    repository.get_by_email.return_value = None

    user = await AuthService(repository).get_or_create_external_user(
        email="Lecturer@Gmail.com",
        full_name="Google Lecturer",
    )

    assert user.email == "lecturer@gmail.com"
    assert user.role == UserRole.LECTURER
    repository.add.assert_awaited_once()


@pytest.mark.anyio
async def test_external_signin_links_an_existing_account() -> None:
    existing = make_test_user(role=UserRole.ADMIN, email="admin@gmail.com")
    repository = AsyncMock()
    repository.get_by_email.return_value = existing

    user = await AuthService(repository).get_or_create_external_user(
        email="admin@gmail.com",
        full_name="Admin",
    )

    # Links the existing account rather than duplicating, and does not
    # demote an existing admin.
    assert user is existing
    assert user.role == UserRole.ADMIN
    repository.add.assert_not_awaited()


@pytest.mark.anyio
async def test_external_signin_rejects_an_inactive_account() -> None:
    inactive = make_test_user()
    inactive.is_active = False
    repository = AsyncMock()
    repository.get_by_email.return_value = inactive

    with pytest.raises(AuthenticationError):
        await AuthService(repository).get_or_create_external_user(
            email="inactive@gmail.com",
            full_name="Inactive",
        )


def test_external_account_password_is_unusable() -> None:
    stored = unusable_password_hash()

    assert stored.startswith("$argon2id$")
    # No caller-supplied password can ever match the discarded secret.
    assert verify_password("anything", stored) is False
    assert verify_password("", stored) is False
