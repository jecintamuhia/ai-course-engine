"""OpenRouter implementation of the LLMProvider interface.

Talks to OpenRouter's OpenAI-compatible ``/chat/completions`` endpoint
using ``httpx`` (no extra dependency). Structured outputs use the
``response_format`` of type ``json_schema`` (OpenRouter structured
outputs) with ``strict: true``; schema conformance is additionally
enforced client-side with Pydantic and, when it fails, retried a bounded
number of times with a corrective hint.

Errors are classified from OpenRouter's typed ``error_type`` codes (and,
when absent, the HTTP status) into two categories:

* permanent — misconfigured key, insufficient credits, guarded/refused
  requests, invalid prompts/schemas, unknown models. These fail fast.
* transient — rate limits, provider overload/unavailability, timeouts,
  5xx responses, connection failures. These are retried a bounded number
  of times with exponential backoff, honoring a ``Retry-After`` header
  when OpenRouter provides one.

Token usage from the final response is captured (``last_usage``) and
logged so cost and latency can be reported without leaking the API key
or the textbook content.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import httpx
from app.core.exceptions import AIProviderError
from app.core.logging import get_logger
from app.services.ai.base import LLMProvider, ResponseModelT
from pydantic import ValidationError

logger = get_logger(__name__)

_CHAT_COMPLETIONS_PATH = "/chat/completions"

# OpenRouter typed error codes that are transient (retryable) per
# https://openrouter.ai/docs/errors. Anything not listed here is treated
# as permanent.
_TRANSIENT_ERROR_TYPES = frozenset(
    {
        "rate_limit_exceeded",
        "provider_overloaded",
        "provider_unavailable",
        "timeout",
        "server",
        "unmapped",
    }
)

# Provider-generated error_type values seen on a 200 response body after
# generation already started (mid-stream style failures).
_TRANSIENT_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504, 529})


@dataclass
class ProviderUsage:
    """Token usage reported by OpenRouter for one model call."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    provider: str | None = None


def _compact_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Return a copy of a JSON schema with verbose annotations stripped.

    The compact schema is only used as a concise corrective hint inside
    the prompt; the authoritative schema is always sent through
    ``response_format``.
    """
    compact: dict[str, Any] = {}
    for key, value in schema.items():
        if key in {"title", "description", "default", "examples", "format"}:
            continue
        if isinstance(value, dict):
            compact[key] = _compact_json_schema(value)
        elif isinstance(value, list):
            compact[key] = [
                _compact_json_schema(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            compact[key] = value
    return compact


def _parse_error_type(status_code: int, body: dict[str, Any]) -> str:
    """Extract OpenRouter's typed error_type from an error response."""
    error = body.get("error") if isinstance(body.get("error"), dict) else {}
    metadata = (
        error.get("metadata") if isinstance(error.get("metadata"), dict) else {}
    )
    error_type = metadata.get("error_type")
    if isinstance(error_type, str) and error_type:
        return error_type
    return ""


def _parse_error_reason(body: dict[str, Any]) -> str:
    """Extract OpenRouter's finer-grained ``metadata.reason`` code."""
    error = body.get("error") if isinstance(body.get("error"), dict) else {}
    metadata = (
        error.get("metadata") if isinstance(error.get("metadata"), dict) else {}
    )
    reason = metadata.get("reason")
    if isinstance(reason, str) and reason:
        return reason
    return ""


# 402 responses are retryable when the request was rejected because the
# account's in-flight budget was momentarily exhausted (OpenRouter asks
# the client to wait for in-flight requests to settle, usually via
# ``Retry-After``). A plain credits/quota shortfall is permanent until
# the account is topped up, so it must fail fast.
_TRANSIENT_REASONS = frozenset({"in_flight_budget_exhausted"})


def _status_implies_transient(status_code: int) -> bool:
    return status_code in _TRANSIENT_HTTP_STATUSES or 500 <= status_code < 600


class OpenRouterProvider(LLMProvider):
    """LLMProvider backed by OpenRouter's chat completions API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: float = 300.0,
        max_attempts: int = 3,
        max_retries: int = 5,
        retry_base_delay_seconds: float = 2.0,
        max_retry_delay_seconds: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._max_retries = max_retries
        self._retry_base_delay_seconds = retry_base_delay_seconds
        self._max_retry_delay_seconds = max_retry_delay_seconds
        self.last_usage: ProviderUsage | None = None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-Title": "AI Course Engine",
        }

    def _payload(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        max_output_tokens: int | None,
        response_schema: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
        }

        if response_schema is not None:
            schema_name = self._schema_name(response_schema)
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": response_schema,
                },
            }
            payload["provider"] = {"require_parameters": True}

        if max_output_tokens is not None:
            payload["max_tokens"] = max_output_tokens

        return payload

    @staticmethod
    def _schema_name(schema: dict[str, Any]) -> str:
        raw = str(schema.get("title") or "response")
        # response_format schema names must be identifiers usable by the
        # upstream provider's structured-output layer.
        cleaned = "".join(char for char in raw if char.isalnum() or char == "_")
        if not cleaned or not cleaned[0].isalpha():
            cleaned = f"response_{cleaned}" if cleaned else "response"
        return cleaned[:64]

    async def _send(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        max_output_tokens: int | None,
        response_schema: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Send one request with bounded transient retries.

        Returns the parsed 2xx JSON body. Permanent errors are raised
        immediately; transient errors are retried with exponential
        backoff (honoring ``Retry-After``) up to ``max_retries``.
        """
        payload = self._payload(
            messages=messages,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_schema=response_schema,
        )
        delay = self._retry_base_delay_seconds

        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.post(
                        f"{self._base_url}{_CHAT_COMPLETIONS_PATH}",
                        headers=self._headers(),
                        json=payload,
                    )
            except httpx.TimeoutException as exc:
                if attempt >= self._max_retries:
                    raise AIProviderError(
                        "OpenRouter request timed out after all retries.",
                    ) from exc
                logger.warning(
                    "OpenRouter request timed out; retrying attempt=%s",
                    attempt + 1,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._max_retry_delay_seconds)
                continue
            except httpx.HTTPError as exc:
                if attempt >= self._max_retries:
                    raise AIProviderError(
                        "Failed to reach OpenRouter after all retries.",
                    ) from exc
                logger.warning(
                    "Failed to reach OpenRouter; retrying attempt=%s",
                    attempt + 1,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._max_retry_delay_seconds)
                continue

            try:
                body = response.json()
            except ValueError:
                body = {}

            if response.status_code < 400 and "error" not in body:
                return body

            error_type = _parse_error_type(response.status_code, body)
            reason = _parse_error_reason(body)
            transient = (
                error_type in _TRANSIENT_ERROR_TYPES
                or reason in _TRANSIENT_REASONS
                or (
                    not error_type
                    and not reason
                    and _status_implies_transient(response.status_code)
                )
            )

            message = self._error_message(
                response.status_code, error_type, body, response.text
            )

            if not transient or attempt >= self._max_retries:
                raise AIProviderError(
                    message,
                    details={"retryable": False},
                )

            retry_after = self._retry_after_seconds(response)
            wait = min(
                retry_after if retry_after else delay,
                self._max_retry_delay_seconds,
            )
            logger.warning(
                "OpenRouter transient error (HTTP %s, type=%r, reason=%r); "
                "retrying attempt=%s wait_seconds=%.1f",
                response.status_code,
                error_type,
                reason,
                attempt + 1,
                wait,
            )
            await asyncio.sleep(wait)
            delay = min(delay * 2, self._max_retry_delay_seconds)

        raise AssertionError("unreachable")

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        raw = response.headers.get("Retry-After")
        if not raw:
            return None
        try:
            return max(0.0, float(raw))
        except ValueError:
            return None

    @staticmethod
    def _error_message(
        status_code: int,
        error_type: str,
        body: dict[str, Any],
        raw_text: str,
    ) -> str:
        error = body.get("error") if isinstance(body.get("error"), dict) else {}
        detail = error.get("message")
        if isinstance(detail, str) and detail:
            return f"OpenRouter error (HTTP {status_code}): {detail}"
        if error_type:
            return (
                f"OpenRouter error (HTTP {status_code}, type={error_type})."
            )
        snippet = raw_text[:200]
        logger.warning(
            "OpenRouter non-2xx response without structured error "
            "status=%s body=%r",
            status_code,
            snippet,
        )
        return f"OpenRouter returned HTTP {status_code}."

    def _capture_usage(self, body: dict[str, Any]) -> None:
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        try:
            prompt_tokens = int(usage.get("prompt_tokens") or 0)
            completion_tokens = int(usage.get("completion_tokens") or 0)
            total_tokens = int(usage.get("total_tokens") or 0)
        except (TypeError, ValueError):
            return
        self.last_usage = ProviderUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            model=str(body.get("model") or self._model),
            provider=(
                str(body["provider"])
                if isinstance(body.get("provider"), str)
                else None
            ),
        )

    def _extract_content(self, body: dict[str, Any]) -> str:
        """
        Pull the assistant text from a 2xx body and translate the known
        failure shapes into AIProviderError.
        """
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            self._capture_usage(body)
            raise AIProviderError(
                "OpenRouter returned no completion choices.",
                details={"retryable": False},
            )

        choice = choices[0]
        message = (
            choice.get("message") if isinstance(choice.get("message"), dict) else {}
        )

        refusal = message.get("refusal")
        if refusal:
            self._capture_usage(body)
            raise AIProviderError(
                "Model refused to generate a response.",
                details={"retryable": False},
            )

        content = message.get("content")
        finish_reason = choice.get("finish_reason")

        if content is None or (isinstance(content, str) and not content.strip()):
            self._capture_usage(body)
            details: dict[str, Any] = {"reason": finish_reason}
            if finish_reason == "length":
                details["advice"] = (
                    "Generation stopped because the output budget ran out; "
                    "raise max_output_tokens for this chapter."
                )
            raise AIProviderError(
                "OpenRouter returned empty content.",
                details=details,
            )

        if not isinstance(content, str):
            raise AIProviderError(
                "OpenRouter returned a non-text completion.",
                details={"retryable": False},
            )

        self._capture_usage(body)
        return content

    @staticmethod
    def _validation_hint(exc: ValidationError) -> str:
        """Condense a ValidationError into a concise corrective hint."""
        details = []
        for error in exc.errors()[:5]:
            location = ".".join(str(part) for part in error["loc"])
            details.append(f"{location} ({error['type']})")
        return "; ".join(details) if details else "invalid JSON"

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
        Generate a structured response conforming to response_model.

        ``response_format`` (json_schema, strict) asks OpenRouter to route
        only to endpoints that can enforce the schema. The returned JSON
        is validated client-side; on schema violations the model is
        retried with a corrective hint up to ``max_attempts``. Persistent
        failure raises AIProviderError.
        """
        schema = response_model.model_json_schema()
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        for attempt in range(self._max_attempts):
            body = await self._send(
                messages=messages,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                response_schema=schema,
            )
            content = self._extract_content(body)

            try:
                result = response_model.model_validate_json(content)
            except ValidationError as exc:
                if attempt >= self._max_attempts - 1:
                    raise AIProviderError(
                        "OpenRouter repeatedly failed to produce output "
                        "conforming to the requested schema.",
                        details={"last_error": self._validation_hint(exc)},
                    ) from exc

                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your previous response did not conform to the "
                            "requested JSON schema. Errors: "
                            f"{self._validation_hint(exc)}. "
                            "Re-output the COMPLETE corrected JSON object "
                            "conforming to exactly this schema:\n"
                            f"{json.dumps(_compact_json_schema(schema))}\n\n"
                            "Each item in a list must keep its required "
                            "type and shape: for example, every 'concepts' "
                            "item must be an object with 'name' and "
                            "'description' fields, never a plain string. "
                            "Output only the JSON object."
                        ),
                    }
                )
            else:
                self._log_success("complete_structured")
                return result

        raise AssertionError("unreachable")

    async def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
    ) -> str:
        """Generate a free-form text response."""
        body = await self._send(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_schema=None,
        )
        content = self._extract_content(body)
        self._log_success("complete_text")
        return content

    def _log_success(self, operation: str) -> None:
        usage = self.last_usage
        logger.info(
            "OpenRouter call succeeded operation=%s model=%s provider=%s "
            "prompt_tokens=%s completion_tokens=%s total_tokens=%s",
            operation,
            self._model,
            usage.provider if usage else None,
            usage.prompt_tokens if usage else None,
            usage.completion_tokens if usage else None,
            usage.total_tokens if usage else None,
        )