from __future__ import annotations


class AppError(Exception):
    """
    Base class for expected application errors.
    """

    status_code: int = 500
    error_code: str = "APP_ERROR"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message)

        self.message = message

        if status_code is not None:
            self.status_code = status_code

        if error_code is not None:
            self.error_code = error_code


class NotFoundError(AppError):
    status_code = 404
    error_code = "NOT_FOUND"


class ValidationError(AppError):
    status_code = 422
    error_code = "VALIDATION_ERROR"


class UnauthorizedError(AppError):
    status_code = 401
    error_code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    status_code = 403
    error_code = "FORBIDDEN"


class ConflictError(AppError):
    status_code = 409
    error_code = "CONFLICT"


class ServiceUnavailableError(AppError):
    status_code = 503
    error_code = "SERVICE_UNAVAILABLE"


class CourseNotFound(NotFoundError):
    error_code = "COURSE_NOT_FOUND"


class DocumentNotFound(NotFoundError):
    error_code = "DOCUMENT_NOT_FOUND"


class IngestionJobNotFound(NotFoundError):
    error_code = "INGESTION_JOB_NOT_FOUND"


class InvalidStateTransition(ConflictError):
    error_code = "INVALID_STATE_TRANSITION"


class DocumentProcessingError(AppError):
    status_code = 500
    error_code = "DOCUMENT_PROCESSING_ERROR"


class AIProviderError(AppError):
    status_code = 502
    error_code = "AI_PROVIDER_ERROR"


class AIOutputValidationError(AppError):
    status_code = 422
    error_code = "AI_OUTPUT_VALIDATION_ERROR"


class CurriculumValidationError(AppError):
    status_code = 422
    error_code = "CURRICULUM_VALIDATION_ERROR"


class MoodleIntegrationError(AppError):
    status_code = 502
    error_code = "MOODLE_INTEGRATION_ERROR"