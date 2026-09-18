"""OpenAI implementation of the LLMProvider interface."""

from __future__ import annotations

import asyncio

import openai
from app.core.exceptions import AIProviderError
from app.core.logging import get_logger
from app.services.ai.base import LLMProvider, ResponseModelT
from openai import AsyncOpenAI

logger = get_logger(__name__)


def _is_quota_error(exc: openai.RateLimitError) -> bool:
    """True when a 429 is an account credit/balance issue, not a transient limit."""
    try:
        body = exc.body if isinstance(exc.body, dict) else {}
        error_payload = (
            body.get("error") if isinstance(body.get("error"), dict) else body
        )
        code = error_payload.get("code")
        error_type = error_payload.get("type")
        message = error_payload.get("message") or ""
        return (
            code in ("insufficient_quota", "credit_balance_exhausted")
            or error_type == "insufficient_quota"
            or "no credits remaining" in message.lower()
        )
    except Exception:
        return False


class OpenAIProvider(LLMProvider):
    """LLMProvider backed by OpenAI's chat completions API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
        retry_base_delay_seconds: float = 4.0,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)
        self._model = model
        self._max_retries = max_retries
        self._retry_base_delay_seconds = retry_base_delay_seconds

    def _is_retryable(self, exc: AIProviderError) -> bool:
        return bool(exc.details and exc.details.get("retryable"))

    async def _call_with_retry(self, operation) -> object:
        """
        Retry "retryable" AIProviderErrors (rate limits, connection
        failures) with exponential backoff. Non-retryable errors are
        re-raised immediately.
        """
        delay = self._retry_base_delay_seconds
        for attempt in range(self._max_retries + 1):
            try:
                return await operation()
            except AIProviderError as exc:
                if not self._is_retryable(exc) or attempt >= self._max_retries:
                    raise
                await asyncio.sleep(delay)
                delay *= 2
        raise AssertionError("unreachable")

    async def _parse_with_retry(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ResponseModelT],
        temperature: float,
        max_output_tokens: int | None,
    ) -> ResponseModelT:
        async def _attempt() -> ResponseModelT:
            try:
                return await self._client.chat.completions.parse(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format=response_model,
                    temperature=temperature,
                    max_completion_tokens=max_output_tokens,
                )
            except openai.LengthFinishReasonError as exc:
                raise AIProviderError(
                    "Model response was truncated before completing valid "
                    "structured output. Consider raising max_output_tokens.",
                    details={"reason": "length_finish"},
                ) from exc
            except openai.AuthenticationError as exc:
                raise AIProviderError(
                    "OpenAI authentication failed. Check OPENAI_API_KEY.",
                ) from exc
            except openai.RateLimitError as exc:
                if _is_quota_error(exc):
                    raise AIProviderError(
                        "OpenAI account has no credits remaining. Add "
                        "credits at platform.openai.com and retry.",
                        details={"cause": "insufficient_quota"},
                    ) from exc
                raise AIProviderError(
                    "OpenAI rate limit exceeded.",
                    details={"retryable": True},
                ) from exc
            except (openai.APIConnectionError, openai.APITimeoutError) as exc:
                raise AIProviderError(
                    "Failed to reach OpenAI API.",
                    details={"retryable": True},
                ) from exc
            except openai.BadRequestError as exc:
                logger.warning("OpenAI rejected request: %s", exc)
                raise AIProviderError(
                    "OpenAI rejected the request.",
                ) from exc
            except openai.APIError as exc:
                logger.exception("OpenAI API error")
                raise AIProviderError(
                    "OpenAI returned an unexpected error."
                ) from exc

        completion = await self._call_with_retry(_attempt)
        choice = completion.choices[0]

        if choice.message.refusal:
            raise AIProviderError(
                "Model refused to generate a response.",
                details={"refusal": choice.message.refusal},
            )

        parsed = choice.message.parsed

        if parsed is None:
            raise AIProviderError(
                "Model response could not be parsed into the expected structure.",
            )

        return parsed

    async def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ResponseModelT],
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
    ) -> ResponseModelT:
        """
        Generate structured output using OpenAI's guaranteed-schema
        parsing mode. The API itself enforces schema conformance; this
        method additionally guards against refusals and null parses.
        """
        return await self._parse_with_retry(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

    async def _complete_text_with_retry(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_output_tokens: int | None,
    ) -> str:
        async def _attempt() -> str:
            try:
                return await self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_completion_tokens=max_output_tokens,
                )
            except openai.AuthenticationError as exc:
                raise AIProviderError(
                    "OpenAI authentication failed. Check OPENAI_API_KEY.",
                ) from exc
            except openai.RateLimitError as exc:
                if _is_quota_error(exc):
                    raise AIProviderError(
                        "OpenAI account has no credits remaining. Add "
                        "credits at platform.openai.com and retry.",
                        details={"cause": "insufficient_quota"},
                    ) from exc
                raise AIProviderError(
                    "OpenAI rate limit exceeded.",
                    details={"retryable": True},
                ) from exc
            except (openai.APIConnectionError, openai.APITimeoutError) as exc:
                raise AIProviderError(
                    "Failed to reach OpenAI API.",
                    details={"retryable": True},
                ) from exc
            except openai.APIError as exc:
                logger.exception("OpenAI API error")
                raise AIProviderError(
                    "OpenAI returned an unexpected error."
                ) from exc

        completion = await self._call_with_retry(_attempt)
        content = completion.choices[0].message.content

        if content is None:
            raise AIProviderError("Model returned an empty response.")

        return content

    async def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
    ) -> str:
        """Generate a free-form text response."""
        return await self._complete_text_with_retry(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
