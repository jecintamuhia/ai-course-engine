"""Pydantic schemas for authentication and user resources."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.models.user import UserRole
from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Credentials submitted to the login endpoint."""

    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)

    def normalized_email(self) -> str:
        """Return the email in its canonical, lower-case form."""
        return self.email.strip().lower()


class TokenResponse(BaseModel):
    """
    Access token returned after successful authentication.

    ``redirect_to`` is the server-decided post-login destination. For
    authoring roles it is a same-origin workspace path; for student and
    teacher accounts it is the learner portal, where their progress,
    assessments and certificates live. The SPA must honour this value
    rather than hard-coding ``/dashboard``.
    """

    access_token: str
    token_type: str = "bearer"
    user: UserRead
    redirect_to: str


class UserCreate(BaseModel):
    """
    Payload for creating a new user (administrator-only).

    This is the only way to create a lecturer, teacher or admin account.
    Self-registration always produces a learner.
    """

    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=320)
    password: str = Field(min_length=8, max_length=1024)
    full_name: str = Field(min_length=1, max_length=200)
    role: UserRole = UserRole.LECTURER

    def normalized_email(self) -> str:
        """Return the email in its canonical, lower-case form."""
        return self.email.strip().lower()


class UserRead(BaseModel):
    """Public representation of an application user (no secrets)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RegisterRequest(BaseModel):
    """
    Payload for public self-registration.

    Intentionally has no ``role`` field: self-registration can only ever
    create a learner. Lecturer, teacher and administrator accounts are
    provisioned by an administrator.
    """

    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=320)
    password: str = Field(min_length=8, max_length=1024)
    full_name: str = Field(min_length=1, max_length=200)

    def normalized_email(self) -> str:
        """Return the email in its canonical, lower-case form."""
        return self.email.strip().lower()


class GoogleExchangeRequest(BaseModel):
    """Single-use code minted by the Google callback, exchanged for a token."""

    code: str = Field(min_length=1, max_length=512)


class GoogleAuthStatus(BaseModel):
    """Which sign-in methods this deployment offers."""

    google_enabled: bool
    registration_enabled: bool
    allowed_domains: list[str] = Field(default_factory=list)
