"""Job requirement, classification, and fit-analysis contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from .analysis_proposal import AnalysisIssue, RequirementSource
from .base import StrictModel
from .taxonomy import Emphasis, ProfileName, Track


class FitLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    #: Requirements could not be read, so Fit was never assessed. Distinct from
    #: MEDIUM, which claims an assessment was made and landed in the middle.
    #: An extraction failure may carry it rather than claiming an assessment.
    UNKNOWN = "unknown"


RequirementKind = Literal["threshold", "compositional", "presence"]
Coverage = Literal["matched", "partial", "unsupported", "undetermined"]

#: What kind of statement a requirement's source text actually is. A
#: `mandatory` obligation is refused when this is not `requirement`, unless a
#: mandatory marker is quoted in `context_quote` - see `interpretation.py`.
SourceRole = Literal["requirement", "responsibility", "company-description", "benefit", "other"]
Obligation = Literal["mandatory", "preferred", "unspecified"]
#: `any-of` is one requirement satisfied by any one member; `all-of` checks
#: each member independently.
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
    A member with no attestation cannot retain inspectable source evidence and
    stays `undetermined`.
    """

    member_id: str
    label: str
    attestation: RequirementAttestation | None = None


class RequirementInterpretation(StrictModel):
    """A provider's declared reading of one requirement. All-or-nothing: a
    `Requirement` either carries a complete interpretation or none at all -
    `unspecified` and absent member attestations preserve uncertainty explicitly.
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
    """How many independently segmented demands the AI extraction covered."""

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
    #: threshold requirement - the demanded value is not stored on `Requirement`
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
    mandatory: bool
    coverage: Coverage
    supporting_fact_ids: list[str] = []
    boundary_fact_ids: list[str] = []
    missing_components: list[MissingComponent] = []
    #: None means the extractor could not establish an interpretation.
    interpretation: RequirementInterpretation | None = None
    #: None means no verified source attestation was established.
    attestation: RequirementAttestation | None = None
    #: None is used only for an engine-synthesized unmapped requirement.
    extractor: str | None = None
    #: How the posting was found to carry this requirement's text. `attestation`
    #: can only hold a single exact span, so it cannot express "the posting says
    #: this in two places" or "says it wrapped differently" - both verified, and
    #: both spanless. Absent on records written before this field existed.
    source: RequirementSource | None = None


class Gap(StrictModel):
    requirement: str
    severity: Literal["warning", "hard"]
    reason: str
    substitute_fact_ids: list[str] = []
    #: The `Requirement` this gap projects and an acceptance names.
    requirement_id: str


OverrideKey = Literal["track", "profile", "emphasis", "language", "fit", "analysis"]
Language = Literal["en", "he"]


class JobClassificationProposal(StrictModel):
    """What the classification provider is allowed to propose.

    Deliberately narrower than `JobAnalysis`: the fields that route safety
    decisions — Fit, approval, requirements, overrides, analysis
    version — are absent, so a provider cannot express them at all. Adding a new
    safety field to `JobAnalysis` therefore keeps it out of provider reach by
    default instead of relying on a merge whitelist staying up to date.
    """

    track: Track
    profile: ProfileName
    emphasis: Emphasis
    language: Language
    confidence: float = Field(ge=0, le=1)
    rationale: str
    keywords: list[str]


class JobAnalysis(StrictModel):
    analysis_version: Literal["2.0"] = "2.0"
    track: Track
    profile: ProfileName
    emphasis: Emphasis
    #: The provider's own confidence in the *classification*, when it reported
    #: one. `None` where nothing reported it: the field says how sure the
    #: provider was about Track/Profile/Emphasis, so no other number may be
    #: substituted into it, and a stand-in would be projected as
    #: `classification_confidence` and read as if it meant that.
    confidence: float | None = Field(default=None, ge=0, le=1)
    rationale: str
    fit: FitLevel
    #: The canonical numeric fit measure `fit` is read off (`fit_level_from_score`,
    #: `domain/analysis/gaps.py`): a weighted fraction of requirement coverage,
    #: mandatory-weighted, with `undetermined` counted at zero credit rather than
    #: excluded - so an incompletely assessed posting cannot outscore a fully
    #: assessed one. `None` only when nothing was assessed at all (no requirements,
    #: or extraction failed).
    fit_score: float | None = Field(default=None, ge=0, le=1)
    gaps: list[Gap]
    requirements: list[Requirement]
    extraction_version: str
    unmapped_statements: list[UnmappedStatement]
    understanding: UnderstandingSources
    interpretation_decisions: list[InterpretationDecision] = []
    mandatory_requirements: list[str]
    preferred_requirements: list[str]
    keywords: list[str]
    language: Literal["en", "he"]
    approval_reasons: list[str] = []
    user_override: dict[OverrideKey, str] = {}
    #: Where this reading was narrowed: a citation dropped, a coverage lowered,
    #: a quote the posting does not carry. Kept on the record because the
    #: question a user asks about an analysis is why it says less than the
    #: posting seems to ask for, and an in-memory answer cannot be read back.
    issues: list[AnalysisIssue] = []
    #: The share of requirements whose text was found in the posting. A
    #: measurement of this reading's grounding, and deliberately not
    #: `confidence`, which is the provider's own account of the classification.
    source_coverage: float | None = Field(default=None, ge=0, le=1)
