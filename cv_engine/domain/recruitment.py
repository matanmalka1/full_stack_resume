from __future__ import annotations

from .models import ApplicationStatus

ALLOWED_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.SAVED: {
        ApplicationStatus.APPLIED,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.CLOSED,
    },
    ApplicationStatus.APPLIED: {
        ApplicationStatus.RECRUITER_SCREEN,
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.CLOSED,
    },
    ApplicationStatus.RECRUITER_SCREEN: {
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.ASSIGNMENT,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.CLOSED,
    },
    ApplicationStatus.INTERVIEW: {
        ApplicationStatus.ASSIGNMENT,
        ApplicationStatus.FINAL_STAGE,
        ApplicationStatus.OFFER,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.CLOSED,
    },
    ApplicationStatus.ASSIGNMENT: {
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.FINAL_STAGE,
        ApplicationStatus.OFFER,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.CLOSED,
    },
    ApplicationStatus.FINAL_STAGE: {
        ApplicationStatus.OFFER,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.CLOSED,
    },
    ApplicationStatus.OFFER: {
        ApplicationStatus.ACCEPTED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.CLOSED,
    },
    ApplicationStatus.ACCEPTED: {ApplicationStatus.CLOSED},
    ApplicationStatus.REJECTED: {ApplicationStatus.CLOSED},
    ApplicationStatus.WITHDRAWN: {ApplicationStatus.CLOSED},
    ApplicationStatus.CLOSED: set(),
}


def transition_allowed(current: ApplicationStatus, target: ApplicationStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def user_transition_targets(current: ApplicationStatus) -> tuple[ApplicationStatus, ...]:
    """Direct status choices a user may make from ``current``.

    ``applied`` belongs to submission even though it is a valid domain transition from
    ``saved``. The query projection uses this function so a Web client can render the
    backend's policy without copying the graph or offering a command the status endpoint
    will refuse.
    """
    allowed = ALLOWED_TRANSITIONS[current] - {ApplicationStatus.APPLIED}
    return tuple(status for status in ApplicationStatus if status in allowed)


def terminal_outcome_after(
    current_outcome: str | None,
    target: ApplicationStatus,
) -> str | None:
    """Project the durable outcome independently from archival ``closed``."""
    if target in {
        ApplicationStatus.ACCEPTED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    }:
        return target.value
    if target is ApplicationStatus.CLOSED:
        return current_outcome
    return None
