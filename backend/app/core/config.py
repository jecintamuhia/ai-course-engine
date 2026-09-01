"""Application configuration and environment management."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


Environment = Literal["development", "testing", "staging", "production"]


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
        "postgresql+asyncpg://course_engine:"
        "course_engine@localhost:5432/course_engine"
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
        default=SecretStr(
            "development-only-change-this-secret-before-production"
        )
    )

    allowed_hosts: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1"]
    )

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
                f"Invalid LOG_LEVEL={value!r}. "
                f"Expected one of: {sorted(allowed)}"
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
        default_secret = (
            "development-only-change-this-secret-before-production"
        )

        if settings.secret_key.get_secret_value() == default_secret:
            raise ValueError(
                "SECRET_KEY must be explicitly configured in production."
            )

        if settings.debug:
            raise ValueError("DEBUG must be disabled in production.")

    return settings