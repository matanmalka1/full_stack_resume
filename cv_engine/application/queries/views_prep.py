"""CV-preparation read projections: snapshot and analysis through the CV document."""

from __future__ import annotations

from typing import Any, Literal

from ...domain.contracts.analysis import JobAnalysis
from ...domain.contracts.drafts import ClaimStyle, ClaimType, DraftDocument
from ...domain.contracts.selection import OmissionReason, ProposalSource, SelectionOutcome
from ...domain.contracts.taxonomy import Emphasis
from ...domain.contracts.validation import ValidationReport
from ...domain.document import ContentCheck, PreparationState
from ..commands import BoundaryDTO


class JobSnapshotView(BoundaryDTO):
    id: str
    application_id: str
    version_number: int
    job_text: str
    source_url: str | None = None
    captured_at: str
    source_metadata: dict[str, Any]
    source_hash: str


class JobSnapshotHistoryItem(BoundaryDTO):
    id: str
    version_number: int
    captured_at: str
    source_url: str | None
    job_text: str | None


class JobSnapshotHistoryView(BoundaryDTO):
    active_job_snapshot_id: str
    items: list[JobSnapshotHistoryItem]


class GapView(BoundaryDTO):
    requirement_id: str
    requirement: str
    severity: Literal["hard", "warning"]
    reason: str
    substitute_fact_ids: list[str] = []


class JobAnalysisView(BoundaryDTO):
    """The stored analysis, and what is projected from it for display.

    `fit_level`, `fit_score` and `gaps` sit beside `analysis` rather than inside
    it. The record holds requirements only; these are computed from them at read
    time, so a reader sees the same answer the engine would compute and there is
    no second stored copy to disagree with the first.
    """

    id: str
    application_id: str
    job_snapshot_id: str
    version_number: int
    analysis: JobAnalysis
    fit_level: str
    fit_score: float | None = None
    gaps: list[GapView] = []
    provider: str
    model: str
    created_at: str


class ClaimReviewAssertionView(BoundaryDTO):
    claim_quote: str
    fact_ids: list[str]
    source_quotes: list[str]


class ClaimReviewEvidenceView(BoundaryDTO):
    """Safe, user-readable evidence; internal provider lineage stays private."""

    policy_version: str
    assertions: list[ClaimReviewAssertionView]


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
    review_evidence: ClaimReviewEvidenceView | None = None


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


class BuiltWithView(BoundaryDTO):
    profile_version: str
    selection_policy_version: str


class DocumentCandidateView(BoundaryDTO):
    """One candidate in the document's selection, with safe display text."""

    fact_id: str
    text: str | None = None
    section: str
    outcome: SelectionOutcome
    reason: OmissionReason | None = None
    user_selectable: bool


class DocumentSelectionView(BoundaryDTO):
    """The document's selection with its complete candidate accounting (§20)."""

    emphasis: Emphasis
    emphasis_override: Emphasis | None = None
    selected_fact_ids: list[str]
    pinned_fact_ids: list[str]
    excluded_fact_ids: list[str]
    #: `"ai"` when an AI selection proposal was activated; null for engine and
    #: user selections.
    proposed_by: ProposalSource | None = None
    #: The provider's own written rationale, verbatim; provenance only.
    proposal_rationale: str | None = None
    candidates: list[DocumentCandidateView]


class DocumentView(BoundaryDTO):
    """§20: the CVDocument, with its token and the states derived at read time.

    `document_hash` is the concurrency token a client conditions on. The stored
    content report is returned even when outdated, so it can be shown as such;
    `content_check` says whether it is current. No path is carried.
    """

    id: str
    application_id: str
    analysis_id: str
    document_hash: str
    built_with: BuiltWithView
    language: str
    selection: DocumentSelectionView
    content: DraftDocument | None = None
    outline: DraftOutlineView | None = None
    facts: list[DraftFactView] = []
    preparation_state: PreparationState
    content_check: ContentCheck
    content_report: ValidationReport | None = None
    approved_at: str | None = None
    last_render_error: dict[str, Any] | None = None
    created_at: str
    updated_at: str


class DocumentPreviewView(BoundaryDTO):
    """The HTML of the document's current content, marked as a draft, stored nowhere.

    The hash travels with it so a caller can tell which content it is looking at,
    rather than inferring it from when the request was made.
    """

    application_id: str
    document_id: str
    document_hash: str
    language: str
    html: str


class DocumentPdfPreviewView(BoundaryDTO):
    """The document's current content as a stamped, unstored preview PDF."""

    application_id: str
    document_id: str
    document_hash: str
    pdf: bytes


class ArtifactVersionView(BoundaryDTO):
    id: str
    artifact_id: str
    artifact_type: str
    logical_name: str
    version_number: int
    lifecycle_status: str
    content_hash: str
    created_at: str
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
