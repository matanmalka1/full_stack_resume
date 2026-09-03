from __future__ import annotations

from collections import Counter
from enum import StrEnum
from typing import Any, Literal, Self

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
    #: Requirements could not be read, so Fit was never assessed. Distinct from
    #: MEDIUM, which claims an assessment was made and landed in the middle.
    #: Only a *new* analysis run whose extraction failed may carry it; analyses
    #: stored before the extractor existed keep the Fit they were written with.
    UNKNOWN = "unknown"


class ApplicationStatus(StrEnum):
    SAVED = "saved"
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


class TerminalOutcome(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


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
    # The absolute address a rendering stands for, where the rendering is
    # display text rather than the address itself: "linkedin.com/in/..." is
    # what a CV shows, "https://www.linkedin.com/in/..." is what the link must
    # point at. Declaring it here keeps the address in the fact's one canonical
    # location instead of a second copy beside it.
    link_target: str | None = None

    @model_validator(mode="after")
    def require_english_rendering(self) -> Fact:
        if not self.renderings.get("en"):
            raise ValueError("every fact requires an English rendering")
        return self

    @model_validator(mode="after")
    def link_target_carries_the_rendering(self) -> Fact:
        """A declared address must still be the one the fact displays.

        Without this the two halves of the same fact can drift apart and the
        CV shows one profile while linking to another.
        """
        if self.link_target is None:
            return self
        if not self.link_target.startswith("https://"):
            raise ValueError(f"link target is not https: {self.link_target}")
        if self.renderings["en"] not in self.link_target:
            raise ValueError(
                f"link target {self.link_target} does not carry the fact's "
                f"English rendering {self.renderings['en']!r}"
            )
        return self


class FactSource(StrictModel):
    source_version: str
    facts: list[Fact]

    @model_validator(mode="after")
    def require_unique_fact_ids(self) -> FactSource:
        duplicates = sorted(
            fact_id
            for fact_id, count in Counter(fact.fact_id for fact in self.facts).items()
            if count > 1
        )
        if duplicates:
            raise ValueError(f"fact source repeats fact IDs: {duplicates}")
        return self


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
    def validate_pool(self) -> ResumeSectionSpec:
        if len(set(self.fact_ids)) != len(self.fact_ids):
            raise ValueError(f"section {self.name_en!r} repeats a candidate fact")
        if self.min_claims_per_role < 0 or self.min_quantitative_per_role < 0:
            raise ValueError(f"section {self.name_en!r} has a negative role-block floor")
        if self.max_claims_per_role is not None:
            ceiling = self.max_claims_per_role
            if ceiling < max(self.min_claims_per_role, self.min_quantitative_per_role):
                raise ValueError(f"section {self.name_en!r} caps a role block below its own floor")
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
    minimum_coverage: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_coverage(self) -> EmphasisPolicy:
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
    # The dated roles this Profile deliberately does not offer, each against the
    # reason it does not. Employment-history coverage is checked against the
    # fact store, so a dated role that is neither offered nor named here fails
    # the profile set instead of quietly vanishing from the CV. A waiver records
    # a decision about the head or tail of the timeline; it cannot buy off a
    # hole between two roles the Profile does offer.
    omitted_roles: dict[str, str] = {}
    sections: list[ResumeSectionSpec]
    allow_two_pages: bool = False

    @model_validator(mode="after")
    def validate_default_emphasis(self) -> Profile:
        if self.default_emphasis not in self.allowed_emphases:
            raise ValueError("default emphasis must be allowed")
        if self.headline is not None and self.headline not in self.safe_headlines:
            raise ValueError("headline must be one of the safe headlines")
        if self.normalized_role not in self.safe_headlines:
            raise ValueError("normalized role must be a safe headline")
        return self

    @model_validator(mode="after")
    def validate_omitted_role_reasons(self) -> Profile:
        """A declined role states why, so the waiver records a decision.

        Without this the reason is decoration: `{"role": ""}` would satisfy the
        coverage rule and leave the omission as unexplained as never declaring
        it. An empty string is what an absent-minded edit produces, which is
        precisely the case the waiver list exists to catch.
        """
        blank = sorted(
            fact_id for fact_id, reason in self.omitted_roles.items() if not reason.strip()
        )
        if blank:
            raise ValueError(f"omitted roles need a reason: {', '.join(blank)}")
        return self


ContactScheme = Literal["text", "mailto", "tel", "https"]


class CandidateContext(StrictModel):
    """Who this application is about, expressed as references rather than literals.

    The candidate's name and contacts stay canonical facts with one location.
    This context only says which fact plays which role, how a contact becomes a
    link, and how the recruiter-facing filename is built, so no renderer,
    validator, or filename policy contains a candidate literal.

    `names`, `link_targets`, and `resolved_filename_name` are resolved from the
    canonical facts at load time. They are a projection of those facts, never a
    second place to edit them.
    """

    context_version: str
    name_fact_id: str
    filename_name: str | None = None
    filename_language: Literal["en", "he"] = "en"
    locale: str
    timezone: str
    contact_fact_ids: list[str]
    track_contact_fact_ids: dict[str, list[str]] = {}
    link_schemes: dict[str, ContactScheme] = {}
    # `mailto`/`tel` addresses are the fact's own rendering. A profile URL is
    # not: its canonical rendering is display text ("linkedin.com/in/..."), so
    # the absolute target lives on the fact as `link_target` and is resolved
    # into this projection at load time. The context decides which scheme wraps
    # a contact; it never carries a second copy of the address.
    link_targets: dict[str, str] = {}
    names: dict[str, str] = {}
    resolved_filename_name: str = ""
    version_hash: str = ""

    def contacts_for_track(self, track: str) -> list[str]:
        extra = [
            fact_id
            for fact_id in self.track_contact_fact_ids.get(track, [])
            if fact_id not in self.contact_fact_ids
        ]
        return [*self.contact_fact_ids, *extra]

    def display_name(self, language: str) -> str:
        try:
            return self.names[language]
        except KeyError as exc:
            raise ValueError(
                f"candidate fact {self.name_fact_id} has no {language!r} rendering"
            ) from exc

    def scheme(self, fact_id: str) -> ContactScheme:
        return self.link_schemes.get(fact_id, "text")


RequirementKind = Literal["threshold", "compositional", "presence"]
Coverage = Literal["matched", "partial", "unsupported"]


class MissingComponent(StrictModel):
    """One named part of a requirement canonical Knowledge cannot establish.

    Structured rather than a prose sentence: what is missing is matched on and
    reasoned about, so it must not become free text the engine later depends on
    parsing. Human-readable explanation is rendered from `label` at the edge,
    and from a boundary fact's own `meaning` where one gives the authoritative
    account.
    """

    component_id: str
    label: str
    demanded: str | None = None


class Requirement(StrictModel):
    """One thing the employer asked for, and what we can truthfully show for it.

    `coverage` is about the requirement being met. `supporting_fact_ids` is
    about evidence existing. They are independent: a demanded proficiency the
    candidate falls short of is `unsupported` and still lists the canonical
    fact carrying the lower value.

    `supporting_fact_ids` records evidence. It never licenses a merged or
    strengthened claim - a fact listed here because it is adjacent to the
    requirement must not be drafted as if it satisfied it. `boundary_fact_ids`
    names the canonical facts that say so explicitly.
    """

    requirement_id: str
    text: str
    kind: RequirementKind
    concept: str | None = None
    mandatory: bool
    coverage: Coverage
    supporting_fact_ids: list[str] = []
    boundary_fact_ids: list[str] = []
    missing_components: list[MissingComponent] = []


class Gap(StrictModel):
    requirement: str
    severity: Literal["warning", "hard"]
    reason: str
    substitute_fact_ids: list[str] = []
    #: The `Requirement` this gap projects, when one produced it. Absent on
    #: analyses written before requirement coverage existed, whose stored gaps
    #: stay authoritative exactly as recorded.
    requirement_id: str | None = None


OverrideKey = Literal["track", "profile", "emphasis", "language", "fit", "analysis"]
Language = Literal["en", "he"]


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
    #: The complete requirement picture, matched requirements included. `gaps`
    #: is its unmet projection. Defaulted so analyses stored before requirement
    #: coverage existed - including those bound to approved and submitted
    #: revisions - keep deserializing unchanged.
    requirements: list[Requirement] = []
    #: Which extractor produced `requirements`. "0" marks a legacy analysis
    #: whose stored `gaps` are authoritative and are never re-derived.
    extraction_version: str = "0"
    mandatory_requirements: list[str]
    preferred_requirements: list[str]
    keywords: list[str]
    language: Literal["en", "he"]
    classification_requires_approval: bool = False
    approval_reasons: list[str] = []
    user_override: dict[OverrideKey, str] = {}


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


OmissionReason = Literal[
    "below_section_budget",
    "not_relevant_to_emphasis",
    "evicted_by_required_tag_rescue",
    "not_in_profile_pool",
    # A user's explicit exclusion, carried in the review form that created this
    # plan. Recorded rather than dropped: a fact the engine ranked out and a
    # fact the user removed are different decisions, and the candidate
    # accounting is the only place that can still tell them apart.
    "excluded_by_user",
]

SelectionOutcome = Literal["pinned", "selected", "rescued", "omitted"]


class SelectionCandidate(StrictModel):
    """One fact's full accounting in the selection decision.

    Recorded so a later reader can answer not only which policy ran but why
    fact A beat fact B: the ranking is the lexicographic tuple
    (requirement_rank, semantic_score, keyword_hits, -pool_index).

    `requirement_rank` is 2 where the fact bears on a mandatory requirement, 1
    for a preferred one, 0 where the posting never asked. `gap_substitute` held
    that slot under policy 1.0.0 and is still recorded: it says something the
    tier does not - that the fact was offered as a stand-in for something
    missing rather than as evidence of something held - and manifests already
    written carry it. Reading either field on an older record means reading
    `policy_version` first.
    """

    fact_id: str
    section: str
    pool_index: int
    profile_score: int
    emphasis_score: int
    semantic_score: int
    keyword_hits: int
    gap_substitute: bool
    #: Defaulted so manifests written under policy 1.0.0, including those bound
    #: to approved and submitted revisions, keep deserializing unchanged, and
    #: bounded because the tier is an enumeration the ranking reads, not a
    #: score: a value outside 0..2 would sort against every real tier while
    #: describing nothing, and the published schema would promise an unbounded
    #: integer no reader of a manifest could interpret.
    requirement_rank: int = Field(default=0, ge=0, le=2)
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


class AcceptedGap(StrictModel):
    """One hard gap the user knowingly proceeded past.

    Acceptance means only that: it never changes a gap to satisfied, never
    authorizes an unsupported claim, and never touches requirement coverage or
    fact ranking. It is recorded per gap, keyed on the `Requirement` the gap
    projects, so accepting one deficiency cannot dismiss another the user has
    not seen.

    It lives on the SelectionPlan rather than the JobAnalysis because it is not
    a change to what the requirement *means* - the analysis is untouched and
    stays reusable - only to whether the user proceeds despite it.
    """

    requirement_id: str
    job_analysis_id: str
    actor: str
    accepted_at: str
    reason: str | None = None


def merge_accepted_gaps(previous: list[AcceptedGap], new: list[AcceptedGap]) -> list[AcceptedGap]:
    """Carry the standing acceptances forward and add the new ones.

    Accumulating rather than replacing is what makes a second decision not a
    silent retraction of the first. A requirement already accepted keeps its
    original record: the acceptance happened when it happened, and re-stamping
    it would lose that.
    """
    already = {accepted.requirement_id for accepted in previous}
    return [*previous, *(item for item in new if item.requirement_id not in already)]


class SelectionPlan(StrictModel):
    """One immutable, versioned fact-selection decision for an analysis."""

    id: str
    application_id: str
    job_analysis_id: str
    version_number: int
    plan: SelectionManifest
    #: The gaps the user knowingly proceeded past, as of this plan version.
    #: Defaulted so plans stored before per-gap acceptance existed - including
    #: those bound to approved and submitted revisions - keep loading unchanged.
    accepted_gaps: list[AcceptedGap] = []

    @model_validator(mode="after")
    def acceptances_belong_to_this_analysis(self) -> SelectionPlan:
        """An acceptance names the analysis it was made against, and it must be
        this one.

        Acceptance is a decision about *these* gaps, as this analysis stated
        them. A plan carrying an acceptance made against a different analysis
        would report a decision the user never made about the requirements it
        actually holds. Enforced on the model rather than in the writer, so it
        covers every path that has ever written a plan and every one that will.
        """
        foreign = sorted(
            {
                accepted.requirement_id
                for accepted in self.accepted_gaps
                if accepted.job_analysis_id != self.job_analysis_id
            }
        )
        if foreign:
            raise ValueError(
                f"selection plan for analysis {self.job_analysis_id} carries acceptances "
                f"made against another analysis: {', '.join(foreign)}"
            )
        return self

    candidate_context_version: str
    candidate_context_hash: str
    profile_version: str
    selection_policy_version: str
    track_emphasis_dependencies: dict[str, str]
    created_at: str


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


class ApprovedRevision(StrictModel):
    """One immutable approved resume and its complete frozen lineage.

    Payload references are opaque project-relative identities. The domain
    record neither composes nor opens them; infrastructure owns that policy.
    """

    id: str
    application_id: str
    version_number: int
    job_snapshot_id: str
    job_analysis_id: str
    selection_plan_id: str
    working_draft_id: str
    draft_edit_version: int
    draft_content_hash: str
    resume_json_reference: str
    resume_json_hash: str
    resume_markdown_reference: str
    resume_markdown_hash: str
    candidate_context_version: str
    candidate_context_hash: str
    facts_version: str
    knowledge_context_hash: str
    profile_version: str
    selection_policy_version: str
    track_emphasis_dependencies: dict[str, str]
    validation_run_id: str
    validator_versions: dict[str, str]
    decision_provenance: dict[str, str]
    approved_at: str


class DecisionRecord(StrictModel):
    """The immutable approval decision stored beside an approved artifact."""

    id: str
    application_id: str
    artifact_version_id: str
    job_snapshot_id: str
    job_analysis_id: str
    structured: dict[str, Any]
    summary: str
    created_at: str


class AuditRecord(StrictModel):
    """One immutable local actor record for an application-layer decision."""

    id: str
    application_id: str
    action: str
    entity_type: str
    entity_id: str
    actor_type: Literal["user", "system"]
    client: Literal["web", "worker"]
    occurred_at: str
    details: dict[str, Any] = {}


class ValidationRunLineage(StrictModel):
    """Exact mutable-draft and frozen-context inputs validated by one run."""

    working_draft_id: str
    edit_version: int
    content_hash: str
    job_snapshot_id: str
    job_analysis_id: str
    selection_plan_id: str
    knowledge_context_hash: str
    validator_versions: dict[str, str]


class ValidationIssue(StrictModel):
    group: str
    code: str
    message: str
    hard: bool = True


class ValidationReport(StrictModel):
    report_schema_version: str | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    passed: bool
    groups: dict[str, bool]
    issues: list[ValidationIssue] = []
    evidence: dict[str, Any] = {}

    @classmethod
    def from_findings(
        cls,
        groups: dict[str, bool],
        issues: list[ValidationIssue],
        *,
        evidence: dict[str, Any] | None = None,
    ) -> Self:
        """Build a report whose pass result is derived from its findings."""
        return cls(
            report_schema_version="2.0",
            passed=all(groups.values()) and not any(issue.hard for issue in issues),
            groups=groups,
            issues=issues,
            evidence=evidence if evidence is not None else {},
        )

    @model_validator(mode="after")
    def passed_agrees_with_findings(self) -> ValidationReport:
        if not self.passed:
            return self
        failed_groups = sorted(group for group, passed in self.groups.items() if not passed)
        if failed_groups:
            raise ValueError(f"report claims to have passed with failed groups: {failed_groups}")
        hard_issues = sorted({issue.code for issue in self.issues if issue.hard})
        if hard_issues:
            raise ValueError(f"report claims to have passed with hard failures: {hard_issues}")
        return self


class ReadyQualification(StrictModel):
    """Current integrity projection for one immutable approved revision."""

    application_id: str
    approved_revision_id: str
    pdf_artifact_version_id: str | None = None
    html_artifact_version_id: str | None = None
    ready_qualified: bool
    validation: ValidationReport

    @model_validator(mode="after")
    def qualification_agrees_with_evidence(self) -> ReadyQualification:
        if self.ready_qualified != self.validation.passed:
            raise ValueError("ready_qualified must be derived from its validation evidence")
        if self.ready_qualified and self.pdf_artifact_version_id is None:
            raise ValueError("ready_qualified requires an exact PDF artifact version")
        if self.ready_qualified and self.html_artifact_version_id is None:
            raise ValueError("ready_qualified requires an exact HTML artifact version")
        return self


class ProposedClaim(StrictModel):
    """One line a provider proposes, with the facts it says support it.

    `fact_ids` is not proof. A valid ID paired with strengthened wording is the
    failure mode invariant 12 names, so every proposed line still passes the
    same semantic support check a manual edit passes; the IDs only say which
    facts the check is run against.
    """

    section: str
    claim_id: str | None = None
    text: str
    fact_ids: list[str] = []


class SelectionProposal(StrictModel):
    """`propose_selection_plan`: an overlay on the deterministic selection.

    Deliberately expressed as the same two lists a user's review form submits,
    because activation replays the identical deterministic `build_selection`.
    A provider that could return a finished plan could express a selection the
    engine would never make; a provider that returns an overlay cannot.
    """

    pinned_fact_ids: list[str] = []
    excluded_fact_ids: list[str] = []
    rationale: str


class DraftProposal(StrictModel):
    """`draft_resume`: proposed wording for a draft the engine composed."""

    claims: list[ProposedClaim]
    rationale: str


class SectionProposal(StrictModel):
    """`regenerate_section`: proposed wording for one named section."""

    section: str
    claims: list[ProposedClaim]
    rationale: str


class ClaimProposal(StrictModel):
    """`regenerate_claim`: proposed wording for one named claim."""

    claim_id: str
    text: str
    fact_ids: list[str]
    rationale: str


class ProviderUsage(StrictModel):
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ProviderPricing(StrictModel):
    currency: Literal["USD"] = "USD"
    version: str
    source: str
    input_per_million_usd: str
    cached_input_per_million_usd: str
    output_per_million_usd: str
    long_context_threshold_tokens: int
    long_context_input_multiplier: str
    long_context_output_multiplier: str


class ProviderCost(StrictModel):
    currency: Literal["USD"] = "USD"
    input_usd: str
    output_usd: str
    total_usd: str


class ProviderContext(StrictModel):
    """Exactly what ran, recorded on every provider execution (architecture §11).

    No field here can hold a credential. The key is environment configuration
    that never enters a record, request headers are never captured, and hidden
    reasoning content is never requested or retained - so what is stored is
    the execution's identity and effort setting, not hidden reasoning.
    """

    provider: str
    model: str
    reasoning_effort: str | None = None
    task_contract_version: str
    prompt_version: str
    prompt_hash: str
    system_version: str
    # Architecture §11 requires the input and output schema versions alongside
    # the contract and prompt versions. The declared version is the label the
    # contract file states; the hash is computed from the actual Pydantic schema
    # at call time, so a schema that changes without its version moving is
    # visible in the record rather than only in a diff. Same pairing the prompt
    # already uses, for the same reason.
    input_schema_version: str
    input_schema_hash: str
    output_schema_version: str
    output_schema_hash: str
    response_id: str | None = None
    usage: ProviderUsage = ProviderUsage()
    pricing: ProviderPricing | None = None
    cost: ProviderCost | None = None
    latency_ms: int = 0


class ProviderTaskResult(StrictModel):
    """One provider execution's provenance, and the sanitized bytes to preserve.

    `sanitized_response` is the payload the application commits as an immutable
    artifact; `raw_output_hash` is its hash, and `output_hash` is the hash of
    the parsed output that entered the Proposal. Two hashes because they answer
    two questions: what the provider sent, and what the engine acted on.
    """

    task: str
    output: dict[str, Any]
    context: ProviderContext
    input_hash: str
    output_hash: str
    raw_output_hash: str
    sanitized_response: str
