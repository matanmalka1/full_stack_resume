"""Typed command inputs and application-boundary outcomes.

These models are deliberately storage-neutral. A client receives identities,
validated domain documents, and workflow state; local paths are resolved only
by an infrastructure adapter.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..domain.models import Fact, JobAnalysis, SelectionPlan, ValidationReport


class BoundaryDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


#: Who a new record may name as its originating client. There is no default: a
#: command that records who acted must be told, because a wrong default is
#: indistinguishable from a correct one once it is in the audit trail.
WriteClient = Literal["web", "worker"]

DuplicateMatchReason = Literal["source_url", "normalized_text", "company_title"]


class IngestCommand(BoundaryDTO):
    company: str
    target_role: str
    job_text: str
    source_url: str | None = None
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient
    acknowledged_duplicates: bool = False


class DuplicateCheckCommand(BoundaryDTO):
    company: str
    target_role: str
    job_text: str
    source_url: str | None = None


class CreateJobSnapshotCommand(BoundaryDTO):
    application_id: str
    job_text: str
    source_url: str | None = None
    source_metadata: dict[str, Any] = {}
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient


class CloseApplicationCommand(BoundaryDTO):
    application_id: str
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient


class AnalyzeCommand(BoundaryDTO):
    application_id: str
    job_snapshot_id: str
    track_override: str | None = None
    profile_override: str | None = None
    emphasis_override: str | None = None
    language_override: str | None = None
    accept_low_fit: bool = False
    provider: str = "deterministic"
    model: str = "rules-v1"


class SelectionOverlay(BoundaryDTO):
    """One user's explicit fact decisions, laid over the deterministic engine.

    Two lists, not three. `selected` is what the plan reports, not what a client
    asks for: in a budgeted deterministic selection the only way to say "include
    this" is to hold it, which is what a pin is.
    """

    pinned_fact_ids: list[str] = []
    excluded_fact_ids: list[str] = []


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
    expected_candidate_context_hash: str | None = None
    expected_profile_version: str | None = None
    expected_selection_policy_version: str | None = None


class ApplyAnalysisDecisionsCommand(SelectionOverlay):
    """One local review-form submission (§13).

    Carries both kinds of decision because one form does. Which branch runs is
    decided by what actually changes, not by which fields the client filled in.
    """

    application_id: str
    job_analysis_id: str
    track_override: str | None = None
    profile_override: str | None = None
    emphasis_override: str | None = None
    language_override: str | None = None
    accept_low_fit: bool = False


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
    expected_profile_version: str | None = None
    expected_selection_policy_version: str | None = None
    model: str | None = None


class DraftCommand(BoundaryDTO):
    """§14 `create_draft`, in either mode.

    `provider` is explicit and has no `auto` value (§12). Deterministic is the
    default because the deterministic workflow must reach Ready with no key
    configured; asking for `openai` without a configured provider is a refusal,
    never a silent fall back to the default.
    """

    application_id: str
    job_analysis_id: str
    selection_plan_id: str
    parent_revision_id: str | None = None
    provider: Literal["deterministic", "openai"] = "deterministic"


class RegenerateSectionCommand(BoundaryDTO):
    """§14 `regenerate_section`: one exact draft version, one named section.

    The draft's identity is stated in all three parts the specification names -
    ID, `edit_version`, and content hash - because that is what the Operation
    freezes. A regeneration that named only the ID could activate over content
    the user changed while it was running.
    """

    application_id: str
    working_draft_id: str
    expected_edit_version: int
    expected_content_hash: str
    job_analysis_id: str
    selection_plan_id: str
    section: str
    instruction: str = ""


class RegenerateClaimCommand(BoundaryDTO):
    """§14 `regenerate_claim`: one exact draft version, one named claim."""

    application_id: str
    working_draft_id: str
    expected_edit_version: int
    expected_content_hash: str
    job_analysis_id: str
    selection_plan_id: str
    claim_id: str
    instruction: str = ""


class ClaimPatch(BoundaryDTO):
    """One claim's new content inside a structured WorkingDraft patch.

    Free text with no fact behind it is not refused here. The domain edit path
    keeps it as a `pending` claim carrying the reason it could not be
    authorized, because §14 requires unauthorized free text to be saved rather
    than silently rejected or discarded.
    """

    claim_id: str
    fact_ids: list[str] = []
    text: str | None = None
    template_id: str | None = None
    template_version: str | None = None


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

    @model_validator(mode="after")
    def validate_patch(self) -> UpdateWorkingDraftCommand:
        """A patch has to change something, and may not contradict itself.

        Removal rides on this command rather than on one of its own because
        product-spec §10 makes removal one of the three ways an unsupported
        claim is resolved, and §14 commits an autosave patch as a single edit
        against a single expected version. A separate command would need its own
        token and could interleave with the save the user is already making.
        """
        if not self.claim_edits and not self.claim_removals:
            raise ValueError("a working draft patch must edit or remove at least one claim")
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


class RenderCommand(BoundaryDTO):
    application_id: str
    approved_revision_id: str


class RecruitmentStatusCommand(BoundaryDTO):
    application_id: str
    target_status: str
    reason: str = ""
    occurred_at: str | None = None
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient


class RecruitmentCorrectionCommand(BoundaryDTO):
    application_id: str
    target_status: str
    corrects_event_id: str
    reason: str = Field(min_length=1)
    occurred_at: str | None = None
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient


class SubmissionCommand(BoundaryDTO):
    application_id: str
    approved_revision_id: str
    pdf_artifact_version_id: str
    submitted_at: str = Field(min_length=1)
    metadata: dict[str, Any] = {}
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient


class ExternalSubmissionCommand(BoundaryDTO):
    application_id: str
    submitted_at: str = Field(min_length=1)
    artifact_version_id: str | None = None
    metadata: dict[str, Any] = {}
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient


class NextActionCommand(BoundaryDTO):
    application_id: str
    next_action: str | None = None
    next_action_date: str | None = None
    occurred_at: str | None = None
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient


class DuplicateMatch(BoundaryDTO):
    application_id: str
    company: str
    target_role: str
    matched_on: list[DuplicateMatchReason]


class IngestedApplication(BoundaryDTO):
    application_id: str
    job_snapshot_id: str
    warnings: list[str] = []
    duplicate_matches: list[DuplicateMatch] = []


class DuplicateCheckResult(BoundaryDTO):
    matches: list[DuplicateMatch] = []


class CreatedJobSnapshot(BoundaryDTO):
    application_id: str
    job_snapshot_id: str


class AnalysisResult(BoundaryDTO):
    application_id: str
    job_snapshot_id: str
    analysis_id: str
    selection_plan_id: str
    analysis: JobAnalysis


class SelectionPlanResult(BoundaryDTO):
    application_id: str
    job_analysis_id: str
    selection_plan_id: str
    plan: SelectionPlan


class AnalysisDecisionsResult(BoundaryDTO):
    """What the review form produced, and which of the two branches produced it.

    `job_analysis_id` is the analysis in force *after* the command: the new one
    when meaning changed, the original one when only the overlay did. The source
    analysis is untouched either way, so `created_analysis` is what tells a
    client whether it is now looking at a different record.
    """

    application_id: str
    job_analysis_id: str
    selection_plan_id: str
    created_analysis: bool
    analysis: JobAnalysis
    plan: SelectionPlan


class DraftResult(BoundaryDTO):
    application_id: str
    job_analysis_id: str
    selection_plan_id: str
    working_draft_id: str
    edit_version: int
    validation: ValidationReport


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


class RegenerationResult(BoundaryDTO):
    """What one AI regeneration committed, and what produced it.

    `provider_artifact_version_id` names the registered sanitized response, so a
    client - and a later reader of the record - can reach the exact evidence for
    the wording that landed without going through the Operation's outputs.
    """

    application_id: str
    working_draft_id: str
    edit_version: int
    content_hash: str
    selection_plan_id: str
    regenerated_claim_ids: list[str]
    provider_artifact_version_id: str


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


class RenderResult(BoundaryDTO):
    application_id: str
    pdf_artifact_version_id: str
    validation: ValidationReport


class ApplicationMutationResult(BoundaryDTO):
    application_id: str
    current_status: str
    terminal_outcome: str | None = None
    next_action: str | None = None
    next_action_date: str | None = None
    event_id: str | None = None


class SubmissionResult(ApplicationMutationResult):
    submission_id: str
    approved_revision_id: str | None = None
    pdf_artifact_version_id: str | None = None
    warnings: list[str] = []


class DecisionMarkdownExport(BoundaryDTO):
    application_id: str
    approved_revision_id: str
    filename: str
    content: str
    content_hash: str


class KnowledgeVersionsResult(BoundaryDTO):
    facts: str
    facts_lifecycle: str
    profiles: str
    emphasis_policies: str
    presentations: str
    candidate_context: str


class FactEventView(BoundaryDTO):
    id: str
    fact_id: str
    source_file: str
    event_type: str
    from_status: str | None
    to_status: str
    application_id: str | None
    claim_id: str | None
    reason: str
    fact_hash: str
    facts_version: str
    lifecycle_version: str
    created_at: str


class FactListItem(BoundaryDTO):
    fact: Fact
    recorded_status: str | None = None


class FactListResult(BoundaryDTO):
    items: list[FactListItem]


class FactDetailResult(BoundaryDTO):
    fact: Fact
    events: list[FactEventView]


class FactHistoryResult(BoundaryDTO):
    events: list[FactEventView]


class FactMutationResult(BoundaryDTO):
    fact: Fact
    event_id: str
    facts_version: str
    lifecycle_version: str


class FactAttachmentResult(FactMutationResult):
    profile: str
    section: str
    pinned: bool
    profile_source: str
    profile_store_version: str


class ConfirmAndUseFactResult(BoundaryDTO):
    fact: Fact
    event_ids: list[str]
    selection_plan: SelectionPlan
    facts_version: str
    lifecycle_version: str
    profile_store_version: str


class FactReconciliationResult(BoundaryDTO):
    passed: bool
    fact_counts: dict[str, int]
    tracked_facts: int
    facts_version: str
    lifecycle_version: str
    problems: list[str]
    journal_prepared: int = 0
    journal_quarantined: int = 0


class ReconciliationResult(BoundaryDTO):
    """The whole-instance reconciliation report.

    `passed` is the conjunction of both halves: stored evidence agreeing with
    the database, and the fact lifecycle agreeing with its audit trail. A
    caller that reads only one half would report a healthy instance while the
    other half is broken.
    """

    passed: bool
    artifact_versions_checked: int
    problems: list[str]
    fact_lifecycle: FactReconciliationResult


def fact_event_view(record: dict[str, Any]) -> FactEventView:
    """Strip persistence-only payload columns from one audit row."""
    return FactEventView.model_validate(
        {key: record.get(key) for key in FactEventView.model_fields}
    )
