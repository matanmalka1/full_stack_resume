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
    """A section's candidate pool, not its output.

    `fact_ids` is everything this section is *allowed* to say; the selection
    policy chooses a subset of it under `max_claims`. `pinned_fact_ids` names
    the non-structural facts that must survive regardless of score — the ones
    that keep a role block from rendering as a heading with no evidence.
    Structural facts (headings, dates, contacts) are pinned implicitly.

    A section budget alone says nothing about how the budget is spread across
    the roles inside it, so a long, senior role can end up with two bullets
    while an older one takes seven. `min_claims_per_role` and
    `min_quantitative_per_role` are floors each role block must reach before
    the rest of the budget is handed out by rank, and `max_claims_per_role` is
    the ceiling that stops one role absorbing what is left: an older role
    carrying seven bullets under a newer one carrying two reads as a career
    running backwards, however the ranking got there.
    """

    name_en: str
    name_he: str
    fact_ids: list[str]
    pinned_fact_ids: list[str] = []
    max_claims: int | None = None
    min_claims_per_role: int = 0
    min_quantitative_per_role: int = 0
    max_claims_per_role: int | None = None
    optional: bool = False

    @model_validator(mode="after")
    def validate_pool(self) -> "ResumeSectionSpec":
        if len(set(self.fact_ids)) != len(self.fact_ids):
            raise ValueError(f"section {self.name_en!r} repeats a candidate fact")
        if self.min_claims_per_role < 0 or self.min_quantitative_per_role < 0:
            raise ValueError(f"section {self.name_en!r} has a negative role-block floor")
        if self.max_claims_per_role is not None:
            ceiling = self.max_claims_per_role
            if ceiling < max(self.min_claims_per_role, self.min_quantitative_per_role):
                raise ValueError(
                    f"section {self.name_en!r} caps a role block below its own floor"
                )
        outside = sorted(set(self.pinned_fact_ids) - set(self.fact_ids))
        if outside:
            raise ValueError(f"section {self.name_en!r} pins facts outside its pool: {outside}")
        if self.max_claims is not None:
            if self.max_claims < 1:
                raise ValueError(f"section {self.name_en!r} has a non-positive claim budget")
            if self.max_claims > len(self.fact_ids):
                raise ValueError(
                    f"section {self.name_en!r} budgets more claims than its pool holds"
                )
        return self


class EmphasisPolicy(StrictModel):
    """How one Emphasis weights the shared canonical tag vocabulary.

    Emphasis is orthogonal to Profile, so its policy lives once here rather than
    being copied into every Profile that allows it. `preferred_tags` is a
    coverage expectation, not a structural invariant: unlike `Profile.required_tags`
    it never forces a fact into the document, it only reports when the selected
    content drifted away from what the Emphasis is supposed to be about.
    """

    emphasis: Emphasis
    tag_weights: dict[str, int]
    preferred_tags: list[str] = []
    minimum_coverage: int = 0

    @model_validator(mode="after")
    def validate_coverage(self) -> "EmphasisPolicy":
        if any(weight < 0 for weight in self.tag_weights.values()):
            raise ValueError(f"emphasis {self.emphasis} has a negative tag weight")
        if self.minimum_coverage > len(self.preferred_tags):
            raise ValueError(
                f"emphasis {self.emphasis} requires more coverage than it has preferred tags"
            )
        return self


class Profile(StrictModel):
    profile_id: str
    version: str
    track: Track
    profile: ProfileName
    default_emphasis: Emphasis
    allowed_emphases: list[Emphasis]
    normalized_role: str
    safe_headlines: list[str]
    # What the CV says under the name. `normalized_role` stays the filing name —
    # the PDF filename and role folder — so a headline written for a reader
    # ("Technical Sales | B2B Sales | Software Background") does not leak into
    # the artifact path.
    headline: str | None = None
    required_tags: list[str] = []
    tag_weights: dict[str, int] = {}
    sections: list[ResumeSectionSpec]
    allow_two_pages: bool = False

    @model_validator(mode="after")
    def validate_default_emphasis(self) -> "Profile":
        if self.default_emphasis not in self.allowed_emphases:
            raise ValueError("default emphasis must be allowed")
        if self.headline is not None and self.headline not in self.safe_headlines:
            raise ValueError("headline must be one of the safe headlines")
        if self.normalized_role not in self.safe_headlines:
            raise ValueError("normalized role must be a safe headline")
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


OmissionReason = Literal[
    "below_section_budget",
    "not_relevant_to_emphasis",
    "evicted_by_required_tag_rescue",
    "not_in_profile_pool",
]

SelectionOutcome = Literal["pinned", "selected", "rescued", "omitted"]


class SelectionCandidate(StrictModel):
    """One fact's full accounting in the selection decision.

    Recorded so a later reader can answer not only which policy ran but why
    fact A beat fact B: the ranking is the lexicographic tuple
    (gap_substitute, semantic_score, keyword_hits, -pool_index).
    """

    fact_id: str
    section: str
    pool_index: int
    profile_score: int
    emphasis_score: int
    semantic_score: int
    keyword_hits: int
    gap_substitute: bool
    outcome: SelectionOutcome
    reason: OmissionReason | None = None


class SelectionManifest(StrictModel):
    """The engine's selection decision, as decided at build time.

    Manual claim edits afterwards do not rewrite this record; they set
    `superseded_by_manual_edit` so the audit trail keeps the original decision
    instead of quietly reshaping itself around the edit.
    """

    policy_version: str
    emphasis: Emphasis
    emphasis_policy_version: str
    candidates: list[SelectionCandidate] = []
    selected_fact_ids: list[str] = []
    required_tag_coverage: dict[str, list[str]] = {}
    preferred_tag_coverage: dict[str, list[str]] = {}
    superseded_by_manual_edit: bool = False


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
    omitted_facts: dict[str, OmissionReason] = {}
    selection: SelectionManifest | None = None
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
