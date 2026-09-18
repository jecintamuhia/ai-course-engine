"""Unit tests for the ingestion pipeline state machine."""

from __future__ import annotations

import pytest
from app.core.exceptions import InvalidStateTransition
from app.models.ingestion_job import IngestionState
from app.services.ingestion.state_machine import (
    get_allowed_transitions,
    validate_transition,
)


def test_full_pipeline_path_is_valid() -> None:
    path = [
        IngestionState.PENDING,
        IngestionState.VALIDATING,
        IngestionState.EXTRACTING,
        IngestionState.NORMALIZING,
        IngestionState.STRUCTURING,
        IngestionState.CHUNKING,
        IngestionState.ANALYZING,
        IngestionState.COMPLETED,
    ]

    for current, target in zip(path[:-1], path[1:], strict=True):
        validate_transition(current, target)


def test_skipping_stages_is_rejected() -> None:
    with pytest.raises(InvalidStateTransition):
        validate_transition(IngestionState.PENDING, IngestionState.CHUNKING)


def test_transition_from_terminal_state_is_rejected() -> None:
    with pytest.raises(InvalidStateTransition):
        validate_transition(
            IngestionState.COMPLETED, IngestionState.EXTRACTING
        )


def test_retry_path_from_failed_to_pending_is_valid() -> None:
    validate_transition(IngestionState.FAILED, IngestionState.PENDING)


def test_resurrecting_cancelled_job_is_rejected() -> None:
    with pytest.raises(InvalidStateTransition):
        validate_transition(
            IngestionState.CANCELLED, IngestionState.PENDING
        )


def test_mid_pipeline_cancellation_is_valid() -> None:
    validate_transition(IngestionState.EXTRACTING, IngestionState.CANCELLED)


def test_completed_and_cancelled_have_no_outgoing_transitions() -> None:
    assert get_allowed_transitions(IngestionState.COMPLETED) == set()
    assert get_allowed_transitions(IngestionState.CANCELLED) == set()


def test_invalid_transition_error_includes_allowed_states() -> None:
    with pytest.raises(InvalidStateTransition) as exc_info:
        validate_transition(IngestionState.PENDING, IngestionState.FAILED)

    assert "allowed_states" in exc_info.value.details
    assert "validating" in exc_info.value.details["allowed_states"]