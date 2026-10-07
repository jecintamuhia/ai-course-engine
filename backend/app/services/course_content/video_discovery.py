"""YouTube video discovery for lessons.

Videos are discovered through the YouTube Data API v3 ``search`` REST
endpoint — never fabricated by an LLM. Without a configured
``YOUTUBE_API_KEY`` the discovery is disabled and the orchestrator records
a skip, so no lesson claims videos it does not have.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from app.schemas.course_content import VideoPayload

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


@dataclass
class VideoDiscoveryResult:
    """Outcome of a video discovery run."""

    videos: list[VideoPayload] = field(default_factory=list)
    disabled: bool = False
    error: str | None = None


async def discover_videos(
    *,
    query: str,
    api_key: str,
    max_results: int = 3,
    timeout_seconds: float = 8.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> VideoDiscoveryResult:
    """
    Search YouTube for videos relevant to ``query``.

    Returns at most ``max_results`` validated VideoPayload records. Any
    transport/API failure is surfaced as ``error`` so the orchestrator can
    record it instead of silently inventing a video.

    ``transport`` is an optional ``httpx`` transport (e.g. MockTransport
    in tests); when omitted the default network transport is used.
    """
    if not api_key:
        return VideoDiscoveryResult(
            disabled=True,
            error="YOUTUBE_API_KEY is not configured; video discovery is disabled.",
        )

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max(max_results, 1),
        "key": api_key,
    }

    async with httpx.AsyncClient(
        timeout=timeout_seconds,
        transport=transport,
        headers={"User-Agent": "ai-course-engine-video-discovery/0.1"},
    ) as client:
        try:
            response = await client.get(YOUTUBE_SEARCH_URL, params=params)
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            return VideoDiscoveryResult(
                error=(f"YouTube search unreachable ({type(exc).__name__})")
            )

    if response.status_code != 200:
        return VideoDiscoveryResult(
            error=f"YouTube Data API returned HTTP {response.status_code}."
        )

    try:
        body = response.json()
    except ValueError:
        return VideoDiscoveryResult(error="YouTube Data API returned invalid JSON.")

    videos: list[VideoPayload] = []
    for item in body.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        if not video_id:
            continue
        videos.append(
            VideoPayload(
                title=snippet.get("title") or "Untitled video",
                video_id=video_id,
                url=f"https://www.youtube.com/watch?v={video_id}",
                channel=snippet.get("channelTitle"),
                description=snippet.get("description") or "",
                reason="Selected automatically from YouTube search for this lesson.",
                source_chunk_markers=[],
            )
        )

    return VideoDiscoveryResult(videos=videos[:max_results])
