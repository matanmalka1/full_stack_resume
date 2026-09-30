"""Resume claim, draft-document, and working-draft contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .base import StrictModel
from .taxonomy import Emphasis, ProfileName, Track

ClaimStyle = Literal["paragraph", "heading", "date", "bullet", "item", "contact", "headline"]
ClaimType = Literal["canonical", "composite", "derived", "reviewed", "pending", "headline"]


class ClaimReviewAssertion(StrictModel):
    claim_quote: str = Field(min_length=1)
    fact_ids: list[str]
    source_quotes: list[str]


class ClaimReviewEvidence(StrictModel):
    policy_version: str = Field(min_length=1)
    provider_artifact_version_id: str = Field(min_length=1)
    input_hash: str = Field(min_length=1)
    assertions: list[ClaimReviewAssertion]


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
    review_evidence: ClaimReviewEvidence | None = None

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
        if self.claim_type == "reviewed" and self.review_evidence is None:
            raise ValueError("reviewed claims require semantic review evidence")
        if self.claim_type != "reviewed" and self.review_evidence is not None:
            raise ValueError("only reviewed claims may include semantic review evidence")
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

    There is no compatibility shape: the database starts empty, so accepting a
    manifest without its analysis binding would preserve no real record and would
    weaken the provenance contract for every caller.
    """

    schema_version: Literal["1.2"] = Field(default="1.2", frozen=True)
    application_id: str = Field(frozen=True)
    job_snapshot_id: str = Field(frozen=True)
    job_analysis_id: str = Field(min_length=1, frozen=True)
    language: Literal["en", "he"]
    track: Track
    profile: ProfileName
    emphasis: Emphasis
    name: str
    headline: ClaimLine
    contacts: list[ClaimLine]
    sections: list[ResumeSection]
    fact_store_version: str = Field(frozen=True)
    content_hash: str = ""

    @model_validator(mode="after")
    def validate_headline_placement(self) -> DraftDocument:
        body = [*self.contacts, *(claim for section in self.sections for claim in section.claims)]
        if any(claim.claim_type == "headline" or claim.style == "headline" for claim in body):
            raise ValueError("only the document headline may use the headline claim type or style")
        return self
