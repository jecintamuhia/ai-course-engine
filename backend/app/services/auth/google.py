"""Google OAuth 2.0 (OpenID Connect) sign-in provider.

Implements Google's authorization-code flow with PKCE-less server-side
exchange, which is the appropriate shape for a confidential web client:
the client secret never reaches the browser, and the authorization code
is exchanged server-side for the user's verified identity.

The provider is deliberately isolated behind :class:`OAuthProvider` so
business logic (user provisioning, token issuing) never depends on Google
specifically — adding another identity provider means implementing one
interface, not editing the auth service.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

import httpx
from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.logging import get_logger

logger = get_logger(__name__)

GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"

SCOPES = ("openid", "email", "profile")


@dataclass(frozen=True)
class OAuthProfile:
    """The verified identity Google asserts about a user."""

    email: str
    full_name: str
    email_verified: bool


class OAuthProvider(Protocol):
    """Minimal contract an external identity provider must satisfy."""

    @property
    def enabled(self) -> bool: ...

    def authorization_url(self, *, state: str, redirect_uri: str) -> str: ...

    async def exchange(
        self, *, code: str, state: str | None, redirect_uri: str
    ) -> OAuthProfile: ...


class GoogleOAuthProvider:
    """Sign-in with Google via the authorization-code flow."""

    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._http_client = http_client
        self._embedded_client = None if http_client is not None else httpx.AsyncClient()

    @property
    def _client(self) -> httpx.AsyncClient:
        return (
            self._http_client
            if self._http_client is not None
            else self._embedded_client  # type: ignore[return-value]
        )

    @property
    def enabled(self) -> bool:
        return self._settings.google_oauth_enabled

    def authorization_url(self, *, state: str, redirect_uri: str) -> str:
        """Build the Google consent-screen URL the browser is sent to."""
        if not self.enabled:
            raise AuthenticationError(
                "Sign in with Google is not configured on this server."
            )

        params = {
            "client_id": self._settings.google_oauth_client_id.get_secret_value(),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "state": state,
            # prompt=select_account keeps a lecturer who is already signed
            # into Google from silently landing on the wrong account.
            "prompt": "select_account",
        }
        return f"{GOOGLE_AUTHORIZATION_ENDPOINT}?{urlencode(params)}"

    async def exchange(
        self, *, code: str, state: str | None, redirect_uri: str
    ) -> OAuthProfile:
        """
        Exchange an authorization code for the user's identity.

        ``state`` is verified by the caller against the value it issued;
        it is accepted here only so the interface stays provider-neutral.
        """
        try:
            settings = self._settings
            token_response = await self._client.post(
                GOOGLE_TOKEN_ENDPOINT,
                data={
                    "code": code,
                    "client_id": settings.google_oauth_client_id.get_secret_value(),
                    "client_secret": (
                        settings.google_oauth_client_secret.get_secret_value()
                    ),
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                timeout=settings.google_oauth_timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise AuthenticationError(
                "Could not reach Google to complete sign-in."
            ) from exc

        if token_response.status_code != 200:
            logger.warning(
                "Google token exchange rejected status=%s body=%s",
                token_response.status_code,
                token_response.text[:500],
            )
            raise AuthenticationError("Google rejected the sign-in request.")

        try:
            id_token = token_response.json()["access_token"]
        except (ValueError, KeyError) as exc:
            raise AuthenticationError(
                "Google returned an unexpected token response."
            ) from exc

        try:
            userinfo = await self._client.get(
                GOOGLE_USERINFO_ENDPOINT,
                headers={"Authorization": f"Bearer {id_token}"},
                timeout=self._settings.google_oauth_timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise AuthenticationError("Could not read your Google profile.") from exc

        if userinfo.status_code != 200:
            raise AuthenticationError("Google did not return your profile.")

        try:
            claims = userinfo.json()
        except ValueError as exc:
            raise AuthenticationError(
                "Google returned an unexpected profile response."
            ) from exc

        email = str(claims.get("email") or "").strip().lower()
        if not email:
            raise AuthenticationError("Google did not provide an email address.")

        return OAuthProfile(
            email=email,
            full_name=str(claims.get("name") or email.split("@")[0]).strip(),
            email_verified=bool(claims.get("email_verified", False)),
        )

    async def aclose(self) -> None:
        """Close resources owned by this provider (not injected ones)."""
        if self._http_client is not None:
            return
        if self._embedded_client is not None:
            await self._embedded_client.aclose()
            self._embedded_client = None


def new_state() -> str:
    """Return an unguessable CSRF state value for one sign-in attempt."""
    return secrets.token_urlsafe(32)
