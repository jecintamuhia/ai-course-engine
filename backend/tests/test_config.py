"""Configuration tests."""

from app.core.config import Settings


def test_default_configuration() -> None:
    """Development configuration should have sensible defaults."""
    settings = Settings()

    assert settings.app_name == "AI Course Engine"
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.database_pool_size > 0


def test_upload_size_conversion() -> None:
    """Upload size should correctly convert MB to bytes."""
    settings = Settings(max_upload_size_mb=10)

    assert settings.max_upload_size_bytes == 10 * 1024 * 1024