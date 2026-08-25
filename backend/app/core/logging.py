from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any


request_id_context: ContextVar[str | None] = ContextVar(
    "request_id",
    default=None,
)

job_id_context: ContextVar[str | None] = ContextVar(
    "job_id",
    default=None,
)


class JsonFormatter(logging.Formatter):
    """
    Format logs as structured JSON.

    This makes logs easier to ingest into production observability systems.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = request_id_context.get()
        job_id = job_id_context.get()

        if request_id:
            payload["request_id"] = request_id

        if job_id:
            payload["job_id"] = job_id

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "course_id"):
            payload["course_id"] = record.course_id

        if hasattr(record, "document_id"):
            payload["document_id"] = record.document_id

        if hasattr(record, "operation"):
            payload["operation"] = record.operation

        return json.dumps(
            payload,
            default=str,
            ensure_ascii=False,
        )


def configure_logging(log_level: str = "INFO") -> None:
    """
    Configure application-wide structured logging.
    """

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()

    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level.upper())

    # Keep noisy third-party loggers controlled.
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)