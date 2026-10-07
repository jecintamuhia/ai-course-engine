"""Authentication service: login, token issuance, and user management."""

from __future__ import annotations

import secrets
import uuid

from app.core.config import Settings
from app.core.exceptions import (
    AuthenticationError,
    EmailAlreadyRegisteredError,
    RegistrationDisabledError,
    RegistrationDomainNotAllowedError,
)
from app.core.security import create_access_token, hash_password, verify_password
from app.db.repositories.users import UserRepository
from app.models.user import User, UserRole


def unusable_password_hash() -> str:
    """
    Return a hash of a random secret that is never disclosed.

    Used for accounts created through an external identity provider, so
    they have no usable password. The column is NOT NULL, and this keeps
    such an account from ever authenticating via the password route
    without a schema change. Setting a real password later simply
    overwrites it.
    """
    return hash_password(secrets.token_urlsafe(32))


class AuthService:
    """Coordinates authentication and token issuance for the application."""

    def __init__(
        self,
        user_repository: UserRepository,
        settings: Settings | None = None,
    ) -> None:
        self._user_repository = user_repository
        self._settings = settings

    async def authenticate_user(self, email: str, password: str) -> User | None:
        """
        Authenticate an email/password pair.

        Returns the user on success and ``None`` on any failure so that
        callers never leak which part of the credential was wrong. The
        email is normalized before the lookup, so casings and stray
        whitespace never affect the result.
        """
        user = await self._user_repository.get_by_email(email.strip().lower())
        if user is None or not user.is_active:
            return None

        if not verify_password(password, user.password_hash):
            return None

        return user

    def issue_token_payload(self, user: User) -> dict:
        """Build the login response payload for an authenticated user."""
        return {
            "access_token": create_access_token(str(user.id), user.role.value),
            "token_type": "bearer",
            "user": user,
        }

    async def create_user(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
        role: UserRole = UserRole.LECTURER,
    ) -> User:
        """Create a new user with a hashed password and persist it."""
        user = User(
            id=uuid.uuid4(),
            email=email.strip().lower(),
            password_hash=hash_password(password),
            full_name=full_name.strip(),
            role=role,
            is_active=True,
        )
        await self._user_repository.add(user)
        await self._user_repository.commit()
        return user

    # ------------------------------------------------------------------
    # Self-registration
    # ------------------------------------------------------------------

    async def register_user(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
    ) -> User:
        """
        Self-register a lecturer account.

        Deliberately takes no ``role``: public registration can never mint
        an administrator, so a signed-up account cannot reach the admin
        user-creation or Moodle-publishing endpoints. Role assignment
        stays an admin-only action.

        Honors ``AUTH_REGISTRATION_ENABLED`` and the optional domain
        allowlist.
        """
        settings = self._settings
        if settings is not None:
            if not settings.auth_registration_enabled:
                raise RegistrationDisabledError(
                    "Self-registration is disabled on this server. "
                    "Please sign in or use Sign in with Google."
                )

            allowed = [
                domain.strip().lower().lstrip("@")
                for domain in settings.auth_registration_allowed_domains
                if domain.strip()
            ]
            if allowed:
                domain = email.strip().lower().partition("@")[2]
                if domain not in allowed:
                    raise RegistrationDomainNotAllowedError(
                        "This email domain cannot be used to register. "
                        f"Allowed domains: {', '.join(allowed)}.",
                        details={"allowed_domains": allowed},
                    )

        normalized = email.strip().lower()
        if await self._user_repository.get_by_email(normalized) is not None:
            raise EmailAlreadyRegisteredError(
                "An account with this email already exists. Try signing in instead."
            )

        return await self.create_user(
            email=normalized,
            password=password,
            full_name=full_name,
            role=UserRole.LECTURER,
        )

    # ------------------------------------------------------------------
    # External identity providers
    # ------------------------------------------------------------------

    async def get_or_create_external_user(
        self,
        *,
        email: str,
        full_name: str,
    ) -> User:
        """
        Return the account for a verified external identity, creating a
        lecturer account on first sign-in.

        An existing account is linked by email rather than duplicated, so
        someone who registered with a password can later use Google on the
        same account. An existing admin keeps its admin role — this never
        demotes anyone, and never promotes.
        """
        normalized = email.strip().lower()
        existing = await self._user_repository.get_by_email(normalized)

        if existing is not None:
            if not existing.is_active:
                raise AuthenticationError(
                    "The account is inactive or no longer exists."
                )
            return existing

        return await self.create_user(
            email=normalized,
            password=secrets.token_urlsafe(32),
            full_name=full_name,
            role=UserRole.LECTURER,
        )
