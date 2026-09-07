"""CV-preparation read projections: snapshot/analysis through artifacts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from ...domain.contracts.analysis import JobAnalysis
from ...domain.contracts.drafts import ClaimStyle, ClaimType, DraftDocument
from ...domain.contracts.selection import OmissionReason, SelectionOutcome
from ...domain.contracts.validation import ValidationReport
from ..commands import BoundaryDTO


class JobSnapshotView(BoundaryDTO):
    id: str
    application_id: str
    version_number: int
    job_text: str
    source_url: str | None = None
    captured_at: str
    source_metadata: dict[str, Any]
    content_hash: str
    prior_snapshot_id: str | None = None


class JobAnalysisView(BoundaryDTO):
    id: str
    application_id: str
    job_snapshot_id: str
    version_number: int
    analysis: JobAnalysis
    provider: str
    model: str
    created_at: str


class PreparationState(StrEnum):
    NEEDS_ANALYSIS = "needs_analysis"
    NEEDS_REVIEW = "needs_review"
    READY_TO_DRAFT = "ready_to_draft"
    DRAFT_IN_PROGRESS = "draft_in_progress"
    READY_FOR_APPROVAL = "ready_for_approval"
    APPROVED = "approved"
    READY = "ready"


class WorkingDraftState(StrEnum):
    NONE = "none"
    EDITING = "editing"
    VALIDATION_FAILED = "validation_failed"
    VALIDATED = "validated"
    STALE = "stale"


class DraftClaimView(BoundaryDTO):
    """One editable line, as the editor needs to see it.

    Exactly the fields a claim edit addresses, plus the two that say what the
    claim currently is. `claim_type` and `style` are the domain's own closed
    sets rather than `str`, so a client's status labels stay exhaustive over
    them.
    """

    claim_id: str
    style: ClaimStyle
    text: str
    claim_type: ClaimType
    fact_ids: list[str]
    pending_reason: str | None = None


class DraftSectionView(BoundaryDTO):
    name: str
    claims: list[DraftClaimView]


class DraftOutlineView(BoundaryDTO):
    """The document's editable structure, derived per read.

    Not a second copy of `DraftDocument`: it is computed from the same object on
    each read, it stores nothing, and it deliberately carries only what an edit
    can address. The document itself stays available as `source`, versioned and
    whole, for anything that needs more than this.

    Headline and contacts are here because `draft_claims` includes them and the
    editor has to show them - marked as the structural claims they are, not as
    lines a user may remove.
    """

    headline: DraftClaimView
    contacts: list[DraftClaimView]
    sections: list[DraftSectionView]


class DraftFactView(BoundaryDTO):
    """One fact this draft either uses or considered.

    `text` is nullable because a fact the store can no longer resolve is a state
    the projection already reports as a stale reason; a read that raised instead
    would turn an explainable staleness into a 500.

    `outcome` is null for a fact that is not a SelectionPlan candidate - a
    contact, or a fact a manual relink attached. That null is what says no
    include/exclude decision applies to it, so nothing needs a second flag.
    """

    fact_id: str
    text: str | None = None
    linked_claim_ids: list[str] = []
    section: str | None = None
    outcome: SelectionOutcome | None = None
    reason: OmissionReason | None = None


class WorkingDraftFactsView(BoundaryDTO):
    """§20 candidate accounting: every fact the draft links, and every candidate.

    The union of the two, because neither covers the other. Contacts come from
    the candidate context and never appear in a SelectionPlan, while an omitted
    candidate appears in no claim - and the editor needs both to show what backs
    a line and what could be added to one.
    """

    working_draft_id: str
    application_id: str
    selection_plan_id: str
    language: str
    facts: list[DraftFactView]


class SelectionPlanCandidateView(BoundaryDTO):
    """One candidate in an immutable SelectionPlan, with safe display text."""

    fact_id: str
    text: str | None = None
    section: str
    outcome: SelectionOutcome
    reason: OmissionReason | None = None
    user_selectable: bool


class SelectionPlanDetailView(BoundaryDTO):
    """§20 SelectionPlan detail and its complete candidate accounting."""

    id: str
    application_id: str
    job_analysis_id: str
    version_number: int
    plan: dict[str, Any]
    candidate_context_version: str
    candidate_context_hash: str
    profile_version: str
    selection_policy_version: str
    track_emphasis_dependencies: dict[str, str]
    accepted_gaps: list[dict[str, Any]] = []
    created_at: str
    language: str
    facts_version: str
    pinned_fact_ids: list[str]
    excluded_fact_ids: list[str]
    candidates: list[SelectionPlanCandidateView]


class DraftPreviewView(BoundaryDTO):
    """The HTML for one exact draft version.

    The version travels with the document so a caller can tell which edit it is
    looking at, rather than inferring it from when the request was made.
    """

    working_draft_id: str
    edit_version: int
    content_hash: str
    language: str
    html: str


class WorkingDraftView(BoundaryDTO):
    """§20: the WorkingDraft a client edits, plus its optimistic token.

    `edit_version` and `content_hash` are the two halves of the ETag. They are
    carried as query fields rather than as a formatted token because the format
    is HTTP's business: the application layer states what the version is, and
    the transport decides how to spell it in a header.

    `latest_validation_run_id` is what makes an approve reachable from a read.
    Without it a client that has just seen `working_draft_state: validated`
    would have to validate again to obtain the run ID approval requires.
    """

    id: str
    application_id: str
    job_analysis_id: str
    selection_plan_id: str
    parent_revision_id: str | None = None
    source: DraftDocument
    outline: DraftOutlineView
    edit_version: int
    content_hash: str
    active: bool
    created_at: str
    updated_at: str
    latest_validation_run_id: str | None = None
    latest_validation_passed: bool | None = None


class ValidationRunView(BoundaryDTO):
    application_id: str
    working_draft_id: str
    validation_run_id: str
    edit_version: int
    content_hash: str
    passed: bool
    report: ValidationReport
    created_at: str


class ArtifactVersionView(BoundaryDTO):
    id: str
    artifact_id: str
    revision_id: str | None = None
    artifact_type: str
    logical_name: str
    version_number: int
    lifecycle_status: str
    content_hash: str
    created_at: str
    approved_at: str | None = None
    submitted_at: str | None = None
    track: str | None = None
    profile: str | None = None
    emphasis: str | None = None
    facts_version: str | None = None
    job_snapshot_id: str | None = None
    metadata: dict[str, Any]


class ArtifactVersionsView(BoundaryDTO):
    items: list[ArtifactVersionView]


class ArtifactVersionDetailView(ArtifactVersionView):
    """One artifact's registered metadata plus whether it would download (§20).

    `downloadable` is verified rather than assumed. §20 lists "artifact
    metadata/download eligibility" as one query, and a client told a payload is
    available which is then refused at download learned nothing from the first
    call - so this runs the same containment/presence/hash verification the
    download runs. `unavailable_reason` is the refusal's stable code, never its
    message: the message is where a path would be if one ever appeared.
    """

    downloadable: bool
    size: int | None = None
    unavailable_reason: str | None = None


class ApprovedRevisionView(BoundaryDTO):
    """One immutable ApprovedRevision and its Ready qualification (§20).

    The two are one query because they are one question. A revision's
    qualification is re-derived from its own stored evidence every time it is
    asked for - `ready_qualified` is never a stored flag - so returning the
    revision without it would hand a client a record it then has to interpret.

    Nothing here says whether the revision is the *active* Ready one. That is
    the Application's `preparation_state`, which is a fact about the active
    JobSnapshot and JobAnalysis rather than about this record.

    `ApprovedRevision` carries `resume_json_reference` and
    `resume_markdown_reference`, which are stored paths. They are absent here
    deliberately and `approved_revision_view` names its fields one by one
    rather than validating the record from attributes - which is how the same
    field set stayed a superset three times in M3 already. A client reaches
    those two payloads the way it reaches every other one: by artifact-version
    ID.
    """

    id: str
    application_id: str
    version_number: int
    working_draft_id: str
    job_snapshot_id: str
    job_analysis_id: str
    selection_plan_id: str
    validation_run_id: str
    draft_edit_version: int
    draft_content_hash: str
    facts_version: str
    approved_at: str
    decision_provenance: dict[str, Any]
    ready_qualified: bool
    pdf_artifact_version_id: str | None = None
    html_artifact_version_id: str | None = None
    ready_validation: ValidationReport


class DecisionRecordView(BoundaryDTO):
    id: str
    application_id: str
    artifact_version_id: str | None = None
    job_snapshot_id: str
    job_analysis_id: str
    structured: dict[str, Any]
    summary: str
    created_at: str
