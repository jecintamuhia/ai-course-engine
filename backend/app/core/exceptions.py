"""Application exception hierarchy."""

from typing import Any


class AppError(Exception):
    """Base exception for expected application-level failures."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(AppError):
    """Raised when application configuration is invalid."""

    status_code = 500
    error_code = "configuration_error"


class DatabaseError(AppError):
    """Raised when a database operation fails."""

    status_code = 503
    error_code = "database_error"


class DocumentNotFound(AppError):
    """Raised when a requested document does not exist."""

    status_code = 404
    error_code = "document_not_found"


class CourseNotFound(AppError):
    """Raised when a requested course does not exist."""

    status_code = 404
    error_code = "course_not_found"


class IngestionJobNotFound(AppError):
    """Raised when an ingestion job does not exist."""

    status_code = 404
    error_code = "ingestion_job_not_found"


class InvalidStateTransition(AppError):
    """Raised when a domain state transition is invalid."""

    status_code = 409
    error_code = "invalid_state_transition"


class DocumentProcessingError(AppError):
    """Raised when document processing fails."""

    status_code = 422
    error_code = "document_processing_error"


class AIProviderError(AppError):
    """Raised when an AI provider operation fails."""

    status_code = 502
    error_code = "ai_provider_error"


class AIOutputValidationError(AppError):
    """Raised when AI output fails structural validation."""

    status_code = 422
    error_code = "ai_output_validation_error"


class CurriculumValidationError(AppError):
    """Raised when generated curriculum violates constraints."""

    status_code = 422
    error_code = "curriculum_validation_error"


class MoodleIntegrationError(AppError):
    """Raised when Moodle integration fails."""

    status_code = 502
    error_code = "moodle_integration_error"