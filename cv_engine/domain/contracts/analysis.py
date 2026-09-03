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
