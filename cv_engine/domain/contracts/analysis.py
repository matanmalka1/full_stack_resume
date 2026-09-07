"""Job requirement, classification, and fit-analysis contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from .base import StrictModel
from .taxonomy import Emphasis, ProfileName, Track


class FitLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    #: Requirements could not be read, so Fit was never assessed. Distinct from
    #: MEDIUM, which claims an assessment was made and landed in the middle.
    #: Only a *new* analysis run whose extraction failed may carry it; analyses
    #: stored before the extractor existed keep the Fit they were written with.
    UNKNOWN = "unknown"


RequirementKind = Literal["threshold", "compositional", "presence"]
Coverage = Literal["matched", "partial", "unsupported", "undetermined"]

#: What kind of statement a requirement's source text actually is. A
#: `mandatory` obligation is refused when this is not `requirement`, unless a
#: mandatory marker is quoted in `context_quote` - see `interpretation.py`.
SourceRole = Literal["requirement", "responsibility", "company-description", "benefit", "other"]
Obligation = Literal["mandatory", "preferred", "unspecified"]
#: `any-of` is one requirement satisfied by any one member; `all-of` checks
#: each member independently, the way `ConceptComponent` already does.
Composition = Literal["single", "any-of", "all-of"]


class RequirementAttestation(StrictModel):
    """The source gate's proof: offsets into the signed snapshot text as read
    from the payload store, and the quote they are supposed to name.

    A gate failure is not represented here - it is a rejected proposal, never
    a partially-populated attestation. When this is present, `quote` was
    already verified to equal `text[start:end]` in the exact snapshot string.
    """

    quote: str
    start: int
    end: int


class RequirementMember(StrictModel):
    """One member of an `any-of`/`all-of` requirement.

    `label` is display text a provider proposes; it is never used to decide
    coverage. `attestation`, when present, is what a member is actually
    mapped against - the same verified-quote mechanism the requirement itself
    uses (stage-1 plan §3.5a addendum) - because a bare label is exactly as
    unverifiable as a requirement's own text would be without a source gate.
    A member with no attestation, or one that fails verification, cannot be
    mapped to a concept and stays `undetermined`.
    """

    member_id: str
    label: str
    attestation: RequirementAttestation | None = None


class RequirementInterpretation(StrictModel):
    """A provider's declared reading of one requirement. All-or-nothing: a
    `Requirement` either carries a complete interpretation or none at all -
    see `interpretation_of()` in `requirements/compat.py` for why a legacy
    record's absence of these fields is never filled in with a default.
    """

    source_role: SourceRole
    obligation: Obligation
    composition: Composition
    members: list[RequirementMember] = []
    negation: bool
    #: The quoted heading or surrounding sentence the interpretation leans on,
    #: when it leans on one. Verified by the source gate like any other quote.
    context_quote: str | None = None


class UnmappedStatement(StrictModel):
    """A requirement-bearing statement no proposed requirement covers.

    Explicit rather than inferred from the gap between total statements and
    covered ones: an extractor that lists why it left something unmapped can
    be graded on the reason, and a false "company-description" excuse is
    something a reviewer can actually see and dispute.
    """

    start: int
    end: int
    text: str
    source_role: SourceRole
    reason: str


class UnderstandingSources(StrictModel):
    """Where credit for reading a requirement-bearing statement came from.

    Three counts, not one `understood_elsewhere: bool`: a bool answers
    "was anything understood" but not "by what", and attributing a failure
    needs to know which of concepts, legacy rules, or an AI proposal did the
    reading - or that none of them did.
    """

    by_concepts: int
    by_rules: int
    by_ai: int


class InterpretationOverride(StrictModel):
    """One user-submitted correction to a requirement's interpretation (§3.5).

    Submitted through `apply_analysis_decisions` like any other classification
    decision. `prior_requirement_id` names the requirement, on the analysis
    being decided on, whose interpretation the user is correcting - not a
    requirement id on some other analysis, since identity is scoped to one
    analysis's snapshot and extractor namespace.
    """

    prior_requirement_id: str
    interpretation: RequirementInterpretation
    #: Required to re-derive coverage when the corrected requirement is a
    #: `threshold` concept - the demanded value is not stored on `Requirement`
    #: itself, only computed at extraction time, so a correction that changes
    #: a threshold's interpretation must resupply it explicitly or coverage
    #: cannot be recomputed at all.
    demanded: str | None = None
    reason: str | None = None


class InterpretationDecision(StrictModel):
    """One correction recorded when an analysis revision changes what a prior
    requirement's interpretation was decided to mean (§3.5 of the stage-1 plan).
    """

    prior_requirement_id: str
    prior_analysis_id: str
    interpretation: RequirementInterpretation
    actor: str
    decided_at: str
    reason: str | None = None


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
    #: None = this record was written before the interpretation gate existed.
    #: Not "single, not negated" - that would be inventing a value the record
    #: never carried. Read through `interpretation_of()`, never directly.
    interpretation: RequirementInterpretation | None = None
    #: None = this record carries no attestation; do not infer which
    #: extractor produced it from that absence.
    attestation: RequirementAttestation | None = None
    #: None = this record predates the extractor namespace introduced with
    #: the interpretation gate.
    extractor: str | None = None


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
    #: "1.1" carries `interpretation`/`attestation`/`understanding`/
    #: `unmapped_statements`; "1.0" and unset predate them and read as `None`
    #: through the explicit version adapter, never as an invented default.
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
    #: None = this analysis never asked the completeness question (predates
    #: the interpretation gate). [] = it asked, and found no unmapped
    #: requirement-bearing statement. The distinction is deliberate: an empty
    #: list is a finding, not a missing question.
    unmapped_statements: list[UnmappedStatement] | None = None
    understanding: UnderstandingSources | None = None
    interpretation_decisions: list[InterpretationDecision] | None = None
    mandatory_requirements: list[str]
    preferred_requirements: list[str]
    keywords: list[str]
    language: Literal["en", "he"]
    classification_requires_approval: bool = False
    approval_reasons: list[str] = []
    user_override: dict[OverrideKey, str] = {}
