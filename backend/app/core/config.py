"""Application configuration and environment management."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "testing", "staging", "production"]
AIProvider = Literal["openai", "openrouter"]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------

    app_name: str = "AI Course Engine"
    app_version: str = "0.1.0"
    environment: Environment = "development"
    debug: bool = False

    api_v1_prefix: str = "/api/v1"

    # ------------------------------------------------------------------
    # Server
    # ------------------------------------------------------------------

    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    database_url: str = (
        "postgresql+asyncpg://course_engine:course_engine@localhost:5432/course_engine"
    )

    database_pool_size: int = Field(default=10, ge=1)
    database_max_overflow: int = Field(default=20, ge=0)
    database_pool_timeout: int = Field(default=30, ge=1)
    database_pool_recycle: int = Field(default=1800, ge=60)

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------

    redis_url: str = "redis://localhost:6379/0"

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------

    secret_key: SecretStr = Field(
        default=SecretStr("development-only-change-this-secret-before-production")
    )

    # ------------------------------------------------------------------
    # Authentication (JWT)
    # ------------------------------------------------------------------

    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=720, ge=1)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    auth_registration_enabled: bool = Field(default=True)

    auth_registration_allowed_domains: list[str] = Field(
        default_factory=list,
        description=(
            "Restrict self-registration to these email domains "
            "(e.g. ['gmail.com']). Empty means any valid email address is "
            "accepted. Registration never grants admin rights."
        ),
    )

    # ------------------------------------------------------------------
    # Google OAuth (Sign in with Google)
    # ------------------------------------------------------------------

    google_oauth_client_id: SecretStr = Field(default=SecretStr(""))
    google_oauth_client_secret: SecretStr = Field(default=SecretStr(""))
    google_oauth_redirect_uri: str = ""
    google_oauth_frontend_redirect: str = "/login"
    google_oauth_timeout_seconds: float = Field(default=10.0, ge=1.0, le=60.0)
    google_oauth_exchange_ttl_seconds: int = Field(default=300, ge=30, le=900)

    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    log_level: str = "INFO"
    log_json: bool = False

    # ------------------------------------------------------------------
    # Upload / file processing
    # ------------------------------------------------------------------

    max_upload_size_mb: int = Field(default=50, ge=1, le=2048)

    upload_dir: str = Field(default="storage/documents")
    frontend_dir: str = Field(default="frontend")

    # ------------------------------------------------------------------
    # AI provider
    # ------------------------------------------------------------------

    ai_provider: AIProvider = Field(default="openrouter")

    openai_api_key: SecretStr = Field(default=SecretStr(""))
    openai_model: str = Field(default="gpt-4o-mini")

    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")
    openrouter_api_key: SecretStr = Field(default=SecretStr(""))
    openrouter_model: str = Field(default="")
    openrouter_timeout_seconds: float = Field(default=300.0, ge=1.0)
    openrouter_max_attempts: int = Field(default=3, ge=1, le=5)
    openrouter_max_retries: int = Field(default=5, ge=0, le=10)
    openrouter_retry_base_delay_seconds: float = Field(default=2.0, ge=0.1)
    openrouter_max_retry_delay_seconds: float = Field(default=120.0, ge=1.0)

    ai_extract_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    ai_extract_max_tokens: int = Field(default=2560, ge=1, le=32768)
    ai_extract_max_topics: int = Field(default=6, ge=1, le=50)
    ai_extract_max_objectives: int = Field(default=3, ge=1, le=20)
    ai_extract_max_concepts: int = Field(default=3, ge=1, le=20)
    ai_extract_max_prerequisites: int = Field(default=2, ge=0, le=20)

    ai_max_context_chars: int = Field(default=6_000, ge=1_000)
    ai_min_content_chars: int = Field(default=500, ge=1)

    # Document-wide prerequisite linking (the second analysis pass).
    # The catalogue is the whole book's topic list shown at once so the
    # model can link across chapters; it is far smaller than the chapter
    # text prompts and is budgeted separately.
    ai_linker_max_catalogue_chars: int = Field(default=24_000, ge=1_000)
    ai_linker_batch_size: int = Field(default=60, ge=1, le=500)
    ai_linker_max_prerequisites: int = Field(default=4, ge=0, le=20)

    # ------------------------------------------------------------------
    # Course content generation (lessons, diagrams, resources, activities)
    # ------------------------------------------------------------------

    content_max_lessons_per_week: int = Field(default=5, ge=1, le=20)
    content_max_tokens: int = Field(default=4000, ge=512, le=32768)
    content_max_knowledge_checks: int = Field(default=3, ge=0, le=10)
    content_max_activities: int = Field(default=2, ge=0, le=10)
    content_max_diagrams: int = Field(default=2, ge=0, le=10)
    content_max_resources: int = Field(default=3, ge=0, le=10)
    content_resource_timeout_seconds: float = Field(default=8.0, ge=1.0, le=60.0)

    # ------------------------------------------------------------------
    # Content QA
    # ------------------------------------------------------------------

    qa_min_major_prose_chars: int = Field(default=600, ge=0)
    qa_min_supporting_prose_chars: int = Field(default=200, ge=0)
    qa_duplicate_title_similarity: float = Field(default=0.8, ge=0.0, le=1.0)

    # ------------------------------------------------------------------
    # External content discovery
    # ------------------------------------------------------------------

    youtube_api_key: SecretStr = Field(default=SecretStr(""))

    # ------------------------------------------------------------------
    # Moodle integration
    # ------------------------------------------------------------------

    moodle_url: str | None = None
    moodle_token: SecretStr = Field(default=SecretStr(""))
    moodle_timeout_seconds: float = Field(default=30.0, ge=1.0)
    moodle_course_category_id: int = Field(default=1, ge=1)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Validate and normalize logging level."""
        normalized = value.upper()

        allowed = {
            "CRITICAL",
            "ERROR",
            "WARNING",
            "INFO",
            "DEBUG",
        }

        if normalized not in allowed:
            raise ValueError(
                f"Invalid LOG_LEVEL={value!r}. Expected one of: {sorted(allowed)}"
            )

        return normalized

    @property
    def max_upload_size_bytes(self) -> int:
        """Return maximum upload size in bytes."""
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        """Return whether the application runs in production."""
        return self.environment == "production"

    @property
    def google_oauth_enabled(self) -> bool:
        """Return whether Sign in with Google is configured and usable."""
        return bool(
            self.google_oauth_client_id.get_secret_value().strip()
            and self.google_oauth_client_secret.get_secret_value().strip()
        )

    @property
    def effective_google_redirect_uri(self) -> str:
        """
        Return the OAuth callback URI registered with Google.

        Falls back to a same-origin callback on the API's own prefix, which
        is correct for the SPA-served-by-FastAPI deployment and for the
        Vite dev proxy. Deployments that split the origins must set
        GOOGLE_OAUTH_REDIRECT_URI explicitly.
        """
        if self.google_oauth_redirect_uri.strip():
            return self.google_oauth_redirect_uri.strip()
        return f"{self.api_v1_prefix}/auth/google/callback"

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: SecretStr) -> SecretStr:
        """
        Reject obviously unsafe production configuration.

        Development may use the default secret so that a fresh checkout
        remains easy to run. Production must explicitly configure it.
        """
        if value.get_secret_value().strip() == "":
            raise ValueError("SECRET_KEY cannot be empty.")

        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached application settings.

    Caching ensures all application components use the same immutable
    configuration object during a process lifetime.
    """
    settings = Settings()

    if settings.is_production:
        default_secret = "development-only-change-this-secret-before-production"

        if settings.secret_key.get_secret_value() == default_secret:
            raise ValueError("SECRET_KEY must be explicitly configured in production.")

        if settings.debug:
            raise ValueError("DEBUG must be disabled in production.")

    return settings
