"""WorkingDrafts, validation, and approval over HTTP.

The draft document itself travels as an object, for the same reason the
analysis and the plan do in `schemas/analyses.py`: it is a versioned domain
document, and a second hand-written copy of its schema in the HTTP layer could
only drift from the one that is enforced.

Nothing here carries a filesystem path, and nothing here carries the ETag. The
token is a header, which is what makes it usable by a conditional request.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from ...domain.models import ClaimStyle, ClaimType, OmissionReason, SelectionOutcome
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
    provider: Literal["deterministic", "openai"] = "deterministic"


class RegenerateSectionRequest(HttpSchema):
    """What `POST /working-drafts/{id}/regenerate-section` accepts (§14).

    The draft's exact version and content hash are in the body rather than in
    `If-Match`, on the same reasoning as `validate` and `approve`: this is an
    action on a resource, not a conditional replacement of it, and an action
    that accepted `If-Match: *` would be the lost update the header exists to
    prevent.

    The analysis and plan are explicit. A regeneration that resolved them for
    itself could rewrite a section against a plan the user never saw.
    """

    application_id: str
    expected_edit_version: int
    expected_content_hash: str
    job_analysis_id: str
    selection_plan_id: str
    section: str = Field(max_length=200)
    instruction: str = Field(default="", max_length=2000)


class RegenerateClaimRequest(HttpSchema):
    """What `POST /working-drafts/{id}/regenerate-claim` accepts (§14)."""

    application_id: str
    expected_edit_version: int
    expected_content_hash: str
    job_analysis_id: str
    selection_plan_id: str
    claim_id: str = Field(max_length=200)
    instruction: str = Field(default="", max_length=2000)


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
    """The structured patch `PATCH /working-drafts/{id}` applies as one edit.

    Removals travel with the edits rather than in a command of their own.
    Product spec §10 makes removal one of the three resolutions for free text
    nothing could authorize, and §14 commits an autosave patch as a single edit
    against a single expected version - a second command would need its own
    token and could interleave with the save already in flight.

    Only one of the two lists has to be non-empty. Requiring both would make
    "remove this line" impossible to express without also rewriting one.
    """

    claim_edits: list[ClaimPatchRequest] = []
    claim_removals: list[str] = Field(
        default=[],
        description=(
            "Claims to delete outright. Only an unauthorized section claim may "
            "be removed this way; a claim the fact selection authorizes is a "
            "412 naming apply-selection-change, and the headline and contacts "
            "are structural."
        ),
    )

    @model_validator(mode="after")
    def validate_patch(self) -> UpdateWorkingDraftRequest:
        """Refused as a bad request, before any of it is applied.

        The command carries the same invariant for the CLI, but a contradiction
        that only surfaced there would reach the client as a 500 rather than as
        the `422` an unusable request deserves.
        """
        if not self.claim_edits and not self.claim_removals:
            raise ValueError("a patch must edit or remove at least one claim")
        both = {edit.claim_id for edit in self.claim_edits} & set(self.claim_removals)
        if both:
            raise ValueError(f"a patch cannot both edit and remove the same claim: {sorted(both)}")
        return self


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
    provider: Literal["deterministic", "openai"] = "deterministic"


class ApproveDraftRequest(WorkingDraftVersionRequest):
    """Approval names the ValidationRun whose result it is relying on.

    The run is not created here. Approval verifies that the run describes this
    exact draft version and content and that it passed; a run approval created
    for itself could only ever agree with approval.
    """

    validation_run_id: str


class DraftClaimResponse(HttpSchema):
    """One editable line: what a claim edit addresses, plus what it currently is.

    `claim_type` and `style` are the domain's closed sets rather than `str`, so
    a client's status labels stay exhaustive over them and a claim type added
    here fails that client's build instead of reaching a screen untranslated.
    """

    claim_id: str
    style: ClaimStyle
    text: str
    claim_type: ClaimType
    fact_ids: list[str]
    pending_reason: str | None = None


class DraftSectionResponse(HttpSchema):
    name: str
    claims: list[DraftClaimResponse]


class DraftOutlineResponse(HttpSchema):
    """The document's editable structure, derived from `source` on every read.

    Not a competing copy of the draft: it stores nothing, it is computed from
    the same object `source` carries, and it holds only what an edit can
    address. `source` remains the whole versioned document for anything that
    needs more than the editor does.
    """

    headline: DraftClaimResponse
    contacts: list[DraftClaimResponse]
    sections: list[DraftSectionResponse]


class DraftFactResponse(HttpSchema):
    """One fact this draft uses, or one its SelectionPlan considered.

    `text` is nullable: a fact the store can no longer resolve is already
    reported as a stale reason by the state projection, and a read that raised
    over it would turn an explainable staleness into a `500`.

    `outcome` is null for a fact no SelectionPlan ranked - a contact, or a fact
    a manual relink attached. That null is what says no include/exclude decision
    applies to it, so no second flag is needed to say the same thing.
    """

    fact_id: str
    text: str | None = None
    linked_claim_ids: list[str] = []
    section: str | None = None
    outcome: SelectionOutcome | None = None
    reason: OmissionReason | None = None


class WorkingDraftFactsResponse(HttpSchema):
    """§20 candidate accounting: the union of linked facts and plan candidates.

    Neither set covers the other. Contacts come from the candidate context and
    appear in no SelectionPlan; an omitted candidate appears in no claim. The
    editor needs both - one to say what backs a line, the other to say what
    could be added to one.
    """

    working_draft_id: str
    application_id: str
    selection_plan_id: str
    language: str
    facts: list[DraftFactResponse]


class WorkingDraftResponse(HttpSchema):
    id: str
    application_id: str
    job_analysis_id: str
    selection_plan_id: str
    parent_revision_id: str | None = None
    source: dict[str, Any]
    outline: DraftOutlineResponse
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
