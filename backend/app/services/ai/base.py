"""Abstract LLM provider interface. All AI-dependent code depends on
this, never on a provider SDK directly."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

ResponseModelT = TypeVar("ResponseModelT", bound=BaseModel)


class LLMProvider(ABC):
    """Abstract interface for a large language model provider."""

    @abstractmethod
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
        Generate a response constrained to match response_model's schema.

        Implementations must guarantee the returned object is a valid
        instance of response_model, or raise AIProviderError — never
        return a partially-valid or unvalidated result.
        """
        raise NotImplementedError

    @abstractmethod
    async def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
    ) -> str:
        """Generate a free-form text response."""
        raise NotImplementedError