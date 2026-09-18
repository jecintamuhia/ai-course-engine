"""Structured application logging configuration."""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

from app.core.config import Settings

_request_id: ContextVar[str] = ContextVar(
    "request_id",
    default="-",
)


class RequestContextFilter(logging.Filter):
    """Inject request context into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Attach request ID to the current log record."""
        record.request_id = _request_id.get()
        return True


class SafeFormatter(logging.Formatter):
    """Formatter that includes useful operational context."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record consistently."""
        message = super().format(record)

        return (
            f"{message} "
            f"request_id={getattr(record, 'request_id', '-')}"
        )


def set_request_id(request_id: str) -> None:
    """Set request ID for the current asynchronous execution context."""
    _request_id.set(request_id)


def get_request_id() -> str:
    """Return the current request ID."""
    return _request_id.get()


def configure_logging(settings: Settings) -> None:
    """Configure application-wide logging."""
    level = getattr(logging, settings.log_level.upper())

    formatter = SafeFormatter(
        fmt=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s "
            "%(message)s"
        ),
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(RequestContextFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Keep noisy third-party loggers under control.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Create an application logger."""
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **context: Any,
) -> None:
    """
    Log a structured operational event.

    Secrets, credentials, tokens and document contents must never be
    passed into this helper.
    """
    safe_context = {
        key: value
        for key, value in context.items()
        if key.lower()
        not in {
            "password",
            "token",
            "access_token",
            "refresh_token",
            "api_key",
            "secret",
            "secret_key",
        }
    }

    logger.log(
        level,
        "%s %s",
        event,
        " ".join(
            f"{key}={value!r}"
            for key, value in safe_context.items()
        ),
    )