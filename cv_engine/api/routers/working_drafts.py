"""The WorkingDraft surface: read, autosave, selection, lifecycle, validate, approve.

Every route here is one application command or one application query. The
router parses the transport - the ETag, the idempotency key, the path ID - and
hands the application layer explicit arguments; it holds no rule about when a
save is allowed, what a validation means, or what approval requires.

`If-Match` is required on `PATCH` and nowhere else. The other commands take the
expected version in the body because they are actions on a resource rather than
conditional replacements of it, and because an action that silently accepted
`If-Match: *` would be exactly the lost update the header exists to prevent.

Every command that writes provenance is told it is being called from the web.
The application layer defaults to `cli` because the CLI is the older caller, so
a router that stayed silent would record a browser's approval as a person at a
terminal - permanently, in an immutable `decision_provenance`.

Draft generation and replacement are not here. They are addressed to the
Application, which owns the one active draft, and live beside `analyses` in the
applications router.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from ...application.commands import (
    ApplySelectionChangeCommand,
    ApproveDraftCommand,
    ArchiveWorkingDraftCommand,
    ClaimPatch,
    RegenerateClaimCommand,
    RegenerateSectionCommand,
    UpdateWorkingDraftCommand,
    ValidateDraftCommand,
)
from ...util import new_id
from ..dependencies import Services
from ..etags import IfMatch, draft_etag, parse_draft_etag
from ..headers import IdempotencyKey
from ..responses import accepted_operation
from ..schemas.drafts import (
    ApplySelectionChangeRequest,
    ApprovalResponse,
    ApproveDraftRequest,
    ArchivedWorkingDraftResponse,
    RegenerateClaimRequest,
    RegenerateSectionRequest,
    SelectionChangeResponse,
    UpdateWorkingDraftRequest,
    ValidationRunResponse,
    WorkingDraftResponse,
    WorkingDraftUpdateResponse,
    WorkingDraftVersionRequest,
)
from ..schemas.operations import OperationResponse

router = APIRouter(prefix="/working-drafts", tags=["working-drafts"])


@router.get(
    "/{working_draft_id}",
    response_model=WorkingDraftResponse,
    summary="Read one working draft and its ETag",
)
def read_working_draft(
    working_draft_id: str, services: Services, response: Response
) -> WorkingDraftResponse:
    """`200` plus an `ETag` built from `edit_version` and `content_hash` (§20)."""
    result = services.queries.working_draft(working_draft_id)
    response.headers["ETag"] = draft_etag(result.edit_version, result.content_hash)
    return WorkingDraftResponse.model_validate(result.model_dump(mode="json"))


@router.patch(
    "/{working_draft_id}",
    response_model=WorkingDraftUpdateResponse,
    summary="Autosave one structured patch against an exact draft version",
)
def update_working_draft(
    working_draft_id: str,
    request: UpdateWorkingDraftRequest,
    services: Services,
    response: Response,
    if_match: IfMatch,
) -> WorkingDraftUpdateResponse:
    """`200` and the new `ETag`; a mismatch is `409` and changes nothing (§14).

    The header is parsed into the two arguments the command declares rather
    than handed through as a string, so the application layer is never asked to
    understand an HTTP header.
    """
    token = parse_draft_etag(if_match)
    result = services.drafts.update_working_draft(
        UpdateWorkingDraftCommand(
            working_draft_id=working_draft_id,
            expected_edit_version=token.edit_version,
            expected_content_hash=token.content_hash,
            claim_edits=[
                ClaimPatch(**edit.model_dump(mode="python")) for edit in request.claim_edits
            ],
        )
    )
    response.headers["ETag"] = draft_etag(result.edit_version, result.content_hash)
    return WorkingDraftUpdateResponse.model_validate(result.model_dump(mode="json"))


@router.post(
    "/{working_draft_id}/apply-selection-change",
    response_model=SelectionChangeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Re-select facts deterministically and rebuild the draft",
)
def apply_selection_change(
    working_draft_id: str,
    request: ApplySelectionChangeRequest,
    services: Services,
    response: Response,
) -> SelectionChangeResponse:
    """`201`: the change creates an immutable SelectionPlan (§14, §22).

    A draft carrying manual wording is refused with a `412` naming the
    regeneration commands, because a deterministic rebuild would replace the
    user's sentences with the engine's.
    """
    result = services.drafts.apply_selection_change(
        ApplySelectionChangeCommand(
            working_draft_id=working_draft_id,
            **request.model_dump(mode="python"),
        ),
        analysis_service=services.analysis,
    )
    response.headers["ETag"] = draft_etag(result.edit_version, result.content_hash)
    return SelectionChangeResponse.model_validate(result.model_dump(mode="json"))


@router.post(
    "/{working_draft_id}/regenerate-section",
    response_model=OperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Regenerate one section's wording from the analysis and plan",
)
def regenerate_section(
    working_draft_id: str,
    request: RegenerateSectionRequest,
    services: Services,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> OperationResponse:
    """`202` and a `Location`: regeneration is an AI Operation (§14).

    The exact draft version and content hash are frozen onto the Operation, so
    an autosave that lands while the provider is answering makes activation
    fail as `SOURCE_CHANGED` instead of overwriting the user's edit.

    A provider failure never falls back to a deterministic rebuild. The draft is
    left exactly as it was, and continuing deterministically is
    `apply-selection-change`, which the user issues themselves.
    """
    queued = services.operations.submit_regeneration(
        RegenerateSectionCommand(
            working_draft_id=working_draft_id,
            **request.model_dump(mode="python"),
        ),
        idempotency_key=idempotency_key or new_id(),
        draft_service=services.drafts,
    )
    return accepted_operation(response, queued)


@router.post(
    "/{working_draft_id}/regenerate-claim",
    response_model=OperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Regenerate one claim's wording from its own supporting facts",
)
def regenerate_claim(
    working_draft_id: str,
    request: RegenerateClaimRequest,
    services: Services,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> OperationResponse:
    """`202` and a `Location`, on the same contract as section regeneration (§14).

    The claim is the unit: the provider is given that claim's own supporting
    facts and nothing else, so a proposal cannot reach for a fact this line was
    never built from.
    """
    queued = services.operations.submit_regeneration(
        RegenerateClaimCommand(
            working_draft_id=working_draft_id,
            **request.model_dump(mode="python"),
        ),
        idempotency_key=idempotency_key or new_id(),
        draft_service=services.drafts,
    )
    return accepted_operation(response, queued)


@router.post(
    "/{working_draft_id}/archive",
    response_model=ArchivedWorkingDraftResponse,
    summary="Archive the draft as an immutable historical snapshot",
)
def archive_working_draft(
    working_draft_id: str,
    request: WorkingDraftVersionRequest,
    services: Services,
) -> ArchivedWorkingDraftResponse:
    """`200`: the snapshot is registered before the active pointer is cleared."""
    result = services.drafts.archive_working_draft(
        ArchiveWorkingDraftCommand(
            working_draft_id=working_draft_id,
            **request.model_dump(mode="python"),
            actor_type="user",
            client="web",
        )
    )
    return ArchivedWorkingDraftResponse.model_validate(result.model_dump(mode="json"))


@router.post(
    "/{working_draft_id}/validate",
    response_model=ValidationRunResponse,
    summary="Validate one exact working draft version",
)
def validate_working_draft(
    working_draft_id: str,
    request: WorkingDraftVersionRequest,
    services: Services,
) -> ValidationRunResponse:
    """`200` whether or not it passed: a failed validation is an outcome (§22).

    Only a validator that could not execute is an error, and that surfaces as
    `500`/`503` from the application taxonomy rather than as a report nobody
    produced.
    """
    result = services.drafts.validate_draft(
        ValidateDraftCommand(
            working_draft_id=working_draft_id,
            **request.model_dump(mode="python"),
        )
    )
    return ValidationRunResponse.model_validate(result.model_dump(mode="json"))


@router.post(
    "/{working_draft_id}/approve",
    response_model=ApprovalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Approve exactly the content one ValidationRun passed",
)
def approve_working_draft(
    working_draft_id: str,
    request: ApproveDraftRequest,
    services: Services,
    idempotency_key: IdempotencyKey = None,
) -> ApprovalResponse:
    """`201`: approval creates the immutable ApprovedRevision (§15, §22).

    The same key with the same payload returns the same revision; the same key
    with a different draft, version, run, or content hash is
    `409 IDEMPOTENCY_KEY_REUSED`.
    """
    result = services.operations.approve_idempotent(
        ApproveDraftCommand(
            working_draft_id=working_draft_id,
            **request.model_dump(mode="python"),
            actor_type="user",
            client="web",
        ),
        idempotency_key=idempotency_key or new_id(),
        draft_service=services.drafts,
    )
    return ApprovalResponse.model_validate(result.model_dump(mode="json"))
