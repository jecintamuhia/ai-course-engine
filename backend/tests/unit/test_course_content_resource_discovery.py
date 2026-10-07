"""Unit tests for external resource candidate URL validation."""

from __future__ import annotations

import httpx
from app.schemas.ai_content import GeneratedResourceCandidate
from app.services.course_content.resource_discovery import (
    validate_resource_candidates,
)


def _candidate(url: str, title: str = "Reference") -> GeneratedResourceCandidate:
    return GeneratedResourceCandidate(
        kind="article",
        title=title,
        url=url,
        description="A description.",
        why_recommended="It is helpful.",
    )


def _transport(*handlers):
    return httpx.MockTransport(handlers[0])


async def test_non_http_url_dropped_without_network() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text="ok"))

    validated, dropped = await validate_resource_candidates(
        [_candidate("javascript:alert(1)")], transport=transport
    )

    assert validated == []
    assert any("not an http(s) URL" in reason for reason in dropped)


async def test_valid_http_url_is_kept_and_timestamped() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text="ok"))

    validated, dropped = await validate_resource_candidates(
        [_candidate("https://example.com/article")], transport=transport
    )

    assert len(validated) == 1
    assert validated[0].url == "https://example.com/article"
    assert validated[0].validated_at is not None
    assert dropped == []


async def test_http_error_status_drops_candidate() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(404, text="missing"))

    validated, dropped = await validate_resource_candidates(
        [_candidate("https://example.com/missing")], transport=transport
    )

    assert validated == []
    assert any("HTTP 404" in reason for reason in dropped)


async def test_transport_error_drops_candidate() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    validated, dropped = await validate_resource_candidates(
        [_candidate("https://example.com/unreachable")],
        transport=httpx.MockTransport(boom),
    )

    assert validated == []
    assert any("unreachable" in reason for reason in dropped)


async def test_redirected_url_is_followed() -> None:
    def redirect(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/article":
            return httpx.Response(200, text="ok")
        return httpx.Response(302, headers={"location": "/article"}, text="")

    validated, dropped = await validate_resource_candidates(
        [_candidate("https://example.com/start")],
        transport=httpx.MockTransport(redirect),
    )

    assert len(validated) == 1
    assert validated[0].url == "https://example.com/start"
    assert dropped == []


async def test_empty_candidates_returns_empty_without_http() -> None:
    validated, dropped = await validate_resource_candidates([])
    assert validated == []
    assert dropped == []
