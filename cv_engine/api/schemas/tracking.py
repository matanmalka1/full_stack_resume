"""Recruitment tracking over HTTP: status, corrections, submissions, next action.

`applied` is absent from `TransitionStatusRequest` deliberately. It is
submission-owned (state-and-use-cases.md 18): it is reached by recording a
submission, never by asking for it, and the application layer refuses it as a
`409`. Naming the closed set here refuses it as a `422` with a field name
instead, before a command is built - the same reason the classification
overrides are typed rather than flattened to `str`.

Actor and client are not accepted from the wire. They are provenance, not
input: a request arriving at this API came from the Web client by definition,
and letting a caller name its own client would let it write a false audit
trail.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from ...domain.contracts.recruitment import ApplicationStatus
from .health import HttpSchema

#: Every status a client may ask for directly. `applied` is excluded because it
#: is submission-owned; `saved` is the state an Application starts in.
TransitionableStatus = Literal[
    "saved",
    "recruiter_screen",
    "interview",
    "assignment",
    "final_stage",
    "offer",
    "accepted",
    "rejected",
    "withdrawn",
    "closed",
]

#: A correction may name any status, `applied` included: it describes what
#: should have been recorded, and refusing to correct a mis-recorded `applied`
#: would leave the trail wrong with no way to say so.
CorrectableStatus = Literal[
    "saved",
    "applied",
    "recruiter_screen",
    "interview",
    "assignment",
    "final_stage",
    "offer",
    "accepted",
    "rejected",
    "withdrawn",
    "closed",
]

# The two vocabularies above are the domain's, checked rather than trusted: a
# status added to `ApplicationStatus` must not silently keep being refused here
# as an unknown value. Raised rather than asserted, because `python -O` strips
# an assert and a guard that can vanish is not a guard.
_ALL_STATUSES = {status.value for status in ApplicationStatus}
if set(CorrectableStatus.__args__) != _ALL_STATUSES:
    raise RuntimeError(
        "CorrectableStatus must match domain ApplicationStatus: "
        f"{sorted(_ALL_STATUSES ^ set(CorrectableStatus.__args__))} differ"
    )
if set(TransitionableStatus.__args__) != _ALL_STATUSES - {ApplicationStatus.APPLIED.value}:
    raise RuntimeError(
        "TransitionableStatus must be every ApplicationStatus except the submission-owned `applied`"
    )


class ApplicationMutationResponse(HttpSchema):
    """One Application's tracked state after a write, and the event that moved it."""

    application_id: str
    current_status: str
    terminal_outcome: str | None = None
    next_action: str | None = None
    next_action_date: str | None = None
    event_id: str | None = None


class SubmissionResponse(ApplicationMutationResponse):
    """A recorded submission, with any warning the caller should see.

    `warnings` carries `DOCUMENT_ON_OLDER_ANALYSIS` when the active snapshot or
    analysis has moved on from the document's (§18). It is reported, not raised.
    """

    submission_id: str
    document_hash: str | None = None
    warnings: list[str] = []


class RecruitmentTimelineItemResponse(HttpSchema):
    """One status, correction, next-action, or submission item in time order."""

    id: str
    item_type: Literal["status_transition", "status_correction", "next_action", "submission"]
    occurred_at: str
    actor_type: Literal["user", "system"] | None = None
    client: Literal["web", "worker"] | None = None
    from_status: CorrectableStatus | None = None
    to_status: CorrectableStatus | None = None
    corrects_event_id: str | None = None
    reason: str = ""
    next_action: str | None = None
    next_action_date: str | None = None
    submission_type: Literal["internal", "external"] | None = None
    document_hash: str | None = None
    metadata: dict[str, Any] = {}


class TransitionStatusRequest(HttpSchema):
    """An allowed forward transition. `reason` is optional for a normal move."""

    target_status: TransitionableStatus
    reason: str = ""
    occurred_at: str | None = None


class CorrectStatusRequest(HttpSchema):
    """A reasoned correction appended to the trail.

    The corrected event is never deleted or altered, so both the event being
    corrected and the reason are required: a correction that named neither
    would be indistinguishable from an ordinary transition.
    """

    target_status: CorrectableStatus
    corrects_event_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    occurred_at: str | None = None


class SubmitApplicationRequest(HttpSchema):
    """Record that the Ready document the client was showing was sent (§18).

    `expected_document_hash` is explicit. A submission against whatever the document
    holds now could record having sent something the user never saw, which is the
    one claim in this system that cannot be re-derived afterwards.
    """

    expected_document_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    submitted_at: str = Field(min_length=1)
    metadata: dict[str, Any] = {}


class ExternalSubmissionRequest(HttpSchema):
    """A submission made outside the system, recorded without inventing evidence.

    It carries no document content or files: nothing here sent them.
    """

    submitted_at: str = Field(min_length=1)
    metadata: dict[str, Any] = {}


class NextActionRequest(HttpSchema):
    """Set or clear the one active next action, stated in whole.

    Both fields are required and both are nullable. Clearing is a real request
    - sending `null` for each is how a client says the action is done - and
    requiring them is what keeps that distinguishable from an omitted field
    meaning "leave it alone".
    """

    next_action: str | None
    next_action_date: str | None
