"""Unit tests for OpenRouterProvider, against a mocked httpx transport."""

from __future__ import annotations

import json

import httpx
import pytest
from app.core.exceptions import AIProviderError
from app.services.ai import openrouter_provider
from app.services.ai.openrouter_provider import OpenRouterProvider
from pydantic import BaseModel


class _SampleModel(BaseModel):
    title: str
    difficulty: int


def _completion(
    payload: object,
    *,
    finish_reason: str = "stop",
    usage: dict | None = None,
    provider: str | None = "Anthropic",
) -> dict:
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": json.dumps(payload)},
                "finish_reason": finish_reason,
            }
        ],
        "model": "openrouter/test",
        "provider": provider,
        "usage": usage
        or {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _text_completion(text: str) -> dict:
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "model": "openrouter/test",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _error_body(code: int, message: str, error_type: str | None = None) -> dict:
    body: dict = {"error": {"code": code, "message": message}}
    if error_type:
        body["error"]["metadata"] = {"error_type": error_type}
    return body


def _resp(
    *,
    status: int = 200,
    body: dict | None = None,
    headers: dict | None = None,
) -> httpx.Response:
    return httpx.Response(
        status,
        json=body if body is not None else {},
        headers=headers or {},
    )


class _QueuedClient:
    """Async context manager fake whose post() drains a pre-loaded queue."""

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.post_calls = 0
        self.last_kwargs: dict | None = None

    async def __aenter__(self) -> _QueuedClient:
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def post(self, *args, **kwargs) -> httpx.Response:
        self.post_calls += 1
        self.last_kwargs = kwargs
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def provider() -> OpenRouterProvider:
    return OpenRouterProvider(
        api_key="sk-or-test-key",
        model="openrouter/test",
        retry_base_delay_seconds=0.01,
        max_retry_delay_seconds=1.0,
    )


def _patch_client(monkeypatch, client: _QueuedClient) -> None:
    monkeypatch.setattr(
        openrouter_provider.httpx,
        "AsyncClient",
        lambda **kwargs: client,
    )


def _disable_sleep(monkeypatch) -> None:
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(openrouter_provider.asyncio, "sleep", _noop)


def test_api_key_sent_only_in_auth_header(provider: OpenRouterProvider) -> None:
    headers = provider._headers()
    assert headers["Authorization"] == "Bearer sk-or-test-key"
    payload = provider._payload(
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.0,
        max_output_tokens=None,
        response_schema=None,
    )
    # The key must never be embedded in the JSON body.
    assert "sk-or-test-key" not in json.dumps(payload)


@pytest.mark.asyncio
async def test_structured_parse_returns_typed_object(
    provider: OpenRouterProvider, monkeypatch
) -> None:
    client = _QueuedClient(
        [_resp(body=_completion({"title": "Regression", "difficulty": 3}))]
    )
    _patch_client(monkeypatch, client)

    result = await provider.complete_structured(
        system_prompt="extract",
        user_prompt="chapter text",
        response_model=_SampleModel,
    )

    assert result.title == "Regression"
    assert result.difficulty == 3
    assert client.post_calls == 1


@pytest.mark.asyncio
async def test_structured_sends_json_schema_response_format(
    provider: OpenRouterProvider, monkeypatch
) -> None:
    client = _QueuedClient(
        [_resp(body=_completion({"title": "Regression", "difficulty": 3}))]
    )
    _patch_client(monkeypatch, client)

    await provider.complete_structured(
        system_prompt="extract",
        user_prompt="chapter text",
        response_model=_SampleModel,
        max_output_tokens=3072,
    )

    payload = client.last_kwargs["json"]
    response_format = payload["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    props = response_format["json_schema"]["schema"]["properties"]
    assert props["title"]["type"] == "string"
    assert payload["provider"] == {"require_parameters": True}
    assert payload["max_tokens"] == 3072


@pytest.mark.asyncio
async def test_complete_text_omits_response_format(
    provider: OpenRouterProvider, monkeypatch
) -> None:
    client = _QueuedClient([_resp(body=_text_completion("plain text answer"))])
    _patch_client(monkeypatch, client)

    result = await provider.complete_text(system_prompt="s", user_prompt="u")

    assert result == "plain text answer"
    assert "response_format" not in client.last_kwargs["json"]


@pytest.mark.asyncio
async def test_structured_retries_on_invalid_json_then_succeeds(
    provider: OpenRouterProvider, monkeypatch
) -> None:
    client = _QueuedClient(
        [
            _resp(body=_completion({"title": "X"})),
            _resp(body=_completion({"title": "Regression", "difficulty": 3})),
        ]
    )
    _patch_client(monkeypatch, client)

    result = await provider.complete_structured(
        system_prompt="extract",
        user_prompt="chapter text",
        response_model=_SampleModel,
    )

    assert result.title == "Regression"
    assert client.post_calls == 2


@pytest.mark.asyncio
async def test_structured_persistent_schema_failure_raises(
    provider: OpenRouterProvider, monkeypatch
) -> None:
    client = _QueuedClient(
        [
            _resp(body=_completion({"title": "X"})),
            _resp(body=_completion({"title": "Y"})),
            _resp(body=_completion({"title": "Z"})),
        ]
    )
    _patch_client(monkeypatch, client)

    with pytest.raises(AIProviderError) as exc_info:
        await provider.complete_structured(
            system_prompt="extract",
            user_prompt="chapter text",
            response_model=_SampleModel,
        )

    assert "schema" in exc_info.value.message
    assert client.post_calls == provider._max_attempts


@pytest.mark.asyncio
async def test_authentication_error_fails_fast(
    provider: OpenRouterProvider, monkeypatch
) -> None:
    client = _QueuedClient(
        [_resp(status=401, body=_error_body(401, "Invalid API key"))]
    )
    _patch_client(monkeypatch, client)

    with pytest.raises(AIProviderError) as exc_info:
        await provider.complete_structured(
            system_prompt="extract",
            user_prompt="chapter text",
            response_model=_SampleModel,
        )

    assert exc_info.value.details.get("retryable") is False
    assert client.post_calls == 1
    assert "Invalid API key" in exc_info.value.message


@pytest.mark.asyncio
async def test_insufficient_credits_fails_fast(
    provider: OpenRouterProvider, monkeypatch
) -> None:
    client = _QueuedClient(
        [_resp(status=402, body=_error_body(402, "insufficient credits"))]
    )
    _patch_client(monkeypatch, client)

    with pytest.raises(AIProviderError) as exc_info:
        await provider.complete_structured(
            system_prompt="extract",
            user_prompt="chapter text",
            response_model=_SampleModel,
        )

    assert exc_info.value.details.get("retryable") is False
    assert client.post_calls == 1


@pytest.mark.asyncio
async def test_credits_reason_fails_fast(
    provider: OpenRouterProvider, monkeypatch
) -> None:
    body = {
        "error": {
            "code": 402,
            "message": "requires more credits, or fewer max_tokens",
            "metadata": {"reason": "openrouter_credits"},
        }
    }
    client = _QueuedClient([_resp(status=402, body=body)])
    _patch_client(monkeypatch, client)

    with pytest.raises(AIProviderError) as exc_info:
        await provider.complete_structured(
            system_prompt="extract",
            user_prompt="chapter text",
            response_model=_SampleModel,
        )

    assert exc_info.value.details.get("retryable") is False
    assert client.post_calls == 1


@pytest.mark.asyncio
async def test_in_flight_budget_exhausted_retried_then_succeeds(
    provider: OpenRouterProvider, monkeypatch
) -> None:
    _disable_sleep(monkeypatch)
    body = {
        "error": {
            "code": 402,
            "message": "would exceed your available credits given your "
            "current in-flight requests",
            "metadata": {
                "reason": "in_flight_budget_exhausted",
                "limit_source": "openrouter_in_flight_budget",
            },
        }
    }
    client = _QueuedClient(
        [
            _resp(status=402, body=body, headers={"Retry-After": "0"}),
            _resp(body=_completion({"title": "Regression", "difficulty": 3})),
        ]
    )
    _patch_client(monkeypatch, client)

    result = await provider.complete_structured(
        system_prompt="extract",
        user_prompt="chapter text",
        response_model=_SampleModel,
    )

    assert result.title == "Regression"
    assert result.difficulty == 3
    assert client.post_calls == 2


@pytest.mark.asyncio
async def test_rate_limit_retried_then_succeeds(
    provider: OpenRouterProvider, monkeypatch
) -> None:
    _disable_sleep(monkeypatch)
    client = _QueuedClient(
        [
            _resp(
                status=429,
                body=_error_body(429, "rate limited"),
                headers={"Retry-After": "2"},
            ),
            _resp(body=_completion({"title": "Regression", "difficulty": 3})),
        ]
    )
    _patch_client(monkeypatch, client)

    result = await provider.complete_structured(
        system_prompt="extract",
        user_prompt="chapter text",
        response_model=_SampleModel,
    )

    assert result.title == "Regression"
    assert client.post_calls == 2


@pytest.mark.asyncio
async def test_provider_unavailable_error_type_retried(
    provider: OpenRouterProvider, monkeypatch
) -> None:
    _disable_sleep(monkeypatch)
    client = _QueuedClient(
        [
            _resp(
                status=200,
                body=_error_body(
                    502,
                    "provider down",
                    error_type="provider_unavailable",
                ),
            ),
            _resp(body=_completion({"title": "Regression", "difficulty": 3})),
        ]
    )
    _patch_client(monkeypatch, client)

    result = await provider.complete_structured(
        system_prompt="extract",
        user_prompt="chapter text",
        response_model=_SampleModel,
    )

    assert result.title == "Regression"
    assert client.post_calls == 2


@pytest.mark.asyncio
async def test_transient_failures_exhausted_raises(
    provider: OpenRouterProvider, monkeypatch
) -> None:
    _disable_sleep(monkeypatch)
    responses = [_resp(status=429, body=_error_body(429, "rate limited"))] * (
        provider._max_retries + 1
    )
    client = _QueuedClient(responses)
    _patch_client(monkeypatch, client)

    with pytest.raises(AIProviderError) as exc_info:
        await provider.complete_text(system_prompt="s", user_prompt="u")

    assert exc_info.value.details.get("retryable") is False
    assert client.post_calls == provider._max_retries + 1


@pytest.mark.asyncio
async def test_timeout_then_success(provider: OpenRouterProvider, monkeypatch) -> None:
    _disable_sleep(monkeypatch)
    client = _QueuedClient(
        [
            httpx.TimeoutException("timed out"),
            _resp(body=_text_completion("answer after timeout")),
        ]
    )
    _patch_client(monkeypatch, client)

    result = await provider.complete_text(system_prompt="s", user_prompt="u")

    assert result == "answer after timeout"
    assert client.post_calls == 2


@pytest.mark.asyncio
async def test_connection_error_exhausted_raises(
    provider: OpenRouterProvider, monkeypatch
) -> None:
    _disable_sleep(monkeypatch)
    client = _QueuedClient(
        [httpx.ConnectError("connection refused")] * (provider._max_retries + 1)
    )
    _patch_client(monkeypatch, client)

    with pytest.raises(AIProviderError) as exc_info:
        await provider.complete_text(system_prompt="s", user_prompt="u")

    assert "reach OpenRouter" in exc_info.value.message
    assert client.post_calls == provider._max_retries + 1


@pytest.mark.asyncio
async def test_empty_content_with_length_finish_reason_advises_tokens(
    provider: OpenRouterProvider, monkeypatch
) -> None:
    body = {
        "choices": [
            {
                "message": {"role": "assistant", "content": ""},
                "finish_reason": "length",
                "error": None,
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    client = _QueuedClient([_resp(body=body)])
    _patch_client(monkeypatch, client)

    with pytest.raises(AIProviderError) as exc_info:
        await provider.complete_text(system_prompt="s", user_prompt="u")

    assert "empty" in exc_info.value.message
    assert exc_info.value.details.get("reason") == "length"


@pytest.mark.asyncio
async def test_refusal_raises(provider: OpenRouterProvider, monkeypatch) -> None:
    body = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "refusal": "I cannot comply.",
                }
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    client = _QueuedClient([_resp(body=body)])
    _patch_client(monkeypatch, client)

    with pytest.raises(AIProviderError) as exc_info:
        await provider.complete_text(system_prompt="s", user_prompt="u")

    assert "refused" in exc_info.value.message
    assert client.post_calls == 1


@pytest.mark.asyncio
async def test_usage_captured_after_success(
    provider: OpenRouterProvider, monkeypatch
) -> None:
    client = _QueuedClient(
        [
            _resp(
                body=_completion(
                    {"title": "Regression", "difficulty": 3},
                    usage={
                        "prompt_tokens": 120,
                        "completion_tokens": 45,
                        "total_tokens": 165,
                    },
                    provider="OpenAI",
                )
            )
        ]
    )
    _patch_client(monkeypatch, client)

    await provider.complete_structured(
        system_prompt="extract",
        user_prompt="chapter text",
        response_model=_SampleModel,
    )

    assert provider.last_usage is not None
    assert provider.last_usage.prompt_tokens == 120
    assert provider.last_usage.completion_tokens == 45
    assert provider.last_usage.total_tokens == 165
    assert provider.last_usage.provider == "OpenAI"
