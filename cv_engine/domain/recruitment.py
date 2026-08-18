from __future__ import annotations

from .models import ApplicationStatus

ALLOWED_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.SAVED: {
        ApplicationStatus.PREPARING,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.CLOSED,
    },
    ApplicationStatus.PREPARING: {
        ApplicationStatus.READY,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.CLOSED,
    },
    ApplicationStatus.READY: {
        ApplicationStatus.PREPARING,
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
