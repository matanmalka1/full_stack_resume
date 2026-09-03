"""Resume claim, draft-document, and working-draft contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .base import StrictModel
from .selection import OmissionReason, SelectionManifest
from .taxonomy import Emphasis, ProfileName, Track

ClaimStyle = Literal["paragraph", "heading", "date", "bullet", "item", "contact", "headline"]
ClaimType = Literal["canonical", "composite", "derived", "pending", "headline"]


class ClaimLine(StrictModel):
    claim_id: str
    style: ClaimStyle
    text: str
    fact_ids: list[str] = []
    claim_type: ClaimType
    text_hash: str
    template_id: str | None = None
    template_version: str | None = None
    derivation_id: str | None = None
    derivation_version: str | None = None
    pending_reason: str | None = None

    @model_validator(mode="after")
    def validate_template_identity(self) -> ClaimLine:
        has_template = self.template_id is not None or self.template_version is not None
        if self.claim_type == "composite" and not (self.template_id and self.template_version):
            raise ValueError("composite claims require a template ID and version")
        if self.claim_type != "composite" and has_template:
            raise ValueError("only composite claims may identify a template")
        has_derivation = self.derivation_id is not None or self.derivation_version is not None
        if self.claim_type == "derived" and not (self.derivation_id and self.derivation_version):
            raise ValueError("derived claims require a derivation ID and version")
        if self.claim_type != "derived" and has_derivation:
            raise ValueError("only derived claims may identify a derivation contract")
        if self.claim_type == "pending" and not self.pending_reason:
            raise ValueError("pending claims require a reason")
        if self.claim_type != "pending" and self.pending_reason is not None:
            raise ValueError("only pending claims may include a pending reason")
        return self


class ResumeSection(StrictModel):
    name: str
    claims: list[ClaimLine]


class DraftDocument(StrictModel):
    """A draft and the exact chain position it was built from.

    `application_id`, `job_snapshot_id`, and `job_analysis_id` are the binding.
    They are frozen because a draft that can be re-pointed at another owner,
    another job text, or another classification is not evidence of anything: the
    approval, the decision record, and every rendered artifact all inherit their
    provenance from these three fields.

    The schema and fact-store versions are also immutable provenance. The
    content hash remains assignable because controlled edit paths reseal it.

    `job_analysis_id` is absent only on `schema_version` "1.0" manifests, which
    were written before the binding existed. Those are still readable — approved
    versions are immutable and must stay loadable — but their analysis is
    recovered from their own immutable decision record, never from whichever
    analysis happens to be latest.
    """

    schema_version: str = Field(default="1.1", frozen=True)
    application_id: str = Field(frozen=True)
    job_snapshot_id: str = Field(frozen=True)
    job_analysis_id: str | None = Field(default=None, frozen=True)
    language: Literal["en", "he"]
    track: Track
    profile: ProfileName
    emphasis: Emphasis
    name: str
    headline: ClaimLine
    contacts: list[ClaimLine]
    sections: list[ResumeSection]
    selected_fact_ids: list[str]
    omitted_facts: dict[str, OmissionReason] = {}
    selection: SelectionManifest | None = None
    fact_store_version: str = Field(frozen=True)
    content_hash: str = ""

    @model_validator(mode="after")
    def validate_analysis_binding(self) -> DraftDocument:
        if self.schema_version != "1.0" and not self.job_analysis_id:
            raise ValueError("a draft must name the exact job analysis it was built from")
        return self

    @model_validator(mode="after")
    def validate_headline_placement(self) -> DraftDocument:
        body = [*self.contacts, *(claim for section in self.sections for claim in section.claims)]
        if any(claim.claim_type == "headline" or claim.style == "headline" for claim in body):
            raise ValueError("only the document headline may use the headline claim type or style")
        return self


class WorkingDraft(StrictModel):
    """The one mutable resume record for an Application.

    The caller supplies the content hash alongside the structured source, just as it
    does for ``DraftDocument``. Persistence owns optimistic version checks and the
    one-active-draft constraint; the domain record stays storage-neutral.
    """

    id: str
    application_id: str
    job_analysis_id: str
    selection_plan_id: str
    parent_revision_id: str | None = None
    source: DraftDocument
    edit_version: int
    content_hash: str
    active: bool
    created_at: str
    updated_at: str
