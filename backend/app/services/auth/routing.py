"""Post-login routing policy: map an authenticated role to a destination.

This module is the single source of truth for the
``role -> destination`` decision so the API, the SPA, and their tests
cannot drift apart. Authoring roles stay in the SkillUp Action Africa
course intelligence workspace; learning roles land on the learner
portal served by this application, which owns their progress,
assessments and certificates. The Moodle site remains the place where
course content is delivered, and the portal links out to it. No course
id is ever embedded here.
"""

from __future__ import annotations

from app.core.config import Settings
from app.models.user import UserRole

#: Same-origin route that renders the authoring workspace.
WORKSPACE_DESTINATION = "/dashboard"

#: Same-origin route that renders the learner portal.
LEARNER_DESTINATION = "/learn"

#: Fallback used only when no learner destination is configured.
SIGN_IN_DESTINATION = "/login"

#: Roles allowed to use the authoring workspace.
STAFF_ROLES: frozenset[UserRole] = frozenset(
    {UserRole.ADMIN, UserRole.LECTURER}
)

#: Roles that use the learner portal.
LEARNER_ROLES: frozenset[UserRole] = frozenset(
    {UserRole.STUDENT, UserRole.TEACHER}
)


def is_staff(role: UserRole) -> bool:
    """Return whether ``role`` may use the authoring workspace."""
    return role in STAFF_ROLES


def is_learner(role: UserRole) -> bool:
    """Return whether ``role`` uses the learner surface."""
    return role in LEARNER_ROLES


def post_login_destination(role: UserRole, settings: Settings) -> str:
    """
    Return where a freshly authenticated user should be sent.

    Staff roles receive a same-origin workspace path. Learning roles
    receive the configured learner destination — a same-origin path
    (``/learn`` by default) that keeps them in the learner portal of
    this application, or an absolute URL when a deployment prefers to
    hand them to another system. If nothing usable is configured the
    sign-in path is returned, so the result is always a usable
    destination.
    """
    if is_staff(role):
        return WORKSPACE_DESTINATION

    destination = (settings.learner_destination or "").strip()
    if destination:
        return destination

    return SIGN_IN_DESTINATION
