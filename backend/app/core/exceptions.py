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


class CurriculumNotFound(AppError):
    """Raised when a requested curriculum does not exist."""

    status_code = 404
    error_code = "curriculum_not_found"


class TopicNotFound(AppError):
    """Raised when a requested topic does not exist."""

    status_code = 404
    error_code = "topic_not_found"


class LessonNotFound(AppError):
    """Raised when a requested lesson does not exist."""

    status_code = 404
    error_code = "lesson_not_found"


class LessonContentBlockNotFound(AppError):
    """Raised when a requested lesson content block does not exist."""

    status_code = 404
    error_code = "lesson_content_block_not_found"


class CurriculumUnitNotFound(AppError):
    """Raised when a requested curriculum unit (week) does not exist."""

    status_code = 404
    error_code = "curriculum_unit_not_found"


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


class ContentAnalysisEmptyError(AppError):
    """
    Raised when content analysis finishes without producing any topic.

    Individual chapters may legitimately be skipped as too thin, but a
    document that yields nothing cannot generate a curriculum, so the
    ingestion job must fail rather than report success on empty output.
    """

    status_code = 422
    error_code = "content_analysis_empty"


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


class MoodlePublishBlockedError(MoodleIntegrationError):
    """Raised when a preflight check blocks publishing before any write.

    The curriculum is never modified by this failure; the details carry
    the structured readiness issues a Moodle administrator must address.
    """

    status_code = 409
    error_code = "moodle_publish_blocked"


class QualityReportNotFound(AppError):
    """Raised when no QA report exists for a curriculum."""

    status_code = 404
    error_code = "quality_report_not_found"


class AssessmentNotFound(AppError):
    """Raised when a requested assessment does not exist."""

    status_code = 404
    error_code = "assessment_not_found"


class ContentQAError(AppError):
    """
    Raised when automated content QA is severe enough to block an action.

    A ``fail`` verdict from run_curriculum_qa blocks lecturer approval
    and Moodle publishing. Details carry the QA verdict and the severe
    findings the lecturer must address first.
    """

    status_code = 409
    error_code = "qa_blocked"


class AuthenticationError(AppError):
    """Raised when a request cannot be authenticated."""

    status_code = 401
    error_code = "authentication_error"


class InvalidCredentialsError(AuthenticationError):
    """Raised when an email/password pair does not authenticate."""

    error_code = "invalid_credentials"


class AuthorizationError(AppError):
    """Raised when an authenticated user lacks the required permission."""

    status_code = 403
    error_code = "authorization_error"


class UserNotFound(AppError):
    """Raised when a requested user does not exist."""

    status_code = 404
    error_code = "user_not_found"


class ContentGenerationNotAllowed(AppError):
    """
    Raised when bulk lesson generation is requested for a curriculum that
    is not in a state that permits it (it must be approved first, since
    generation targets a reviewed 16-week plan).
    """

    status_code = 409
    error_code = "content_generation_not_allowed"


class EmailAlreadyRegisteredError(AppError):
    """Raised when registration is attempted with an email that already exists."""

    status_code = 409
    error_code = "email_already_registered"


class RegistrationDisabledError(AppError):
    """Raised when self-registration is turned off for this deployment."""

    status_code = 403
    error_code = "registration_disabled"


class RegistrationDomainNotAllowedError(AppError):
    """
    Raised when a registration email's domain is not on the allowlist.

    Used when ``AUTH_REGISTRATION_ALLOWED_DOMAINS`` restricts sign-ups to
    specific providers (for example Gmail) or an institution.
    """

    status_code = 403
    error_code = "registration_domain_not_allowed"
