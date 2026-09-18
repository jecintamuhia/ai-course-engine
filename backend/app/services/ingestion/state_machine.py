"""Ingestion pipeline state machine: valid states and transitions."""

from __future__ import annotations

from app.core.exceptions import InvalidStateTransition
from app.models.ingestion_job import IngestionState

# KNOWLEDGE_BUILDING onward (Batches 10-14: provenance, dependency
# graph, curriculum engine/planner, review/approval, Moodle publishing)
# are not implemented yet, so ANALYZING allows COMPLETED directly. Once
# KNOWLEDGE_BUILDING lands, this narrows to
# {IngestionState.KNOWLEDGE_BUILDING, IngestionState.FAILED, IngestionState.CANCELLED}.
ALLOWED_TRANSITIONS: dict[IngestionState, set[IngestionState]] = {
    IngestionState.PENDING: {
        IngestionState.VALIDATING,
        IngestionState.CANCELLED,
    },
    IngestionState.VALIDATING: {
        IngestionState.EXTRACTING,
        IngestionState.FAILED,
        IngestionState.CANCELLED,
    },
    IngestionState.EXTRACTING: {
        IngestionState.NORMALIZING,
        IngestionState.FAILED,
        IngestionState.CANCELLED,
    },
    IngestionState.NORMALIZING: {
        IngestionState.STRUCTURING,
        IngestionState.FAILED,
        IngestionState.CANCELLED,
    },
    IngestionState.STRUCTURING: {
        IngestionState.CHUNKING,
        IngestionState.FAILED,
        IngestionState.CANCELLED,
    },
    IngestionState.CHUNKING: {
        IngestionState.ANALYZING,
        IngestionState.FAILED,
        IngestionState.CANCELLED,
    },
    IngestionState.ANALYZING: {
        IngestionState.KNOWLEDGE_BUILDING,
        IngestionState.COMPLETED,
        IngestionState.FAILED,
        IngestionState.CANCELLED,
    },
    IngestionState.KNOWLEDGE_BUILDING: {
        IngestionState.PLANNING,
        IngestionState.FAILED,
        IngestionState.CANCELLED,
    },
    IngestionState.PLANNING: {
        IngestionState.VALIDATING_OUTPUT,
        IngestionState.FAILED,
        IngestionState.CANCELLED,
    },
    IngestionState.VALIDATING_OUTPUT: {
        IngestionState.AWAITING_REVIEW,
        IngestionState.FAILED,
        IngestionState.CANCELLED,
    },
    IngestionState.AWAITING_REVIEW: {
        IngestionState.APPROVED,
        IngestionState.FAILED,
        IngestionState.CANCELLED,
    },
    IngestionState.APPROVED: {
        IngestionState.PUBLISHING,
        IngestionState.CANCELLED,
    },
    IngestionState.PUBLISHING: {
        IngestionState.COMPLETED,
        IngestionState.FAILED,
        IngestionState.CANCELLED,
    },
    IngestionState.COMPLETED: set(),
    IngestionState.FAILED: {IngestionState.PENDING},
    IngestionState.CANCELLED: set(),
}


def get_allowed_transitions(current: IngestionState) -> set[IngestionState]:
    """Return the set of states reachable from the current state."""
    return ALLOWED_TRANSITIONS.get(current, set())


def validate_transition(
    current: IngestionState, target: IngestionState
) -> None:
    """
    Validate a proposed state transition.

    Raises InvalidStateTransition if the transition is not permitted from
    the current state.
    """
    allowed = get_allowed_transitions(current)

    if target not in allowed:
        raise InvalidStateTransition(
            f"Cannot transition from {current.value!r} to "
            f"{target.value!r}.",
            details={
                "current_state": current.value,
                "requested_state": target.value,
                "allowed_states": sorted(state.value for state in allowed),
            },
        )