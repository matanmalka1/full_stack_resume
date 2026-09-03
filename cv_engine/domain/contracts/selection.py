"""Fact-selection decisions and their immutable lineage."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .base import StrictModel
from .taxonomy import Emphasis

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
