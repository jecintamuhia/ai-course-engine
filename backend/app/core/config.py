from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.

    Environment variables take precedence over values defined in .env.
    """

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
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    api_v1_prefix: str = "/api/v1"

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    database_url: str = Field(
        default="postgresql+asyncpg://course_engine:course_engine@localhost:5432/course_engine",
        description="Async SQLAlchemy PostgreSQL connection URL.",
    )

    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout: int = 30
    database_pool_recycle: int = 1800

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------

    redis_url: str = "redis://localhost:6379/0"

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------

    secret_key: SecretStr = SecretStr(
        "development-only-change-this-secret-before-production"
    )

    request_id_header: str = "X-Request-ID"

    # ------------------------------------------------------------------
    # File storage
    # ------------------------------------------------------------------

    storage_path: Path = Path("./storage")

    max_upload_size_mb: int = 100

    allowed_upload_mime_types: tuple[str, ...] = (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    # ------------------------------------------------------------------
    # External services
    # ------------------------------------------------------------------

    ai_provider: str = "none"
    ai_model: str = "unset"

    ai_api_key: SecretStr | None = None

    moodle_base_url: str | None = None
    moodle_api_token: SecretStr | None = None

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        normalized = value.lower().strip()

        allowed = {
            "development",
            "testing",
            "staging",
            "production",
        }

        if normalized not in allowed:
            raise ValueError(
                f"environment must be one of: {', '.join(sorted(allowed))}"
            )

        return normalized

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper().strip()

        allowed = {
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        }

        if normalized not in allowed:
            raise ValueError(
                f"log_level must be one of: {', '.join(sorted(allowed))}"
            )

        return normalized

    @field_validator("database_pool_size")
    @classmethod
    def validate_pool_size(cls, value: int) -> int:
        if value < 1:
            raise ValueError("database_pool_size must be greater than zero")
        return value

    @field_validator("database_max_overflow")
    @classmethod
    def validate_max_overflow(cls, value: int) -> int:
        if value < 0:
            raise ValueError("database_max_overflow cannot be negative")
        return value

    @field_validator("max_upload_size_mb")
    @classmethod
    def validate_upload_size(cls, value: int) -> int:
        if value < 1:
            raise ValueError("max_upload_size_mb must be greater than zero")
        return value

    def validate_production_security(self) -> None:
        """
        Prevent development secrets from accidentally being used in production.
        """

        if self.environment != "production":
            return

        if self.secret_key.get_secret_value().startswith("development-only"):
            raise ValueError(
                "A production SECRET_KEY must be explicitly configured."
            )

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """
    Return the cached application settings instance.
    """

    settings = Settings()
    settings.validate_production_security()

    settings.storage_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    return settings