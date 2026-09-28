"""Recruitment tracking: status transitions, corrections, submissions, next action.

These are Application-scoped writes, so they live under `/applications/{id}`
beside `close`, which is the same kind of command and already routed there.

Actor and client are set here, not accepted from the request. A call arriving
over this API is the Web client by definition, and provenance a caller could
name for itself would not be provenance.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from ...application.commands import (
    ExternalSubmissionCommand,
    NextActionCommand,
    RecruitmentCorrectionCommand,
    RecruitmentStatusCommand,
    SubmissionCommand,
)
from ..dependencies import Services
from ..schemas.tracking import (
    ApplicationMutationResponse,
    CorrectStatusRequest,
    ExternalSubmissionRequest,
    NextActionRequest,
    SubmissionResponse,
    SubmitApplicationRequest,
    TransitionStatusRequest,
)

router = APIRouter(prefix="/applications", tags=["tracking"])


@router.post(
    "/{application_id}/status",
    response_model=ApplicationMutationResponse,
    summary="Transition recruitment status with an immutable history",
)
def transition_status(
    application_id: str,
    request: TransitionStatusRequest,
    services: Services,
) -> ApplicationMutationResponse:
    """`200`: asking for the status an Application already holds is not an error.

    The application layer returns the current state unchanged rather than
    appending a second identical event, so a client that retries a transition
    it already made does not write a duplicate into the trail.
    """
    result = services.recruitment.transition_status(
        RecruitmentStatusCommand(
            application_id=application_id,
            target_status=request.target_status,
            reason=request.reason,
            occurred_at=request.occurred_at,
            actor_type="user",
            client="web",
        )
    )
    return ApplicationMutationResponse.model_validate(result.model_dump(mode="json"))


@router.post(
    "/{application_id}/status-corrections",
    response_model=ApplicationMutationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Append a reasoned correction to recruitment history",
)
def correct_status(
    application_id: str,
    request: CorrectStatusRequest,
    services: Services,
) -> ApplicationMutationResponse:
    """`201`: a correction appends an event; it never edits the one it corrects."""
    result = services.recruitment.correct_recruitment_status(
        RecruitmentCorrectionCommand(
            application_id=application_id,
            target_status=request.target_status,
            corrects_event_id=request.corrects_event_id,
            reason=request.reason,
            occurred_at=request.occurred_at,
            actor_type="user",
            client="web",
        )
    )
    return ApplicationMutationResponse.model_validate(result.model_dump(mode="json"))


@router.post(
    "/{application_id}/submissions",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record that the Ready document was sent",
)
def submit_application(
    application_id: str,
    request: SubmitApplicationRequest,
    services: Services,
) -> SubmissionResponse:
    """`201`: an immutable Submission of the content and rendered files (§18).

    Refused with `412` unless the document is Ready when the request is answered and
    still carries `expected_document_hash`, rather than recording a claim that
    something the user never saw was sent.
    """
    result = services.submission.submit_application(
        SubmissionCommand(
            application_id=application_id,
            expected_document_hash=request.expected_document_hash,
            submitted_at=request.submitted_at,
            metadata=request.metadata,
            actor_type="user",
            client="web",
        )
    )
    return SubmissionResponse.model_validate(result.model_dump(mode="json"))


@router.post(
    "/{application_id}/external-submissions",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a submission made outside the system",
)
def record_external_submission(
    application_id: str,
    request: ExternalSubmissionRequest,
    services: Services,
) -> SubmissionResponse:
    """`201`: recorded without inventing content or files that never passed through here."""
    result = services.submission.record_external_submission(
        ExternalSubmissionCommand(
            application_id=application_id,
            submitted_at=request.submitted_at,
            metadata=request.metadata,
            actor_type="user",
            client="web",
        )
    )
    return SubmissionResponse.model_validate(result.model_dump(mode="json"))


@router.patch(
    "/{application_id}/next-action",
    response_model=ApplicationMutationResponse,
    summary="Set or clear the one active next action",
)
def set_next_action(
    application_id: str,
    request: NextActionRequest,
    services: Services,
) -> ApplicationMutationResponse:
    """States what the one active next action now is, in whole.

    Sending both fields empty clears it: the request carries the complete value
    rather than a partial edit, and the schema requires both fields so an
    omitted one cannot be read as "leave it alone". `PATCH` rather than `PUT`
    because `PUT` is outside this API's allowed methods, and widening transport
    policy for one route's verb would be the wrong trade.
    """
    result = services.recruitment.set_next_action(
        NextActionCommand(
            application_id=application_id,
            next_action=request.next_action,
            next_action_date=request.next_action_date,
            actor_type="user",
            client="web",
        )
    )
    return ApplicationMutationResponse.model_validate(result.model_dump(mode="json"))
