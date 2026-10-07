"""Unit tests for YouTube video discovery."""

from __future__ import annotations

import httpx
from app.schemas.course_content import VideoPayload
from app.services.course_content.video_discovery import discover_videos


async def test_discovery_disabled_without_api_key() -> None:
    result = await discover_videos(query="intro to ml", api_key="")

    assert result.disabled is True
    assert result.videos == []
    assert result.error is not None


async def test_successful_search_returns_videos() -> None:
    body = {
        "items": [
            {
                "id": {"videoId": "abc123"},
                "snippet": {
                    "title": "Machine Learning Intro",
                    "channelTitle": "AI Channel",
                    "description": "A short intro.",
                },
            }
        ]
    }
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body))

    result = await discover_videos(
        query="intro", api_key="key", max_results=1, transport=transport
    )

    assert result.disabled is False
    assert result.error is None
    assert len(result.videos) == 1
    video: VideoPayload = result.videos[0]
    assert video.video_id == "abc123"
    assert video.url == "https://www.youtube.com/watch?v=abc123"
    assert video.channel == "AI Channel"


async def test_api_error_status_records_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(403, text="forbidden")
    )

    result = await discover_videos(query="intro", api_key="key", transport=transport)

    assert result.videos == []
    assert "403" in (result.error or "")


async def test_max_results_caps_returned_videos() -> None:
    body = {
        "items": [
            {
                "id": {"videoId": f"vid{i}"},
                "snippet": {"title": f"Video {i}", "description": ""},
            }
            for i in range(5)
        ]
    }
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body))

    result = await discover_videos(
        query="intro", api_key="key", max_results=2, transport=transport
    )

    assert len(result.videos) == 2


async def test_non_json_body_records_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text="not json")
    )

    result = await discover_videos(query="intro", api_key="key", transport=transport)

    assert result.videos == []
    assert result.error is not None


async def test_search_url_uses_expected_endpoint_and_params() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"items": []})

    await discover_videos(
        query="intro",
        api_key="secretkey",
        max_results=2,
        transport=httpx.MockTransport(handler),
    )

    assert len(seen) == 1
    assert "/youtube/v3/search" in seen[0]
    assert "q=intro" in seen[0]
    assert "key=secretkey" in seen[0]
