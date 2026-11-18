"""Unit tests for the rate-limit client-address resolution."""

from __future__ import annotations

from app.services.auth.rate_limit import client_ip
from starlette.requests import Request


def _request(*, client=("203.0.113.9", 1234), forwarded: str | None = None) -> Request:
    headers = []
    if forwarded is not None:
        headers.append((b"x-forwarded-for", forwarded.encode()))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": headers,
            "client": client,
        }
    )


def test_spoofed_forwarded_header_is_ignored_by_default() -> None:
    request = _request(forwarded="198.51.100.7")

    assert client_ip(request) == "203.0.113.9"


def test_forwarded_header_is_used_only_when_proxy_trust_is_enabled() -> None:
    request = _request(forwarded="198.51.100.7, 203.0.113.9")

    assert (
        client_ip(request, trust_proxy_headers=True) == "203.0.113.9"
    )


def test_direct_peer_is_used_when_proxy_trust_is_enabled_but_header_missing() -> None:
    request = _request(forwarded=None)

    assert client_ip(request, trust_proxy_headers=True) == "203.0.113.9"


def test_unknown_is_returned_without_peer_or_header() -> None:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [],
            "client": None,
        }
    )

    assert client_ip(request) == "unknown"
