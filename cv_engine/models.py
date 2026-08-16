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


class JobAnalysis(StrictModel):
    analysis_version: str = "1.0"
    track: Track
    profile: ProfileName
    emphasis: Emphasis
    confidence: float = Field(ge=0, le=1)
    rationale: str
    fit: FitLevel
    gaps: list[Gap]
    mandatory_requirements: list[str]
    preferred_requirements: list[str]
    keywords: list[str]
    language: Literal["en", "he"]
    classification_requires_approval: bool = False
    user_override: dict[str, str] = {}


class ClaimLine(StrictModel):
    claim_id: str
    style: Literal["paragraph", "heading", "date", "bullet", "item", "contact", "headline"]
    text: str
    fact_ids: list[str] = []
    claim_type: Literal["canonical", "derived", "headline"]
    text_hash: str


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
