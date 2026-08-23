"""Typed command inputs and application-boundary outcomes.

These models are deliberately storage-neutral. A client receives identities,
validated domain documents, and workflow state; local paths are resolved only
by CLI compatibility code or an infrastructure adapter.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..domain.models import Fact, JobAnalysis, SelectionPlan, ValidationReport


class BoundaryDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


DuplicateMatchReason = Literal["source_url", "normalized_text", "company_title"]


class IngestCommand(BoundaryDTO):
    company: str
    target_role: str
    job_text: str
    source_url: str | None = None
    actor_type: Literal["user", "system"] = "user"
    client: Literal["web", "cli", "worker"] = "cli"
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
    client: Literal["web", "cli", "worker"] = "cli"


class CloseApplicationCommand(BoundaryDTO):
    application_id: str
    actor_type: Literal["user", "system"] = "user"
    client: Literal["web", "cli", "worker"] = "cli"


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


class DraftCommand(BoundaryDTO):
    application_id: str
    job_analysis_id: str
    selection_plan_id: str


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
    claim_edits: list[ClaimPatch] = Field(min_length=1)


class ApplySelectionChangeCommand(SelectionOverlay):
    """§14: a deterministic fact-selection change against one exact draft."""

    working_draft_id: str
    expected_edit_version: int


class ArchiveWorkingDraftCommand(BoundaryDTO):
    """§14: materialize the historical snapshot, then clear the active pointer."""

    working_draft_id: str
    expected_edit_version: int


class ReplaceWorkingDraftCommand(BoundaryDTO):
    """§14: replace one exact draft from an explicit compatible analysis and plan.

    `keep_previous` is the user's Keep decision. It materializes the immutable
    historical snapshot *before* the replacement is attempted, which is safe in
    both directions: a snapshot of content that existed is true whether or not
    the replacement then succeeds, and nothing is discarded before the new
    draft is committed.
    """

    working_draft_id: str
    expected_edit_version: int
    job_analysis_id: str
    selection_plan_id: str
    keep_previous: bool = False


class ValidateDraftCommand(BoundaryDTO):
    """§15: validate one exact WorkingDraft version."""

    working_draft_id: str
    expected_edit_version: int


class ApproveDraftCommand(BoundaryDTO):
    """§15: approve exactly the content one exact ValidationRun passed.

    All three identities are the caller's. Approval re-checks the binding
    between them; it never runs its own validation, because a validation
    approval creates for itself can only ever agree with approval.
    """

    working_draft_id: str
    expected_edit_version: int
    validation_run_id: str


class RenderCommand(BoundaryDTO):
    application_id: str
    approved_revision_id: str


class RecruitmentStatusCommand(BoundaryDTO):
    application_id: str
    target_status: str
    reason: str = ""
    occurred_at: str | None = None
    actor_type: Literal["user", "system"] = "user"
    client: Literal["web", "cli", "worker"] = "cli"


class RecruitmentCorrectionCommand(BoundaryDTO):
    application_id: str
    target_status: str
    corrects_event_id: str
    reason: str = Field(min_length=1)
    occurred_at: str | None = None
    actor_type: Literal["user", "system"] = "user"
    client: Literal["web", "cli", "worker"] = "cli"


class SubmissionCommand(BoundaryDTO):
    application_id: str
    approved_revision_id: str
    pdf_artifact_version_id: str
    submitted_at: str = Field(min_length=1)
    metadata: dict[str, Any] = {}
    actor_type: Literal["user", "system"] = "user"
    client: Literal["web", "cli", "worker"] = "cli"


class ExternalSubmissionCommand(BoundaryDTO):
    application_id: str
    submitted_at: str = Field(min_length=1)
    artifact_version_id: str | None = None
    metadata: dict[str, Any] = {}
    actor_type: Literal["user", "system"] = "user"
    client: Literal["web", "cli", "worker"] = "cli"


class NextActionCommand(BoundaryDTO):
    application_id: str
    next_action: str | None = None
    next_action_date: str | None = None
    occurred_at: str | None = None
    actor_type: Literal["user", "system"] = "user"
    client: Literal["web", "cli", "worker"] = "cli"


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


def fact_event_view(record: dict[str, Any]) -> FactEventView:
    """Strip persistence-only payload columns from one audit row."""
    return FactEventView.model_validate(
        {key: record.get(key) for key in FactEventView.model_fields}
    )
