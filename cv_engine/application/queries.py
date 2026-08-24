"""Purpose-built read projections returned by the application layer."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from ..domain.drafts import draft_claims
from ..domain.facts import FactStore
from ..domain.models import (
    ApprovedRevision,
    ClaimStyle,
    ClaimType,
    DraftDocument,
    JobAnalysis,
    OmissionReason,
    SelectionOutcome,
    ValidationReport,
)
from .commands import BoundaryDTO
from .operations import OperationView


class ApplicationView(BoundaryDTO):
    id: str
    company: str
    target_role: str
    normalized_role: str | None = None
    source_url: str | None = None
    language: str | None = None
    track: str | None = None
    profile: str | None = None
    emphasis: str | None = None
    classification_confidence: float | None = None
    fit_level: str | None = None
    current_status: str
    terminal_outcome: str | None = None
    last_contact_date: str | None = None
    next_action: str | None = None
    next_action_date: str | None = None
    notes: str = ""
    source: str = "manual"
    created_at: str
    updated_at: str


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


class ReasonView(BoundaryDTO):
    code: str
    message: str
    entity_references: dict[str, str] = {}
    allowed_resolution_actions: list[str] = []


class WarningView(BoundaryDTO):
    code: str
    message: str
    entity_references: dict[str, str] = {}


class BlockedActionView(BoundaryDTO):
    action: str
    reasons: list[str]


class ApplicationStateView(BoundaryDTO):
    recruitment_status: str
    terminal_outcome: str | None = None
    preparation_state: PreparationState
    working_draft_state: WorkingDraftState
    review_reasons: list[ReasonView] = []
    stale_reasons: list[ReasonView] = []
    primary_stale_reason: str | None = None
    warnings: list[WarningView] = []
    active_operation: OperationView | None = None
    active_job_snapshot_id: str
    active_analysis_id: str | None = None
    active_selection_plan_id: str | None = None
    active_working_draft_id: str | None = None
    latest_approved_revision_id: str | None = None
    latest_ready_revision_id: str | None = None
    newer_draft_in_progress: bool = False
    available_actions: list[str] = []
    blocked_actions: list[BlockedActionView] = []
    recommended_action: str | None = None


class ApplicationDetailView(ApplicationStateView):
    application: ApplicationView
    latest_snapshot: JobSnapshotView
    latest_analysis: JobAnalysisView | None = None


class ApplicationListItemView(ApplicationView, ApplicationStateView):
    """The shared state/action projection plus list-display Application fields."""


class ApplicationListView(BoundaryDTO):
    items: list[ApplicationListItemView]


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


def application_view(record: dict[str, Any]) -> ApplicationView:
    return ApplicationView.model_validate(record)


def _claim_view(claim: Any) -> DraftClaimView:
    return DraftClaimView(
        claim_id=claim.claim_id,
        style=claim.style,
        text=claim.text,
        claim_type=claim.claim_type,
        fact_ids=list(claim.fact_ids),
        pending_reason=claim.pending_reason,
    )


def draft_outline_view(draft: DraftDocument) -> DraftOutlineView:
    """The editable structure of one draft, derived from the draft itself."""
    return DraftOutlineView(
        headline=_claim_view(draft.headline),
        contacts=[_claim_view(claim) for claim in draft.contacts],
        sections=[
            DraftSectionView(
                name=section.name,
                claims=[_claim_view(claim) for claim in section.claims],
            )
            for section in draft.sections
        ],
    )


def draft_facts_view(
    working_draft_id: str,
    application_id: str,
    selection_plan_id: str,
    draft: DraftDocument,
    facts: FactStore,
) -> WorkingDraftFactsView:
    """Every fact this draft links, plus every candidate its plan considered.

    Walked through `draft_claims` rather than `sections`, so the headline's
    support and the contacts - which no SelectionPlan contains - are accounted
    for alongside the candidates that can still be included or excluded.

    `draft.omitted_facts` is deliberately not a third source. It spans every
    canonical fact the store holds minus the selected ones, so reading it here
    would hand the browser the whole fact pool - the general Knowledge manager
    the product spec excludes - rather than this draft's accounting.
    """
    linked: dict[str, list[str]] = {}
    for claim in draft_claims(draft):
        for fact_id in claim.fact_ids:
            linked.setdefault(fact_id, []).append(claim.claim_id)

    candidates = {
        candidate.fact_id: candidate
        for candidate in (draft.selection.candidates if draft.selection is not None else [])
    }

    def rendering(fact_id: str) -> str | None:
        try:
            return facts.rendering(fact_id, draft.language)
        except (KeyError, ValueError):
            # A fact the store can no longer resolve is exactly what the
            # projection reports as a stale reason. It is reported as
            # unreadable, not raised: the editor still has to render the line
            # that depends on it.
            return None

    return WorkingDraftFactsView(
        working_draft_id=working_draft_id,
        application_id=application_id,
        selection_plan_id=selection_plan_id,
        language=draft.language,
        facts=[
            DraftFactView(
                fact_id=fact_id,
                text=rendering(fact_id),
                linked_claim_ids=linked.get(fact_id, []),
                section=candidates[fact_id].section if fact_id in candidates else None,
                outcome=candidates[fact_id].outcome if fact_id in candidates else None,
                reason=candidates[fact_id].reason if fact_id in candidates else None,
            )
            for fact_id in sorted(set(linked) | set(candidates))
        ],
    )


def application_list_item_view(
    record: dict[str, Any], state: ApplicationStateView
) -> ApplicationListItemView:
    return ApplicationListItemView.model_validate({**record, **state.model_dump(mode="python")})


def snapshot_view(record: dict[str, Any], job_text: str) -> JobSnapshotView:
    return JobSnapshotView.model_validate(
        {
            **{
                key: record.get(key)
                for key in JobSnapshotView.model_fields
                if key not in {"source_metadata", "job_text"}
            },
            "job_text": job_text,
            "source_metadata": json.loads(record.get("source_metadata_json") or "{}"),
        }
    )


def analysis_view(record: dict[str, Any]) -> JobAnalysisView:
    return JobAnalysisView.model_validate(
        {
            **{key: record.get(key) for key in JobAnalysisView.model_fields if key != "analysis"},
            "analysis": record["analysis"],
        }
    )


def artifact_version_view(record: dict[str, Any]) -> ArtifactVersionView:
    return ArtifactVersionView.model_validate(
        {
            **{
                key: record.get(key)
                for key in ArtifactVersionView.model_fields
                if key != "metadata"
            },
            "metadata": json.loads(record.get("metadata_json") or "{}"),
        }
    )


def approved_revision_view(
    revision: ApprovedRevision,
    qualification: Any,
) -> ApprovedRevisionView:
    """Build the client view field by field, never from the record's attributes.

    `model_validate(record, from_attributes=True)` returns the record untouched
    when it is already an instance of a wider model, which is the no-op that
    shipped the runner's Operation record to HTTP clients three separate times
    in M3. Naming the fields makes the two stored path references impossible to
    inherit by accident.
    """
    return ApprovedRevisionView(
        id=revision.id,
        application_id=revision.application_id,
        version_number=revision.version_number,
        working_draft_id=revision.working_draft_id,
        job_snapshot_id=revision.job_snapshot_id,
        job_analysis_id=revision.job_analysis_id,
        selection_plan_id=revision.selection_plan_id,
        validation_run_id=revision.validation_run_id,
        draft_edit_version=revision.draft_edit_version,
        draft_content_hash=revision.draft_content_hash,
        facts_version=revision.facts_version,
        approved_at=revision.approved_at,
        decision_provenance=revision.decision_provenance,
        ready_qualified=qualification.ready_qualified,
        pdf_artifact_version_id=qualification.pdf_artifact_version_id,
        ready_validation=qualification.validation,
    )


def decision_view(record: dict[str, Any]) -> DecisionRecordView:
    return DecisionRecordView.model_validate(
        {
            **{
                key: record.get(key)
                for key in DecisionRecordView.model_fields
                if key != "structured"
            },
            "structured": json.loads(record.get("structured_json") or "{}"),
        }
    )
