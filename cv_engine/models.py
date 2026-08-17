from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class FactStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANONICAL = "canonical"


class Track(StrEnum):
    DEVELOPMENT = "development"
    SALES = "sales"
    TECH_SALES = "tech-sales"


class ProfileName(StrEnum):
    DEVELOPMENT = "development"
    FIELD_SALES = "field-sales"
    ACCOUNT_MANAGER = "account-manager"
    KEY_ACCOUNT_MANAGER = "key-account-manager"
    SDR_BDR = "sdr-bdr"
    ACCOUNT_EXECUTIVE = "account-executive"
    BUSINESS_DEVELOPMENT = "business-development"
    SALES_MANAGEMENT = "sales-management"
    TECH_SALES = "tech-sales"
    PRE_SALES = "pre-sales-solutions-consultant"


class Emphasis(StrEnum):
    DEVELOPMENT_BALANCED = "development-balanced"
    DEVELOPMENT_BACKEND = "development-backend"
    DEVELOPMENT_AI = "development-ai"
    NEW_BUSINESS = "new-business"
    ACCOUNT_GROWTH = "account-growth"
    LEADERSHIP = "leadership"
    TECH_CONSULTATIVE = "tech-consultative-sales"
    BALANCED_SALES = "balanced-sales"


class FitLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ApplicationStatus(StrEnum):
    SAVED = "saved"
    PREPARING = "preparing"
    READY = "ready"
    APPLIED = "applied"
    RECRUITER_SCREEN = "recruiter_screen"
    INTERVIEW = "interview"
    ASSIGNMENT = "assignment"
    FINAL_STAGE = "final_stage"
    OFFER = "offer"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    CLOSED = "closed"


class Fact(StrictModel):
    fact_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")
    meaning: str = Field(min_length=1)
    renderings: dict[str, str]
    tags: list[str]
    status: FactStatus
    provenance: str = Field(min_length=1)
    confirmed_at: str | None = None
    effective_dates: str | None = None
    replaces: str | None = None
    source_file: str = ""
    resume_style: Literal["paragraph", "heading", "date", "bullet", "item", "contact"]

    @model_validator(mode="after")
    def require_english_rendering(self) -> "Fact":
        if not self.renderings.get("en"):
            raise ValueError("every fact requires an English rendering")
        return self


class FactSource(StrictModel):
    source_version: str
    facts: list[Fact]


class ResumeSectionSpec(StrictModel):
    name_en: str
    name_he: str
    fact_ids: list[str]
    optional: bool = False


class Profile(StrictModel):
    profile_id: str
    version: str
    track: Track
    profile: ProfileName
    default_emphasis: Emphasis
    allowed_emphases: list[Emphasis]
    normalized_role: str
    safe_headlines: list[str]
    required_tags: list[str] = []
    tag_weights: dict[str, int] = {}
    sections: list[ResumeSectionSpec]
    allow_two_pages: bool = False

    @model_validator(mode="after")
    def validate_default_emphasis(self) -> "Profile":
        if self.default_emphasis not in self.allowed_emphases:
            raise ValueError("default emphasis must be allowed")
        return self


class Gap(StrictModel):
    requirement: str
    severity: Literal["warning", "hard"]
    reason: str
    substitute_fact_ids: list[str] = []


class JobClassificationProposal(StrictModel):
    """What an AI provider is allowed to propose for `classify_job`.

    Deliberately narrower than `JobAnalysis`: the fields that route safety
    decisions — language, Fit, approval, requirements, overrides, analysis
    version — are absent, so a provider cannot express them at all. Adding a new
    safety field to `JobAnalysis` therefore keeps it out of provider reach by
    default instead of relying on a merge whitelist staying up to date.
    """

    track: Track
    profile: ProfileName
    emphasis: Emphasis
    confidence: float = Field(ge=0, le=1)
    rationale: str
    gaps: list[Gap]
    keywords: list[str]


class JobAnalysis(StrictModel):
    analysis_version: str = "1.0"
    track: Track
    profile: ProfileName
    emphasis: Emphasis
    confidence: float = Field(ge=0, le=1)
    deterministic_confidence: float | None = Field(default=None, ge=0, le=1)
    proposal_confidence: float | None = Field(default=None, ge=0, le=1)
    rationale: str
    fit: FitLevel
    gaps: list[Gap]
    mandatory_requirements: list[str]
    preferred_requirements: list[str]
    keywords: list[str]
    language: Literal["en", "he"]
    classification_requires_approval: bool = False
    approval_reasons: list[str] = []
    user_override: dict[str, str] = {}


class ClaimLine(StrictModel):
    claim_id: str
    style: Literal["paragraph", "heading", "date", "bullet", "item", "contact", "headline"]
    text: str
    fact_ids: list[str] = []
    claim_type: Literal["canonical", "composite", "derived", "pending", "headline"]
    text_hash: str
    template_id: str | None = None
    template_version: str | None = None
    derivation_id: str | None = None
    derivation_version: str | None = None
    pending_reason: str | None = None

    @model_validator(mode="after")
    def validate_template_identity(self) -> "ClaimLine":
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
    schema_version: str = "1.0"
    application_id: str
    job_snapshot_id: str
    language: Literal["en", "he"]
    track: Track
    profile: ProfileName
    emphasis: Emphasis
    name: str
    headline: ClaimLine
    contacts: list[ClaimLine]
    sections: list[ResumeSection]
    selected_fact_ids: list[str]
    omitted_facts: dict[str, str] = {}
    fact_store_version: str
    content_hash: str = ""

    @model_validator(mode="after")
    def validate_headline_placement(self) -> "DraftDocument":
        body = [*self.contacts, *(claim for section in self.sections for claim in section.claims)]
        if any(claim.claim_type == "headline" or claim.style == "headline" for claim in body):
            raise ValueError("only the document headline may use the headline claim type or style")
        return self


class ValidationIssue(StrictModel):
    group: str
    code: str
    message: str
    hard: bool = True


class ValidationReport(StrictModel):
    passed: bool
    groups: dict[str, bool]
    issues: list[ValidationIssue] = []
    evidence: dict[str, Any] = {}


class ProviderContext(StrictModel):
    provider: str
    model: str
    task_contract_version: str
    prompt_version: str


class ProviderTaskResult(StrictModel):
    task: str
    output: dict[str, Any]
    context: ProviderContext
    raw_output_hash: str
