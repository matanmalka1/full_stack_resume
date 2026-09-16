"""Job requirement, classification, and fit-analysis contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from .analysis_proposal import (
    AnalysisIssue,
    Importance,
    ProposedRequirementCoverage,
    RequirementSource,
)
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


#: The stored vocabulary is the proposed one. There is no second spelling of
#: the same four answers: `unknown` is what "we could not tell" is called
#: everywhere, and the old `undetermined` is gone rather than translated at the
#: boundary.
Coverage = ProposedRequirementCoverage


class Requirement(StrictModel):
    """One thing the employer asked for, and what we can truthfully show for it.

    `coverage` is about the requirement being met. `supporting_fact_ids` is
    about evidence existing. They are independent: a demanded proficiency the
    candidate falls short of is `unsupported` and still lists the canonical
    fact carrying the lower value.

    `supporting_fact_ids` records evidence. It never licenses a merged or
    strengthened claim - a fact listed here because it is adjacent to the
    requirement must not be drafted as if it satisfied it. `boundary_fact_ids`
    names the canonical facts that say so explicitly, and is what lets a gap be
    explained in the candidate's own confirmed words rather than a generic
    label.

    There is no `mandatory` beside `importance`, and no `missing_components`
    beside `coverage`: one fact of the matter, stored once. What is missing from
    a requirement that is not `matched` is the requirement's own `text`.
    """

    requirement_id: str
    text: str
    importance: Importance = "unknown"
    coverage: Coverage = "unknown"
    supporting_fact_ids: list[str] = []
    boundary_fact_ids: list[str] = []
    #: How the posting was found to carry this text, when it was found at all.
    source: RequirementSource | None = None


#: What a user may override on an analysis. `fit` and `analysis` were the
#: acceptance keys - low Fit and an incomplete reading - and there is
#: nothing left to accept.
OverrideKey = Literal["track", "profile", "emphasis", "language"]
Language = Literal["en", "he"]


class JobAnalysis(StrictModel):
    """One reading of one posting: what it asks for, and how the facts answer it.

    Everything derivable lives in `requirements` and is computed where it is
    needed - Fit, gaps, which demands are mandatory. Storing those as well made
    one fact of the matter into four fields that could disagree, and an analysis
    corrected in one of them and not the others.

    There are no `approval_reasons`. A partial reading is kept and shown; its
    `issues` inform the user and stop nothing. What stops unsupported content is
    draft validation, at the point where that content would reach the CV.
    """

    analysis_version: Literal["3.0"] = "3.0"
    track: Track
    profile: ProfileName
    emphasis: Emphasis
    language: Literal["en", "he"]
    #: The provider's short account of its reading. Displayed, never matched on.
    summary: str
    keywords: list[str] = []
    requirements: list[Requirement] = []
    #: Where this reading was narrowed: a citation dropped, a coverage lowered,
    #: a quote the posting does not carry.
    issues: list[AnalysisIssue] = []
    #: The share of requirements whose text was found in the posting.
    source_coverage: float | None = Field(default=None, ge=0, le=1)
    user_override: dict[OverrideKey, str] = {}
