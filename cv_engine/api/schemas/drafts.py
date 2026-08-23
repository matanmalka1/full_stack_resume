"""WorkingDrafts, validation, and approval over HTTP.

The draft document itself travels as an object, for the same reason the
analysis and the plan do in `schemas/analyses.py`: it is a versioned domain
document, and a second hand-written copy of its schema in the HTTP layer could
only drift from the one that is enforced.

Nothing here carries a filesystem path, and nothing here carries the ETag. The
token is a header, which is what makes it usable by a conditional request.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .health import HttpSchema


class GenerateWorkingDraftRequest(HttpSchema):
    """What `POST /applications/{id}/working-draft/generate` accepts.

    Both source IDs are explicit. A generate that resolved the latest analysis
    and plan for itself could build from a plan the user has never seen -
    §5.4's fifth acceptance item is exactly that commands take explicit source
    IDs.
    """

    job_analysis_id: str
    selection_plan_id: str


class ClaimPatchRequest(HttpSchema):
    """One claim's replacement content.

    Free text with no fact behind it is accepted and saved as a pending claim
    carrying the reason it could not be authorized; it is never discarded.
    """

    claim_id: str
    fact_ids: list[str] = []
    text: str | None = None
    template_id: str | None = None
    template_version: str | None = None


class UpdateWorkingDraftRequest(HttpSchema):
    """The structured patch `PATCH /working-drafts/{id}` applies as one edit."""

    claim_edits: list[ClaimPatchRequest] = Field(min_length=1)


class ApplySelectionChangeRequest(HttpSchema):
    """The user's explicit fact decisions for a deterministic re-selection.

    Two lists, not three, on the same reasoning as the analysis review form:
    `selected` is what the resulting plan reports, and explicit inclusion is a
    pin.
    """

    expected_edit_version: int
    pinned_fact_ids: list[str] = []
    excluded_fact_ids: list[str] = []


class WorkingDraftVersionRequest(HttpSchema):
    """The exact version a command is addressed to."""

    expected_edit_version: int


class ReplaceWorkingDraftRequest(WorkingDraftVersionRequest):
    """Replacement names its own compatible analysis and plan (§14).

    The route is `POST /applications/{id}/working-draft/replace`, so the path
    carries the Application and the body carries the draft. Both are explicit
    and neither is inferred from the other: the client states which draft of
    which Application it means, and a pair that does not match is a `412`.

    `keep_previous` is the Keep decision: it materializes the immutable
    historical snapshot before the replacement is attempted.
    """

    working_draft_id: str
    job_analysis_id: str
    selection_plan_id: str
    keep_previous: bool = False


class ApproveDraftRequest(WorkingDraftVersionRequest):
    """Approval names the ValidationRun whose result it is relying on.

    The run is not created here. Approval verifies that the run describes this
    exact draft version and content and that it passed; a run approval created
    for itself could only ever agree with approval.
    """

    validation_run_id: str


class WorkingDraftResponse(HttpSchema):
    id: str
    application_id: str
    job_analysis_id: str
    selection_plan_id: str
    parent_revision_id: str | None = None
    source: dict[str, Any]
    edit_version: int
    content_hash: str
    active: bool
    created_at: str
    updated_at: str
    latest_validation_run_id: str | None = None
    latest_validation_passed: bool | None = None


class WorkingDraftUpdateResponse(HttpSchema):
    """The new token, and which claims were saved as pending."""

    application_id: str
    working_draft_id: str
    edit_version: int
    content_hash: str
    selection_plan_id: str
    pending_claim_ids: list[str] = []


class SelectionChangeResponse(HttpSchema):
    application_id: str
    working_draft_id: str
    edit_version: int
    content_hash: str
    selection_plan_id: str
    plan: dict[str, Any]


class ArchivedWorkingDraftResponse(HttpSchema):
    application_id: str
    working_draft_id: str
    edit_version: int
    content_hash: str
    artifact_version_id: str


class ValidationRunResponse(HttpSchema):
    """A ValidationRun as data. `passed=false` arrives as `200` (§22)."""

    application_id: str
    working_draft_id: str
    validation_run_id: str
    edit_version: int
    content_hash: str
    passed: bool
    report: dict[str, Any]


class ApprovalResponse(HttpSchema):
    application_id: str
    revision_id: str
    version: int
    markdown_artifact_version_id: str
    manifest_artifact_version_id: str
    decision_record_id: str
