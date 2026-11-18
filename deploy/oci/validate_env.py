#!/usr/bin/env python3
"""Validate an OCI production environment file without starting the stack.

This is intentionally provider-neutral Python (standard library only) so it
can run on a fresh Ubuntu host before Docker images are pulled.

Usage:
    python3 deploy/oci/validate_env.py [path-to-env-file]

The default path is ``deploy/oci/.env.production`` relative to this script.
Values are never printed, so the command is safe to run in a terminal or CI
log. It exits non-zero when a production requirement is missing or unsafe.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

APP_DOMAIN = "skillupactionafrica.co.ke"
EXPECTED_API_DOMAIN = f"api.{APP_DOMAIN}"
MOODLE_DOMAIN = "skillupafrica.co.ke"

REQUIRED_KEYS = (
    "CADDY_DOMAIN",
    "ACME_EMAIL",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "DATABASE_URL",
    "REDIS_URL",
    "ENVIRONMENT",
    "DEBUG",
    "SECRET_KEY",
    "CORS_ORIGINS",
    "FRONTEND_URL",
    "ALLOWED_HOSTS",
    "GOOGLE_OAUTH_REDIRECT_URI",
    "UPLOAD_DIR",
    "AI_PROVIDER",
    "MOODLE_URL",
    "MOODLE_TOKEN",
    "BACKUP_RETENTION_DAYS",
)

PLACEHOLDER_PREFIXES = (
    "change_me",
    "replace-this",
    "replace-with",
    "replace_me",
)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
URL_SAFE_SECRET_RE = re.compile(r"^[A-Za-z0-9_-]{24,}$")


def parse_env_file(path: Path) -> tuple[dict[str, str], list[str]]:
    """Parse the simple KEY=VALUE format used by this deployment."""
    values: dict[str, str] = {}
    errors: list[str] = []

    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[7:].lstrip()

        if "=" not in line:
            errors.append(f"line {line_number}: expected KEY=VALUE")
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            errors.append(f"line {line_number}: empty key")
            continue

        if key in values:
            errors.append(f"line {line_number}: duplicate key {key}")
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        values[key] = value

    return values, errors


def is_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return not normalized or normalized.startswith(PLACEHOLDER_PREFIXES)


def parse_https_url(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username


def parse_list(value: str, key: str, errors: list[str]) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        errors.append(f"{key} must be a JSON array, e.g. [\"https://...\"]")
        return []

    if not isinstance(parsed, list) or not all(
        isinstance(item, str) and item.strip() for item in parsed
    ):
        errors.append(f"{key} must be a JSON array of non-empty strings")
        return []

    return [item.strip() for item in parsed]


def is_moodle_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    normalized = hostname.lower().rstrip(".")
    return normalized == MOODLE_DOMAIN or normalized.endswith(f".{MOODLE_DOMAIN}")


def main(argv: list[str]) -> int:
    script_dir = Path(__file__).resolve().parent
    env_path = (
        Path(argv[1]).resolve()
        if len(argv) > 1
        else script_dir / ".env.production"
    )

    if not env_path.is_file():
        print(f"ERROR: environment file not found: {env_path}", file=sys.stderr)
        return 1

    values, errors = parse_env_file(env_path)
    warnings: list[str] = []

    def get(key: str) -> str:
        return values.get(key, "").strip()

    for key in REQUIRED_KEYS:
        if not get(key):
            errors.append(f"{key} is required")

    for key, value in values.items():
        if value.strip() and is_placeholder(value):
            errors.append(f"{key} is still a placeholder")

    if get("ENVIRONMENT").lower() != "production":
        errors.append("ENVIRONMENT must be production")

    if get("DEBUG").lower() not in {"false", "0", "no"}:
        errors.append("DEBUG must be false in production")

    secret = get("SECRET_KEY")
    if secret == "development-only-change-this-secret-before-production":
        errors.append("SECRET_KEY must not use the development default")
    if secret and len(secret) < 32:
        errors.append("SECRET_KEY must contain at least 32 characters")

    caddy_domain = get("CADDY_DOMAIN").lower().rstrip(".")
    if caddy_domain:
        if "/" in caddy_domain or ":" in caddy_domain:
            errors.append(
                "CADDY_DOMAIN must be a hostname without a scheme, port, or path"
            )
        if is_moodle_host(caddy_domain):
            errors.append(
                "CADDY_DOMAIN points at the Moodle domain; use "
                f"{EXPECTED_API_DOMAIN}, not a {MOODLE_DOMAIN} host"
            )
        if caddy_domain != EXPECTED_API_DOMAIN:
            warnings.append(
                f"CADDY_DOMAIN is not the planned API host {EXPECTED_API_DOMAIN}"
            )

    acme_email = get("ACME_EMAIL")
    if acme_email and not EMAIL_RE.match(acme_email):
        errors.append("ACME_EMAIL must be a valid email address")

    postgres_password = get("POSTGRES_PASSWORD")
    if postgres_password and not URL_SAFE_SECRET_RE.match(postgres_password):
        errors.append(
            "POSTGRES_PASSWORD must be at least 24 URL-safe characters; "
            "prefer `openssl rand -hex 32`"
        )

    database_url = get("DATABASE_URL")
    if database_url:
        parsed_database = urlsplit(database_url)
        if parsed_database.scheme != "postgresql+asyncpg":
            errors.append("DATABASE_URL must use postgresql+asyncpg://")
        if parsed_database.hostname != "postgres":
            errors.append("DATABASE_URL must target the Compose host `postgres`")
        if unquote(parsed_database.username or "") != get("POSTGRES_USER"):
            errors.append("DATABASE_URL username must match POSTGRES_USER")
        if unquote(parsed_database.password or "") != postgres_password:
            errors.append("DATABASE_URL password must match POSTGRES_PASSWORD")
        if parsed_database.path.lstrip("/") != get("POSTGRES_DB"):
            errors.append("DATABASE_URL database must match POSTGRES_DB")

    redis_url = get("REDIS_URL")
    if redis_url:
        parsed_redis = urlsplit(redis_url)
        if parsed_redis.scheme != "redis":
            errors.append("REDIS_URL must use redis://")
        if parsed_redis.hostname in {None, "localhost", "127.0.0.1"}:
            errors.append("REDIS_URL must target the Compose Redis service")

    frontend_url = get("FRONTEND_URL")
    if frontend_url:
        if not parse_https_url(frontend_url):
            errors.append("FRONTEND_URL must be an absolute HTTPS URL")
        frontend_host = urlsplit(frontend_url).hostname
        if is_moodle_host(frontend_host):
            errors.append(
                "FRONTEND_URL points at the Moodle domain; use "
                f"https://{APP_DOMAIN}"
            )
        if frontend_host not in {APP_DOMAIN, f"www.{APP_DOMAIN}"}:
            warnings.append(
                f"FRONTEND_URL is not the planned host {APP_DOMAIN}"
            )

    cors_origins = parse_list(get("CORS_ORIGINS"), "CORS_ORIGINS", errors)
    for origin in cors_origins:
        if origin == "*":
            errors.append("CORS_ORIGINS must not use a wildcard")
            continue
        if not parse_https_url(origin):
            errors.append(f"CORS origin {origin!r} must be an absolute HTTPS URL")
            continue
        parsed_origin = urlsplit(origin)
        if parsed_origin.hostname in {"localhost", "127.0.0.1", "::1"}:
            errors.append(f"CORS origin {origin!r} must not point at localhost")
        if parsed_origin.path not in {"", "/"}:
            errors.append(f"CORS origin {origin!r} must not include a path")

    frontend_origin = ""
    if frontend_url:
        parsed_frontend = urlsplit(frontend_url)
        frontend_origin = f"{parsed_frontend.scheme}://{parsed_frontend.netloc}"
        if frontend_origin not in cors_origins:
            errors.append(
                "CORS_ORIGINS must include the FRONTEND_URL origin "
                f"{frontend_origin}"
            )

    allowed_hosts = parse_list(get("ALLOWED_HOSTS"), "ALLOWED_HOSTS", errors)
    if caddy_domain and caddy_domain not in {
        host.lower().rstrip(".") for host in allowed_hosts
    }:
        warnings.append("ALLOWED_HOSTS does not include CADDY_DOMAIN")

    google_redirect = get("GOOGLE_OAUTH_REDIRECT_URI")
    expected_google_redirect = (
        f"https://{caddy_domain or EXPECTED_API_DOMAIN}"
        "/api/v1/auth/google/callback"
    )
    if google_redirect and google_redirect != expected_google_redirect:
        errors.append(
            "GOOGLE_OAUTH_REDIRECT_URI must exactly equal "
            f"{expected_google_redirect}"
        )

    google_client_id = get("GOOGLE_OAUTH_CLIENT_ID")
    google_client_secret = get("GOOGLE_OAUTH_CLIENT_SECRET")
    if bool(google_client_id) != bool(google_client_secret):
        errors.append(
            "GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET must be "
            "set together"
        )
    elif not google_client_id:
        warnings.append(
            "Google OAuth is disabled because client credentials are empty; "
            "the callback URI is prepared for future approval"
        )

    upload_dir = get("UPLOAD_DIR")
    if upload_dir and not upload_dir.startswith("/"):
        errors.append("UPLOAD_DIR must be an absolute container path")

    if get("RUN_INGESTION_WORKER").lower() not in {"false", "0", "no"}:
        errors.append("RUN_INGESTION_WORKER must be false for the OCI worker split")

    provider = get("AI_PROVIDER").lower()
    if provider == "openrouter":
        for key in ("OPENROUTER_API_KEY", "OPENROUTER_MODEL"):
            if not get(key) or is_placeholder(get(key)):
                errors.append(f"{key} is required for AI_PROVIDER=openrouter")
    elif provider == "openai":
        for key in ("OPENAI_API_KEY", "OPENAI_MODEL"):
            if not get(key) or is_placeholder(get(key)):
                errors.append(f"{key} is required for AI_PROVIDER=openai")
    elif provider:
        errors.append("AI_PROVIDER must be `openrouter` or `openai`")

    moodle_url = get("MOODLE_URL")
    if moodle_url:
        parsed_moodle = urlsplit(moodle_url)
        if parsed_moodle.scheme not in {"http", "https"} or not parsed_moodle.netloc:
            errors.append("MOODLE_URL must be an absolute HTTP(S) URL")
        if not is_moodle_host(parsed_moodle.hostname):
            warnings.append(
                "MOODLE_URL is not on the known Moodle domain "
                f"{MOODLE_DOMAIN}"
            )
        if parsed_moodle.hostname and (
            parsed_moodle.hostname == APP_DOMAIN
            or parsed_moodle.hostname.endswith(f".{APP_DOMAIN}")
        ):
            errors.append(
                "MOODLE_URL points at the application domain, not the "
                "existing Moodle site"
            )

    if get("LOG_JSON").lower() not in {"true", "1", "yes"}:
        warnings.append("LOG_JSON is recommended in production")

    if get("APP_IMAGE_TAG") in {"", "latest"}:
        warnings.append(
            "APP_IMAGE_TAG is latest; pin a version for repeatable deploys"
        )

    try:
        retention_days = int(get("BACKUP_RETENTION_DAYS"))
    except ValueError:
        errors.append("BACKUP_RETENTION_DAYS must be an integer")
    else:
        if retention_days < 1:
            errors.append("BACKUP_RETENTION_DAYS must be at least 1")

    if os.name == "posix":
        mode = env_path.stat().st_mode & 0o777
        if mode & 0o077:
            errors.append(
                f"{env_path.name} must not be readable by group or others; "
                "run chmod 600"
            )

    if errors:
        print("Environment validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"  - {warning}")

    print(f"OK: {env_path} passed production checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
