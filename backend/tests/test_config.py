"""Configuration tests."""

import pytest
from app.core.config import Settings
from pydantic import SecretStr, ValidationError


def _production_settings(**overrides: object) -> Settings:
    """Build a valid production configuration, with optional overrides."""
    values: dict[str, object] = {
        "environment": "production",
        "debug": False,
        "secret_key": SecretStr("a" * 48),
        "database_url": "postgresql+asyncpg://user:pass@db:5432/course_engine",
        "frontend_url": "https://skillupactionafrica.co.ke",
        "cors_origins": [
            "https://skillupactionafrica.co.ke",
            "https://www.skillupactionafrica.co.ke",
        ],
        "upload_dir": "/app/storage/documents",
        "ai_provider": "openrouter",
        "openrouter_api_key": SecretStr("test-openrouter-key"),
        "openrouter_model": "test/model",
        "moodle_url": "https://elearning.skillupafrica.co.ke",
        "moodle_token": SecretStr("test-moodle-token"),
    }
    values.update(overrides)
    return Settings(**values)


def test_default_configuration() -> None:
    """Development configuration should have sensible defaults."""
    settings = Settings()

    assert settings.app_name == "SkillUp Action Africa"
    assert settings.app_tagline == "Course Intelligence Workspace"
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.database_pool_size > 0


def test_upload_size_conversion() -> None:
    """Upload size should correctly convert MB to bytes."""
    settings = Settings(max_upload_size_mb=10)

    assert settings.max_upload_size_bytes == 10 * 1024 * 1024


def test_postgres_scheme_is_normalised_for_asyncpg() -> None:
    """Railway's postgres:// URL must select the asyncpg driver."""
    settings = Settings(
        database_url="postgres://user:pass@db.internal:5432/railway"
    )

    assert settings.database_url == (
        "postgresql+asyncpg://user:pass@db.internal:5432/railway"
    )


def test_postgresql_scheme_is_normalised_for_asyncpg() -> None:
    """Railway's postgresql:// URL must select the asyncpg driver."""
    settings = Settings(
        database_url="postgresql://user:pass@db.internal:5432/railway"
    )

    assert settings.database_url == (
        "postgresql+asyncpg://user:pass@db.internal:5432/railway"
    )


def test_explicit_asyncpg_url_is_unchanged() -> None:
    """An already-correct URL must not be rewritten twice."""
    url = "postgresql+asyncpg://user:pass@localhost:5432/course_engine"

    settings = Settings(database_url=url)

    assert settings.database_url == url


def test_neon_libpq_tls_query_is_translated_for_asyncpg() -> None:
    """Neon's sslmode/channel_binding query must reach asyncpg as ssl."""
    settings = Settings(
        database_url=(
            "postgresql://user:pass@ep-example.neon.tech/neondb"
            "?sslmode=require&channel_binding=require"
        )
    )

    assert settings.database_url == (
        "postgresql+asyncpg://user:pass@ep-example.neon.tech/neondb"
        "?ssl=require"
    )


def test_asyncpg_url_keeps_an_explicit_ssl_query() -> None:
    """An explicit asyncpg ssl parameter wins over a duplicate sslmode."""
    settings = Settings(
        database_url=(
            "postgresql+asyncpg://user:pass@db.example.com/neondb"
            "?sslmode=require&ssl=verify-full"
        )
    )

    assert settings.database_url.endswith("?ssl=verify-full")


def test_valid_production_configuration_is_accepted() -> None:
    settings = _production_settings()

    assert settings.is_production is True
    assert settings.google_oauth_enabled is False


def test_production_rejects_default_secret_key() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        _production_settings(
            secret_key=SecretStr(
                "development-only-change-this-secret-before-production"
            )
        )


def test_production_rejects_short_secret_key() -> None:
    with pytest.raises(ValidationError, match="at least 32 characters"):
        _production_settings(secret_key=SecretStr("too-short"))


def test_production_rejects_debug() -> None:
    with pytest.raises(ValidationError, match="DEBUG"):
        _production_settings(debug=True)


def test_production_rejects_insecure_frontend_url() -> None:
    with pytest.raises(ValidationError, match="FRONTEND_URL"):
        _production_settings(frontend_url="http://skillupactionafrica.co.ke")


def test_production_rejects_localhost_cors_origin() -> None:
    with pytest.raises(ValidationError, match="CORS origin"):
        _production_settings(cors_origins=["https://localhost:8000"])


def test_production_rejects_placeholder_ai_key() -> None:
    with pytest.raises(ValidationError, match="OPENROUTER_API_KEY"):
        _production_settings(
            openrouter_api_key=SecretStr("CHANGE_ME_USE_OPENROUTER_KEY")
        )


def test_production_rejects_partial_google_oauth_configuration() -> None:
    with pytest.raises(ValidationError, match="GOOGLE_OAUTH_CLIENT_ID"):
        _production_settings(google_oauth_client_id=SecretStr("client-id"))


def test_production_requires_https_google_callback_when_enabled() -> None:
    with pytest.raises(ValidationError, match="GOOGLE_OAUTH_REDIRECT_URI"):
        _production_settings(
            google_oauth_client_id=SecretStr("client-id"),
            google_oauth_client_secret=SecretStr("client-secret"),
            google_oauth_redirect_uri=(
                "http://api.skillupactionafrica.co.ke"
                "/api/v1/auth/google/callback"
            ),
        )


def test_production_accepts_disabled_google_oauth_with_configured_callback() -> None:
    settings = _production_settings(
        google_oauth_redirect_uri=(
            "https://api.skillupactionafrica.co.ke"
            "/api/v1/auth/google/callback"
        ),
    )

    assert settings.google_oauth_enabled is False
    assert settings.effective_google_redirect_uri.endswith(
        "/api/v1/auth/google/callback"
    )


def test_production_allows_moodle_to_be_unconfigured() -> None:
    settings = _production_settings(moodle_url=None, moodle_token=SecretStr(""))

    assert settings.moodle_url is None


def test_production_rejects_partial_moodle_configuration() -> None:
    with pytest.raises(ValidationError, match="MOODLE_URL and MOODLE_TOKEN"):
        _production_settings(moodle_url=None)


def test_production_rejects_placeholder_moodle_token() -> None:
    with pytest.raises(ValidationError, match="MOODLE_TOKEN"):
        _production_settings(
            moodle_token=SecretStr("CHANGE_ME_MOODLE_WEB_SERVICE_TOKEN")
        )


def test_google_frontend_redirect_must_be_same_origin() -> None:
    with pytest.raises(ValidationError, match="GOOGLE_OAUTH_FRONTEND_REDIRECT"):
        Settings(google_oauth_frontend_redirect="https://evil.example/login")


def test_jwt_algorithm_is_restricted_to_hmac() -> None:
    with pytest.raises(ValidationError, match="JWT_ALGORITHM"):
        Settings(jwt_algorithm="none")
