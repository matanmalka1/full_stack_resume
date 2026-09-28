"""Revision-model command DTOs the single-document model no longer uses.

Temporary re-export: removed in Wave 3. `cv_engine/api` and the revision ports still
import these names until their routers and ports are rewired or deleted; no
application service accepts them any more.
"""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from ...domain.contracts.selection import SelectionPlan
from ...domain.contracts.validation import ValidationReport
from ._base import BoundaryDTO, WriteClient
from .prep import ClaimAddition, ClaimPatch, SelectionOverlay

__all__ = [
    "CreateSelectionPlanCommand",
    "ProposeSelectionPlanCommand",
    "UpdateWorkingDraftCommand",
    "ApplySelectionChangeCommand",
    "ArchiveWorkingDraftCommand",
    "ReplaceWorkingDraftCommand",
    "ValidateDraftCommand",
    "ApproveDraftCommand",
    "SelectionPlanResult",
    "EditResult",
    "WorkingDraftUpdateResult",
    "SelectionChangeResult",
    "ArchivedWorkingDraftResult",
    "ValidationRunResult",
    "ApprovalResult",
]


class CreateSelectionPlanCommand(SelectionOverlay):
    """The deterministic form of §13 `create_selection_plan`.

    The `expected_*` versions are the optimistic check: they are what the client
    had in front of it when the user decided. Left unset the plan is built
    against whatever Knowledge currently says; set and no longer matching, the
    command refuses rather than quietly planning against something the user never
    saw.
    """

    application_id: str
    job_analysis_id: str
    #: Emphasis changes selection and presentation policy but not the meaning
    #: of JobAnalysis. A value here creates a replacement plan and records the
    #: explicit choice on its manifest.
    emphasis_override: str | None = None
    #: The plan the user was looking at when they decided. Set, and the active
    #: plan has moved on, the command is refused rather than quietly rebased
    #: onto a plan the user never saw - which is how an acceptance went missing
    #: with no error at all.
    expected_selection_plan_id: str | None = None
    expected_candidate_context_hash: str | None = None
    expected_facts_version: str | None = None
    expected_profile_version: str | None = None
    expected_selection_policy_version: str | None = None
    #: Internal optimistic guard used by asynchronous selection proposals. Unlike the
    #: public optional ID, this also distinguishes "there was no active plan" from "the
    #: caller did not state an expectation", so a plan created while AI is running cannot
    #: be silently replaced at activation.
    enforce_expected_selection_plan: bool = False
    #: Internal counterpart of AnalyzeCommand's guard, used by the plan-only
    #: branch of apply_analysis_decisions.
    refuse_matching_context_operation: bool = False
    #: Internal: set only by the `propose_selection_plan` Operation, carrying the
    #: provider's rationale onto the manifest it activates. Not a request field.
    ai_proposal_rationale: str | None = None


class ProposeSelectionPlanCommand(SelectionOverlay):
    """The AI form of §13 `create_selection_plan`.

    Carries the same optimistic `expected_*` versions as the deterministic
    form, because activation runs the deterministic command: a Proposal built
    against Knowledge that has since moved is refused there, not here.

    It inherits the overlay lists but does not use them as input - the provider
    proposes the overlay. They are inherited rather than removed so a client
    cannot send them under a name the command silently ignores: an overlay sent
    here is a `422` from the HTTP schema, which declares only what this command
    reads.
    """

    application_id: str
    job_analysis_id: str
    expected_candidate_context_hash: str | None = None
    expected_facts_version: str | None = None
    expected_profile_version: str | None = None
    expected_selection_policy_version: str | None = None
    expected_selection_plan_id: str | None = None
    enforce_expected_selection_plan: bool = False
    model: str | None = None
    reasoning_effort: str | None = None


class UpdateWorkingDraftCommand(BoundaryDTO):
    """§14 autosave: one exact draft version, and a structured patch.

    Both halves of the ETag are stated, not just the version. The version alone
    proves nobody else has saved since; the content hash proves the client was
    editing the document this command is about to change, which is what an
    `If-Match` header actually promised.
    """

    working_draft_id: str
    expected_edit_version: int
    expected_content_hash: str
    claim_edits: list[ClaimPatch] = []
    claim_removals: list[str] = []
    claim_additions: list[ClaimAddition] = []
    claim_orders: dict[str, list[str]] = {}

    @model_validator(mode="after")
    def validate_patch(self) -> UpdateWorkingDraftCommand:
        """A patch has to change something, and may not contradict itself.

        Removal and ordering ride on this command rather than commands of their own because
        product-spec §10 makes removal one of the three ways an unsupported
        claim is resolved, and §14 commits an autosave patch as a single edit
        against a single expected version. A separate command would need its own
        token and could interleave with the save the user is already making.
        """
        if (
            not self.claim_edits
            and not self.claim_removals
            and not self.claim_additions
            and not self.claim_orders
        ):
            raise ValueError("a working draft patch must edit, remove, add, or reorder content")
        both = {edit.claim_id for edit in self.claim_edits} & set(self.claim_removals)
        if both:
            raise ValueError(f"a patch cannot both edit and remove the same claim: {sorted(both)}")
        return self


class ApplySelectionChangeCommand(SelectionOverlay):
    """§14: a deterministic fact-selection change against one exact draft."""

    working_draft_id: str
    expected_edit_version: int


class ArchiveWorkingDraftCommand(BoundaryDTO):
    """§14: materialize the historical snapshot, then clear the active pointer.

    `actor_type` and `client` are carried rather than assumed, because this
    command writes an audit record. A Web archive recorded as anything else is
    a false statement in the one place that exists to answer who did it.
    """

    working_draft_id: str
    expected_edit_version: int
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient


class ReplaceWorkingDraftCommand(BoundaryDTO):
    """§14: replace one exact draft from an explicit compatible analysis and plan.

    `application_id` is stated by the caller rather than read off the draft. The
    client says which Application it believes it is replacing a draft for, and a
    draft that belongs to another one is a `412` naming the broken lineage -
    the same rule Stage D applied to `apply_analysis_decisions`.

    `keep_previous` is the user's Keep decision. It materializes the immutable
    historical snapshot *before* the replacement is attempted, which is safe in
    both directions: a snapshot of content that existed is true whether or not
    the replacement then succeeds, and nothing is discarded before the new
    draft is committed.
    """

    application_id: str
    working_draft_id: str
    expected_edit_version: int
    job_analysis_id: str
    selection_plan_id: str
    keep_previous: bool = False
    provider: Literal["deterministic", "openai"] = "deterministic"
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient


class ValidateDraftCommand(BoundaryDTO):
    """§15: validate one exact WorkingDraft version."""

    working_draft_id: str
    expected_edit_version: int


class ApproveDraftCommand(BoundaryDTO):
    """§15: approve exactly the content one exact ValidationRun passed.

    All three identities are the caller's. Approval re-checks the binding
    between them; it never runs its own validation, because a validation
    approval creates for itself can only ever agree with approval.

    `actor_type` and `client` reach the ApprovedRevision's `decision_provenance`,
    which is immutable. Getting them wrong is not a mislabelled log line: it is
    a permanent record saying a person at a terminal approved something a
    browser did.
    """

    working_draft_id: str
    expected_edit_version: int
    validation_run_id: str
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient


class SelectionPlanResult(BoundaryDTO):
    application_id: str
    job_analysis_id: str
    selection_plan_id: str
    plan: SelectionPlan


class EditResult(BoundaryDTO):
    application_id: str
    working_draft_id: str
    edit_version: int
    validation: ValidationReport


class WorkingDraftUpdateResult(BoundaryDTO):
    """The new optimistic token, plus what could not be authorized.

    `pending_claim_ids` names the claims saved as pending: the text is stored,
    and the client is told which lines still need a fact rather than having to
    diff the document to find out.
    """

    application_id: str
    working_draft_id: str
    edit_version: int
    content_hash: str
    selection_plan_id: str
    pending_claim_ids: list[str] = []


class SelectionChangeResult(BoundaryDTO):
    """The immutable plan the change created, and the draft now built on it."""

    application_id: str
    working_draft_id: str
    edit_version: int
    content_hash: str
    selection_plan_id: str
    plan: SelectionPlan


class ArchivedWorkingDraftResult(BoundaryDTO):
    """The registered historical snapshot, and the draft it froze."""

    application_id: str
    working_draft_id: str
    edit_version: int
    content_hash: str
    artifact_version_id: str


class ValidationRunResult(BoundaryDTO):
    """One immutable ValidationRun, whether or not it passed.

    `passed=false` is a successful outcome (§22). The run ID is returned
    because approval takes it as an argument: a client that could not name the
    run it read could not prove which content it was approving.
    """

    application_id: str
    working_draft_id: str
    validation_run_id: str
    edit_version: int
    content_hash: str
    passed: bool
    report: ValidationReport


class ApprovalResult(BoundaryDTO):
    application_id: str
    revision_id: str
    version: int
    markdown_artifact_version_id: str
    manifest_artifact_version_id: str
    decision_record_id: str
