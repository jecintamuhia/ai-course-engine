"""Unit tests for the central post-login routing policy."""

from __future__ import annotations

from app.core.config import Settings
from app.models.user import UserRole
from app.services.auth.routing import (
    LEARNER_DESTINATION,
    SIGN_IN_DESTINATION,
    WORKSPACE_DESTINATION,
    is_learner,
    is_staff,
    post_login_destination,
)


def test_staff_roles_are_admin_and_lecturer() -> None:
    assert is_staff(UserRole.ADMIN)
    assert is_staff(UserRole.LECTURER)


def test_learning_roles_are_not_staff() -> None:
    assert not is_staff(UserRole.STUDENT)
    assert not is_staff(UserRole.TEACHER)


def test_learning_roles_are_learners() -> None:
    assert is_learner(UserRole.STUDENT)
    assert is_learner(UserRole.TEACHER)


def test_staff_roles_are_not_learners() -> None:
    assert not is_learner(UserRole.ADMIN)
    assert not is_learner(UserRole.LECTURER)


def test_staff_destination_is_the_workspace() -> None:
    settings = Settings(moodle_url="https://moodle.example.com")

    assert post_login_destination(UserRole.ADMIN, settings) == WORKSPACE_DESTINATION
    assert post_login_destination(UserRole.LECTURER, settings) == WORKSPACE_DESTINATION


def test_learning_roles_are_sent_to_the_learner_portal() -> None:
    settings = Settings(moodle_url="https://moodle.example.com/")

    # The learner portal lives in this application, so the configured
    # Moodle base URL is irrelevant to the decision.
    assert post_login_destination(UserRole.STUDENT, settings) == LEARNER_DESTINATION
    assert post_login_destination(UserRole.TEACHER, settings) == LEARNER_DESTINATION


def test_learner_destination_is_configurable() -> None:
    settings = Settings(learner_destination="/portal")

    assert post_login_destination(UserRole.STUDENT, settings) == "/portal"


def test_learner_destination_may_be_an_absolute_url() -> None:
    settings = Settings(learner_destination="https://learn.example.com/")

    assert (
        post_login_destination(UserRole.STUDENT, settings)
        == "https://learn.example.com/"
    )


def test_learning_roles_fall_back_when_no_destination_is_configured() -> None:
    settings = Settings(learner_destination="   ")

    assert post_login_destination(UserRole.STUDENT, settings) == SIGN_IN_DESTINATION
    assert post_login_destination(UserRole.TEACHER, settings) == SIGN_IN_DESTINATION


def test_destination_never_embeds_a_course_id() -> None:
    settings = Settings(moodle_url="https://elearning.skillupafrica.co.ke")

    destination = post_login_destination(UserRole.STUDENT, settings)

    assert "course" not in destination
    assert "id=" not in destination
