"""External resource discovery and URL validation.

An LLM can hallucinate URLs, so resource recommendations from the LLM are
treated as *candidates* and validated against the live web before they are
ever persisted. Only candidates whose URLs respond (HTTP/2xx or 3xx) are
kept; everything else is dropped and reported back to the orchestrator so
the lecturer sees what was rejected instead of being silently served a
fabricated reference.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from app.schemas.ai_content import GeneratedResourceCandidate
from app.schemas.course_content import ExternalResourcePayload


async def validate_resource_candidates(
    candidates: list[GeneratedResourceCandidate],
    *,
    timeout_seconds: float = 8.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[list[ExternalResourcePayload], list[str]]:
    """
    Validate proposed resource URLs against the web.

    Returns (validated, dropped_reasons). ``validated`` contains only
    candidates whose URL reachable and returned a success status; each is
    timestamped with ``validated_at``. ``dropped_reasons`` is one message
    per candidate that failed validation (or an empty list when all
    passed); the orchestrator records these so no fabricated reference
    reaches a learner and none is silently lost.

    ``transport`` is an optional ``httpx`` transport (e.g. MockTransport
    in tests); when omitted the default network transport is used.
    """
    validated: list[ExternalResourcePayload] = []
    dropped: list[str] = []

    for candidate in candidates:
        payload, reason = await _validate_one(
            candidate, timeout_seconds, transport=transport
        )
        if payload is not None:
            validated.append(payload)
        else:
            dropped.append(f"{candidate.title!r} ({candidate.url}): {reason}")

    return validated, dropped


async def _validate_one(
    candidate: GeneratedResourceCandidate,
    timeout_seconds: float,
    *,
    transport: httpx.AsyncBaseTransport | None,
) -> tuple[ExternalResourcePayload | None, str]:
    """Validate one candidate URL. Returns (payload, None) or (None, reason)."""
    url = candidate.url.strip()
    if not url.startswith(("http://", "https://")):
        return None, "not an http(s) URL"

    timeout = httpx.Timeout(timeout=timeout_seconds, connect=min(timeout_seconds, 5.0))
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        verify=True,
        transport=transport,
        headers={"User-Agent": "ai-course-engine-resource-check/0.1"},
    ) as client:
        try:
            response = await client.get(url)
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            return None, f"unreachable ({type(exc).__name__})"

    if response.status_code >= 400:
        return None, f"HTTP {response.status_code}"

    return (
        ExternalResourcePayload(
            kind=candidate.kind,
            title=candidate.title,
            url=url,
            description=candidate.description,
            why_recommended=candidate.why_recommended,
            source_chunk_markers=list(candidate.source_chunk_markers),
            validated_at=datetime.now(UTC),
        ),
        "",
    )
