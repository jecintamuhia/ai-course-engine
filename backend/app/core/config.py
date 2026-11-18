"""Application configuration and environment management."""

from functools import lru_cache
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit, urlunsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "testing", "staging", "production"]
AIProvider = Literal["openai", "openrouter"]

_DEVELOPMENT_SECRET = "development-only-change-this-secret-before-production"
_MIN_PRODUCTION_SECRET_LENGTH = 32
_PLACEHOLDER_MARKERS = (
    "change_me",
    "replace-this",
    "replace-with",
    "replace_me",
)


def _looks_like_placeholder(value: str) -> bool:
    """Return whether a value is an obvious template placeholder."""
    normalized = value.strip().lower()
    return not normalized or normalized.startswith(_PLACEHOLDER_MARKERS)


def _is_absolute_https_url(value: str) -> bool:
    """Return whether a value is an absolute HTTPS URL."""
    parsed = urlparse(value.strip())
    return parsed.scheme == "https" and bool(parsed.netloc)


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

    app_name: str = "SkillUp Action Africa"
    app_tagline: str = "Course Intelligence Workspace"
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
    # CORS / frontend origin
    # ------------------------------------------------------------------

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:8000"],
        description="Trusted origins for cross-origin API requests.",
    )
    frontend_url: str = ""

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

    # Redis-backed login throttling. The per-email bucket stops password
    # guessing against one account; the per-IP bucket caps distributed
    # attempts from a single source. Both are required when Redis is
    # configured because the API refuses logins if the limiter is down.
    login_rate_limit_enabled: bool = Field(default=True)
    login_rate_limit_email_attempts: int = Field(default=5, ge=1, le=100)
    login_rate_limit_ip_attempts: int = Field(default=30, ge=1, le=100)
    login_rate_limit_window_seconds: int = Field(
        default=300,
        ge=30,
        le=86_400,
    )

    # Only trust X-Forwarded-For when the service is reachable exclusively
    # through a reverse proxy that overwrites/appends the header. When
    # false, the direct socket peer is used so a client cannot choose its
    # own rate-limit bucket by spoofing the header.
    trust_proxy_headers: bool = Field(default=False)

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
    # Learner portal
    # ------------------------------------------------------------------

    learner_destination: str = Field(
        default="/learn",
        description=(
            "Where learner accounts (student/teacher) are sent after "
            "signing in. A same-origin path keeps them in the learner "
            "portal served by this application, where their progress, "
            "assessments and certificates live. An absolute URL hands "
            "them to another system instead."
        ),
    )

    assessment_pass_percent: int = Field(
        default=70,
        ge=1,
        le=100,
        description=(
            "Pass mark for the final assessment. A learner must score at "
            "least this percentage on one attempt AND complete every "
            "approved lesson before a certificate is issued. 70% is the "
            "client-approved default; certificates are never issued "
            "below it."
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
    # Google Gemini via OpenRouter, used for textbook analysis and lesson
    # generation. Deployments can override this with any compatible
    # OpenRouter model id.
    openrouter_model: str = Field(default="google/gemini-2.5-pro")
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
    # Course content generation (lessons, diagrams, activities, practical
    # tasks, knowledge checks, resources)
    # ------------------------------------------------------------------

    # Must be at least the planner's maximum topics per week
    # (max_weekly_workload_minutes / min_topic_allocation_minutes = 1200/60
    # = 20 with the default four-month config). Otherwise planned topics in
    # a dense week are silently dropped by lesson generation and can never
    # receive a lesson, so content-QA (topic_without_lesson is an error) can
    # never pass and the curriculum can never be approved or published.
    content_max_lessons_per_week: int = Field(default=20, ge=1, le=20)
    content_max_tokens: int = Field(default=4000, ge=512, le=32768)
    content_max_knowledge_checks: int = Field(default=3, ge=0, le=10)
    content_max_activities: int = Field(default=2, ge=0, le=10)
    content_max_practical_tasks: int = Field(
        default=1,
        ge=0,
        le=5,
        description=(
            "Practical project briefs generated per lesson. Set 0 to "
            "disable the extra generation pass entirely."
        ),
    )
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

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        """
        Accept the URL schemes managed database providers hand out.

        Railway (and several other providers) expose ``DATABASE_URL`` as
        ``postgres://`` or ``postgresql://``. The application uses the
        asyncpg driver, which SQLAlchemy only selects for an explicit
        ``postgresql+asyncpg://`` URL. Normalising here keeps the
        provider-supplied value usable without hand-editing secrets.
        """
        if not isinstance(value, str):
            return value

        url = value.strip()

        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                url = f"postgresql+asyncpg://{url[len(prefix):]}"
                break

        if not url.startswith("postgresql+asyncpg://"):
            return url

        # Neon hands out libpq-style query parameters. SQLAlchemy passes
        # unknown query values straight to asyncpg, which accepts ``ssl``
        # but rejects ``sslmode`` and ``channel_binding``. Translate the
        # TLS mode so a Neon connection string can be used without editing
        # the secret by hand.
        parsed = urlsplit(url)
        if not parsed.query:
            return url

        query = parse_qsl(parsed.query, keep_blank_values=True)
        has_ssl = any(key.lower() == "ssl" for key, _ in query)
        normalized: list[tuple[str, str]] = []

        for key, query_value in query:
            lowered = key.lower()
            if lowered == "sslmode":
                if not has_ssl:
                    normalized.append(("ssl", query_value))
                    has_ssl = True
                continue
            if lowered == "channel_binding":
                continue
            normalized.append((key, query_value))

        return urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                urlencode(normalized),
                parsed.fragment,
            )
        )

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        """Only allow HMAC algorithms supported by the HS256 secret."""
        normalized = value.strip().upper()
        allowed = {"HS256", "HS384", "HS512"}

        if normalized not in allowed:
            raise ValueError(
                f"Invalid JWT_ALGORITHM={value!r}. Expected one of: {sorted(allowed)}"
            )

        return normalized

    @field_validator("google_oauth_frontend_redirect")
    @classmethod
    def validate_google_frontend_redirect(cls, value: str) -> str:
        """
        Keep the post-OAuth redirect on this application's origin.

        A relative path prevents an attacker-controlled absolute URL from
        turning the OAuth callback into an open redirect.
        """
        normalized = value.strip()

        if not normalized:
            return "/login"

        if not normalized.startswith("/") or normalized.startswith("//"):
            raise ValueError(
                "GOOGLE_OAUTH_FRONTEND_REDIRECT must be a same-origin path "
                "such as /login."
            )

        return normalized

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

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: list[str]) -> list[str]:
        """Reject wildcard or insecure origins in production."""
        if not value:
            raise ValueError("CORS_ORIGINS cannot be empty.")

        for origin in value:
            if origin == "*":
                raise ValueError("CORS_ORIGINS cannot use wildcard '*' in production.")
            if origin.startswith("http://") and not (
                "localhost" in origin or "127.0.0.1" in origin
            ):
                raise ValueError(
                    f"Insecure CORS origin {origin!r}: only HTTPS origins are "
                    "allowed except for localhost development."
                )

        return value

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: SecretStr) -> SecretStr:
        """Reject an empty signing secret."""
        if value.get_secret_value().strip() == "":
            raise ValueError("SECRET_KEY cannot be empty.")

        return value

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """
        Fail fast on unsafe production configuration.

        Development and testing may keep convenient defaults. Production
        must use an explicit strong secret, HTTPS public URLs, and
        provider settings that are either complete or deliberately
        absent.
        """
        if not self.is_production:
            return self

        secret = self.secret_key.get_secret_value().strip()
        if (
            secret == _DEVELOPMENT_SECRET
            or _looks_like_placeholder(secret)
            or len(secret) < _MIN_PRODUCTION_SECRET_LENGTH
        ):
            raise ValueError(
                "SECRET_KEY must be a random value of at least "
                f"{_MIN_PRODUCTION_SECRET_LENGTH} characters in production."
            )

        if self.debug:
            raise ValueError("DEBUG must be disabled in production.")

        if not self.database_url.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must use the postgresql+asyncpg:// scheme in "
                "production."
            )

        if not _is_absolute_https_url(self.frontend_url):
            raise ValueError(
                "FRONTEND_URL must be an absolute HTTPS URL in production."
            )

        if urlparse(self.frontend_url).hostname in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("FRONTEND_URL must not point at localhost in production.")

        for origin in self.cors_origins:
            if not _is_absolute_https_url(origin):
                raise ValueError(
                    f"CORS origin {origin!r} must be an absolute HTTPS URL in "
                    "production."
                )

            parsed_origin = urlparse(origin)
            if parsed_origin.hostname in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError(
                    f"CORS origin {origin!r} must not point at localhost in "
                    "production."
                )

        if not self.upload_dir.strip():
            raise ValueError("UPLOAD_DIR must be set in production.")

        google_client_id = self.google_oauth_client_id.get_secret_value().strip()
        google_client_secret = (
            self.google_oauth_client_secret.get_secret_value().strip()
        )
        if bool(google_client_id) != bool(google_client_secret):
            raise ValueError(
                "GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET must "
                "be set together."
            )

        google_redirect = self.google_oauth_redirect_uri.strip()
        if google_redirect and not _is_absolute_https_url(google_redirect):
            raise ValueError(
                "GOOGLE_OAUTH_REDIRECT_URI must be an absolute HTTPS URL in "
                "production."
            )

        if self.google_oauth_enabled:
            if not google_redirect:
                raise ValueError(
                    "GOOGLE_OAUTH_REDIRECT_URI is required when Google OAuth "
                    "is enabled."
                )
            if not urlparse(google_redirect).path.endswith(
                "/auth/google/callback"
            ):
                raise ValueError(
                    "GOOGLE_OAUTH_REDIRECT_URI must end with "
                    "/auth/google/callback."
                )

        moodle_url = (self.moodle_url or "").strip()
        moodle_token = self.moodle_token.get_secret_value().strip()
        if bool(moodle_url) != bool(moodle_token):
            raise ValueError(
                "MOODLE_URL and MOODLE_TOKEN must be set together, or both "
                "left empty."
            )

        if moodle_url:
            parsed_moodle = urlparse(moodle_url)
            if (
                parsed_moodle.scheme not in {"http", "https"}
                or not parsed_moodle.netloc
            ):
                raise ValueError("MOODLE_URL must be an absolute HTTP(S) URL.")

        if moodle_token and _looks_like_placeholder(moodle_token):
            raise ValueError("MOODLE_TOKEN is still a placeholder value.")

        if self.ai_provider == "openrouter":
            api_key = self.openrouter_api_key.get_secret_value().strip()
            if not api_key:
                raise ValueError(
                    "OPENROUTER_API_KEY is required when AI_PROVIDER=openrouter."
                )
            if _looks_like_placeholder(api_key):
                raise ValueError("OPENROUTER_API_KEY is still a placeholder value.")
            if _looks_like_placeholder(self.openrouter_model):
                raise ValueError("OPENROUTER_MODEL is still a placeholder value.")
        else:
            api_key = self.openai_api_key.get_secret_value().strip()
            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY is required when AI_PROVIDER=openai."
                )
            if _looks_like_placeholder(api_key):
                raise ValueError("OPENAI_API_KEY is still a placeholder value.")
            if _looks_like_placeholder(self.openai_model):
                raise ValueError("OPENAI_MODEL is still a placeholder value.")

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached application settings.

    Caching ensures all application components use the same immutable
    configuration object during a process lifetime.
    """
    return Settings()
