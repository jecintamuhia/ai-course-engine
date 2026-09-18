"""Unit tests for OpenAIProvider, against mocked SDK responses."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import openai
import pytest
from app.core.exceptions import AIProviderError
from app.services.ai.openai_provider import OpenAIProvider
from pydantic import BaseModel


class _SampleModel(BaseModel):
    title: str
    difficulty: int


@pytest.fixture
def provider() -> OpenAIProvider:
    return OpenAIProvider(api_key="fake-key-for-tests", model="gpt-4o-mini")


@pytest.mark.asyncio
async def test_successful_structured_parse_returns_typed_object(
    provider: OpenAIProvider,
) -> None:
    fake_parsed = _SampleModel(title="Systems Theory", difficulty=3)
    fake_message = MagicMock(parsed=fake_parsed, refusal=None)
    fake_choice = MagicMock(message=fake_message)
    fake_completion = MagicMock(choices=[fake_choice])

    provider._client.chat.completions.parse = AsyncMock(
        return_value=fake_completion
    )

    result = await provider.complete_structured(
        system_prompt="extract",
        user_prompt="chunk text",
        response_model=_SampleModel,
    )

    assert result.title == "Systems Theory"
    assert result.difficulty == 3


@pytest.mark.asyncio
async def test_refusal_raises_ai_provider_error(
    provider: OpenAIProvider,
) -> None:
    fake_message = MagicMock(parsed=None, refusal="I cannot help with that.")
    fake_choice = MagicMock(message=fake_message)
    fake_completion = MagicMock(choices=[fake_choice])

    provider._client.chat.completions.parse = AsyncMock(
        return_value=fake_completion
    )

    with pytest.raises(AIProviderError) as exc_info:
        await provider.complete_structured(
            system_prompt="x", user_prompt="y", response_model=_SampleModel
        )

    assert "refusal" in exc_info.value.details


@pytest.mark.asyncio
async def test_rate_limit_error_wrapped_as_retryable(
    provider: OpenAIProvider,
) -> None:
    async def raise_rate_limit(*args, **kwargs):
        raise openai.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        )

    provider._client.chat.completions.parse = raise_rate_limit

    with pytest.raises(AIProviderError) as exc_info:
        await provider.complete_structured(
            system_prompt="x", user_prompt="y", response_model=_SampleModel
        )

    assert exc_info.value.details.get("retryable") is True


@pytest.mark.asyncio
async def test_insufficient_quota_raised_as_non_retryable(
    provider: OpenAIProvider,
) -> None:
    body = {
        "message": "You have no credits remaining.",
        "type": "insufficient_quota",
        "param": None,
        "code": "credit_balance_exhausted",
    }

    async def raise_quota(*args, **kwargs):
        raise openai.RateLimitError(
            message="quota",
            response=MagicMock(status_code=429, headers={}),
            body=body,
        )

    provider._client.chat.completions.parse = raise_quota

    with pytest.raises(AIProviderError) as exc_info:
        await provider.complete_structured(
            system_prompt="x", user_prompt="y", response_model=_SampleModel
        )

    assert exc_info.value.details == {"cause": "insufficient_quota"}
    assert "no credits" in exc_info.value.message


@pytest.mark.asyncio
async def test_insufficient_quota_wrapped_error_payload(
    provider: OpenAIProvider,
) -> None:
    body = {
        "error": {
            "message": "You have no credits remaining.",
            "type": "insufficient_quota",
            "param": None,
            "code": "credit_balance_exhausted",
        }
    }

    async def raise_quota(*args, **kwargs):
        raise openai.RateLimitError(
            message="quota",
            response=MagicMock(status_code=429, headers={}),
            body=body,
        )

    provider._client.chat.completions.parse = raise_quota

    with pytest.raises(AIProviderError) as exc_info:
        await provider.complete_structured(
            system_prompt="x", user_prompt="y", response_model=_SampleModel
        )

    assert exc_info.value.details.get("cause") == "insufficient_quota"
    assert exc_info.value.details.get("retryable") is None


@pytest.mark.asyncio
async def test_null_parsed_output_raises(provider: OpenAIProvider) -> None:
    fake_message = MagicMock(parsed=None, refusal=None)
    fake_choice = MagicMock(message=fake_message)
    fake_completion = MagicMock(choices=[fake_choice])

    provider._client.chat.completions.parse = AsyncMock(
        return_value=fake_completion
    )

    with pytest.raises(AIProviderError):
        await provider.complete_structured(
            system_prompt="x", user_prompt="y", response_model=_SampleModel
        )