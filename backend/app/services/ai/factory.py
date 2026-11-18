"""Factory for constructing the configured LLMProvider."""

from __future__ import annotations

from app.core.config import Settings
from app.core.exceptions import ConfigurationError
from app.services.ai.base import LLMProvider
from app.services.ai.openai_provider import OpenAIProvider
from app.services.ai.openrouter_provider import OpenRouterProvider


def create_llm_provider(settings: Settings) -> LLMProvider:
    """
    Construct the LLMProvider configured via settings.ai_provider.

    Raises ConfigurationError for an unrecognized provider name or a
    missing required API key, so misconfiguration fails at startup
    rather than on the first AI-dependent request.
    """
    if settings.ai_provider == "openai":
        if not settings.openai_api_key.get_secret_value():
            raise ConfigurationError(
                "OPENAI_API_KEY is required when AI_PROVIDER=openai."
            )

        return OpenAIProvider(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.openai_model,
        )

    if settings.ai_provider == "openrouter":
        if not settings.openrouter_api_key.get_secret_value():
            raise ConfigurationError(
                "OPENROUTER_API_KEY is required when AI_PROVIDER=openrouter."
            )

        if not settings.openrouter_model:
            raise ConfigurationError(
                "OPENROUTER_MODEL is required when AI_PROVIDER=openrouter "
                "(e.g. 'openai/gpt-4o')."
            )

        return OpenRouterProvider(
            api_key=settings.openrouter_api_key.get_secret_value(),
            model=settings.openrouter_model,
            base_url=settings.openrouter_base_url,
            timeout_seconds=settings.openrouter_timeout_seconds,
            max_attempts=settings.openrouter_max_attempts,
            max_retries=settings.openrouter_max_retries,
            retry_base_delay_seconds=settings.openrouter_retry_base_delay_seconds,
            max_retry_delay_seconds=settings.openrouter_max_retry_delay_seconds,
            app_title=settings.app_name,
        )

    raise ConfigurationError(
        f"Unknown AI_PROVIDER {settings.ai_provider!r}. Supported: "
        "'openai', 'openrouter'."
    )
