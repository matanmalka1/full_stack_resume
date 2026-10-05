"""CV-preparation read projections: job posting and analysis through the CV document."""

from __future__ import annotations

from typing import Any, Literal

from ...domain.contracts.analysis import JobAnalysis
from ...domain.contracts.drafts import ClaimStyle, ClaimType, DraftDocument
from ...domain.contracts.validation import ValidationReport
from ...domain.document import ContentCheck, PreparationState
from ..commands import BoundaryDTO


class JobPostingView(BoundaryDTO):
    """The Application's job text, editable until the Application has a Submission."""

    job_text: str
    source_url: str | None = None
    job_text_hash: str
    job_text_updated_at: str
    locked: bool


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
    job_text_hash: str
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
    """One fact this draft's claims link.

    `text` is nullable because a fact the store can no longer resolve is a state
    the projection already reports as a review reason; a read that raised instead
    would turn an explainable staleness into a 500. `section` is the content
    section whose claims first link it, null for the headline and contacts.
    """

    fact_id: str
    text: str | None = None
    linked_claim_ids: list[str] = []
    section: str | None = None


class BuiltWithView(BoundaryDTO):
    profile_version: str


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
