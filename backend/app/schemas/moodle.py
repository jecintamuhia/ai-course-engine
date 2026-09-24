"""Pydantic schemas for Moodle integration resources."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.models.course import CourseStatus
from pydantic import BaseModel, Field


class MoodleConnectionStatus(BaseModel):
    """Connection status of the configured Moodle instance."""

    configured: bool
    moodle_url: str | None
    connected: bool = False
    site_name: str | None = None
    site_url: str | None = None
    api_version: str | None = None
    username: str | None = None
    error: str | None = None


class MoodleConnectionCheck(BaseModel):
    """Extended Moodle health check with a read-only capability probe."""

    configured: bool
    moodle_url: str | None
    connected: bool = False
    site_name: str | None = None
    site_url: str | None = None
    api_version: str | None = None
    username: str | None = None
    default_category_id: int | None = None
    default_category_found: bool | None = None
    categories_visible: int = 0
    error: str | None = None


class MoodlePreflightIssue(BaseModel):
    """A single structured Moodle readiness problem."""

    kind: str
    message: str
    admin_action: str
    ws_function: str | None = None
    capability: str | None = None
    recoverable: bool = True


class MoodlePreflightCheck(BaseModel):
    """
    One named item in the Moodle readiness checklist.

    ``status`` is ``ok``, ``warning``, or ``error``. ``verification``
    states how the outcome was established: ``direct`` (probed against
    Moodle or application state), ``inferred`` (derived from an indirect
    observation — the Moodle Web Services API does not expose capability
    checks, so capabilities are inferred from the declared functions), or
    ``not_verifiable`` (cannot be confirmed through the API).
    """

    label: str
    status: str
    detail: str
    verification: str
    ws_function: str | None = None
    capability: str | None = None


class MoodlePreflightResponse(BaseModel):
    """
    Structured Moodle readiness report for publishing.

    ``ready`` is false unless the token authenticates, every required
    web service function is exposed with its capability, and the target
    course category exists. ``checks`` is the per-item checklist with an
    honest ``verification`` method per item. When not ready,
    ``blocking_issues`` (same list as ``issues``) explains each problem
    with the function/capability required and the action a Moodle
    administrator must take. Running this check never writes to Moodle.
    """

    ready: bool
    configured: bool
    moodle_url: str | None = None
    site_name: str | None = None
    site_url: str | None = None
    api_version: str | None = None
    username: str | None = None
    functions_available: list[str] = Field(default_factory=list)
    functions_required: list[str] = Field(default_factory=list)
    capabilities_required: list[str] = Field(default_factory=list)
    category_id: int | None = None
    category_found: bool | None = None
    checks: list[MoodlePreflightCheck] = Field(default_factory=list)
    issues: list[MoodlePreflightIssue] = Field(default_factory=list)
    blocking_issues: list[MoodlePreflightIssue] = Field(default_factory=list)
    checked_at: datetime


class MoodlePublishRequest(BaseModel):
    """
    Request to publish a curriculum to Moodle.

    ``idnumber`` overrides the generated Moodle course idnumber used for
    idempotent find-or-create. Defaults to ``ai-ece-<curriculum_id>``.
    ``fullname``/``shortname`` override the coursetitle / idnumber-derived
    Moodle course names. ``category_id`` overrides the configured Moodle
    course category (validated against the live site before creation).
    """

    idnumber: str | None = Field(default=None, max_length=100)
    fullname: str | None = Field(
        default=None,
        max_length=1334,
        description="Override the Moodle course full name.",
    )
    shortname: str | None = Field(
        default=None,
        max_length=255,
        description="Override the Moodle course short name.",
    )
    category_id: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Override the Moodle course category id (validated on the "
            "live site before creation)."
        ),
    )


class MoodleCourseRead(BaseModel):
    """A course record published to Moodle."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    curriculum_id: uuid.UUID
    title: str
    fullname: str
    shortname: str
    idnumber: str
    moodle_course_id: int | None
    moodle_url: str | None
    status: CourseStatus
    sections_published: int
    resources_published: int
    last_sync_at: datetime | None
    sync_error: str | None
    created_at: datetime
    updated_at: datetime


class MoodleCourseListResponse(BaseModel):
    """List of published course records."""

    courses: list[MoodleCourseRead]


class MoodlePublishResponse(BaseModel):
    """Result of publishing a curriculum to Moodle."""

    course_id: str
    moodle_course_id: int
    course_fullname: str
    course_shortname: str
    course_url: str
    idnumber: str
    created: bool
    sections_published: int
    resources_published: int
    verified: bool


class MoodleVerifyResponse(BaseModel):
    """Result of verifying a published Moodle course."""

    course_id: str
    moodle_course_id: int | None
    found: bool
    sections_found: int
    modules_found: int
    section_names: list[str] = Field(default_factory=list)
    course_url: str | None = None
    error: str | None = None
