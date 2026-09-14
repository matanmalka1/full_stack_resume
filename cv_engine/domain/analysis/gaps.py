from __future__ import annotations

import re
from collections.abc import Sequence

from ..contracts.analysis import FitLevel, Gap, JobAnalysis, Requirement
from ..contracts.selection import SelectionPlan
from ..contracts.taxonomy import Track

#: Why a requirement is not met, when no boundary fact gives the authoritative
#: account. Deterministic labels rather than generated prose: the reason is
#: displayed, never matched on.
_COVERAGE_REASON = {
    "partial": "Canonical facts cover part of this requirement; the rest is not verified.",
    "unsupported": "Canonical facts do not verify this requirement.",
    #: Distinct from `unsupported` on purpose (stage-1 plan §3.6): the engine
    #: could not decide coverage at all - an unmodelled scale, an uncomputable
    #: threshold - so it makes no claim about whether canonical facts verify
    #: the requirement. Reporting it as "not verified" would assert something
    #: nobody checked.
    "undetermined": "The engine could not determine coverage for this requirement.",
}

#: A mandatory requirement counts double toward `fit_score`: failing to verify
#: something the posting demanded should move the score more than falling
#: short on something it only preferred.
_MANDATORY_WEIGHT = 2
_PREFERRED_WEIGHT = 1

#: `undetermined` earns no credit here, on purpose - see `fit_score_from_requirements`.
_COVERAGE_VALUE = {"matched": 1.0, "partial": 0.5, "unsupported": 0.0, "undetermined": 0.0}

#: Score thresholds `fit_level_from_score` reads to draw HIGH/MEDIUM/LOW from
#: `fit_score`. Named constants rather than inline literals because they are a
#: tunable product decision, not an arithmetic fact.
FIT_SCORE_HIGH_THRESHOLD = 0.85
FIT_SCORE_MEDIUM_THRESHOLD = 0.55


def fit_score_from_requirements(requirements: Sequence[Requirement]) -> float:
    """The weighted fraction of requirement coverage this posting's analysis found.

    `undetermined` requirements are *not* excluded from the denominator: they
    count toward `total_weight` at zero credit, the same as `unsupported`. An
    analysis that only decided coverage for 2 of 20 mandatory requirements and
    happened to match both must not score 1.0 - excluding what was never
    assessed would let an incomplete read report a fit score no complete read
    could beat. This is a deliberate departure from the old `coverage_undetermined
    -> Fit.UNKNOWN` rule (stage-1 plan §3.6): "we could not tell" now costs the
    score the way "we could tell it isn't there" does, rather than blanking the
    whole classification.

    An empty requirement list scores 1.0, not `None`: nothing was demanded, so
    nothing is missing - the same "not punished for being short" reading a thin,
    legitimately requirement-free posting already got from the old step function
    (`derive_fit` returned HIGH on no gaps). This function cannot on its own tell
    that case apart from an extraction that produced nothing because it failed;
    that distinction is `extraction_failed`, which both callers already carry and
    already use to force the *caller's* `fit_score` to `None` before this
    function would otherwise be asked to guess at zero requirements.
    """
    if not requirements:
        return 1.0
    total_weight = 0.0
    total_value = 0.0
    for requirement in requirements:
        weight = _MANDATORY_WEIGHT if requirement.mandatory else _PREFERRED_WEIGHT
        total_weight += weight
        total_value += weight * _COVERAGE_VALUE[requirement.coverage]
    return total_value / total_weight


def fit_level_from_score(fit_score: float | None, gaps: Sequence[Gap]) -> FitLevel:
    """`fit_score` is canonical; `fit_level` is read off it, gap-overridden.

    Order matters:

    1. A hard gap - a mandatory requirement `derive_gaps`/`gaps_from_requirements`
       could actually decide was unmet, at either the deterministic or the
       AI-merged stage - forces LOW outright, even with no score at all.
       `apply_analysis_decisions(accept_incomplete_analysis=True)` depends on
       exactly this: "Fit remains unknown unless an independently established
       hard gap requires low" (state-and-use-cases.md §12,
       `apply_analysis_decisions`) - a known poor Fit is knowledge that an
       otherwise-unassessed analysis must not erase. This is unchanged from the
       old `derive_fit`/`merge_fit` pair's own reasoning (stage-1 plan §3.6).
    2. Failing that, no score at all (nothing was assessed, or extraction never
       produced a requirement list) reports UNKNOWN rather than guessing a level
       for a number that does not exist.
    3. Otherwise the threshold on `fit_score` decides.
    """
    if any(gap.severity == "hard" for gap in gaps):
        return FitLevel.LOW
    if fit_score is None:
        return FitLevel.UNKNOWN
    if fit_score >= FIT_SCORE_HIGH_THRESHOLD:
        return FitLevel.HIGH
    if fit_score >= FIT_SCORE_MEDIUM_THRESHOLD:
        return FitLevel.MEDIUM
    return FitLevel.LOW


def gaps_from_requirements(
    requirements: Sequence[Requirement], *, boundary_meanings: dict[str, str] | None = None
) -> list[Gap]:
    """Project the unmet requirements as gaps.

    A mandatory requirement produces a hard gap whether its coverage is
    `partial` or `unsupported`. Partial means relevant evidence exists, not
    that the requirement is satisfied, so it still demands an explicit decision
    before drafting.

    `undetermined` is never a hard gap, mandatory or not (stage-1 plan §3.6):
    "we could not tell" is not "you lack this", so it is a warning-severity gap
    here and the `coverage-undetermined` approval reason - raised separately by
    the caller that has access to the analysis's `approval_reasons` - is what
    actually blocks approval for it.

    `substitute_fact_ids` carries the supporting facts because for a *gap* that
    is what they are - what may be shown in place of the thing that is missing.
    The two fields stay distinct on `Requirement`, where they mean different
    things.
    """
    meanings = boundary_meanings or {}
    gaps: list[Gap] = []
    for requirement in requirements:
        if requirement.coverage == "matched":
            continue
        authoritative = [
            meanings[fact_id] for fact_id in requirement.boundary_fact_ids if fact_id in meanings
        ]
        hard = requirement.mandatory and requirement.coverage != "undetermined"
        gaps.append(
            Gap(
                requirement=requirement.text,
                severity="hard" if hard else "warning",
                reason=authoritative[0]
                if authoritative
                else _COVERAGE_REASON[requirement.coverage],
                substitute_fact_ids=list(requirement.supporting_fact_ids),
                requirement_id=requirement.requirement_id,
            )
        )
    return gaps


def unaccepted_hard_gaps(
    analysis: JobAnalysis, plan: SelectionPlan | None, *, job_analysis_id: str | None
) -> list[Gap]:
    """The hard gaps still awaiting an explicit decision.

    One function, three consumers: the state projection that reports the
    blocker, the draft generation that refuses to build past it, and the
    validation that refuses to pass a draft built past it. They disagreed
    before - the projection said blocked while generation happily proceeded -
    because each asked the question in its own words.

    A plan for another analysis contributes nothing: acceptance is a decision
    about the gaps as *this* analysis stated them.
    """
    # `JobAnalysis` does not carry its own id, so the pairing is stated by the
    # caller rather than assumed. A keyword makes it impossible to pass the
    # wrong plan by argument order.
    accepted = (
        {accepted.requirement_id for accepted in plan.accepted_gaps}
        if plan is not None and plan.job_analysis_id == job_analysis_id
        else set()
    )
    return [
        gap
        for gap in analysis.gaps
        if gap.severity == "hard" and gap.requirement_id not in accepted
    ]


def merge_gaps(deterministic: Sequence[Gap], proposed: Sequence[Gap]) -> list[Gap]:
    """Union the two gap sets under a monotonic policy.

    Every deterministic gap survives with its own reason and substitute facts. A
    proposal may add a gap or raise an existing one from warning to hard; it can
    never drop a gap, soften its severity, or rewrite its authoritative text.
    """
    merged: dict[str, Gap] = {gap.requirement: gap for gap in deterministic}
    for gap in proposed:
        existing = merged.get(gap.requirement)
        if existing is None:
            merged[gap.requirement] = gap
        elif gap.severity == "hard" and existing.severity == "warning":
            merged[gap.requirement] = Gap(
                requirement=existing.requirement,
                severity="hard",
                reason=existing.reason,
                substitute_fact_ids=existing.substitute_fact_ids,
                requirement_id=existing.requirement_id,
            )
    return list(merged.values())


def derive_gaps(lowered: str, track: Track) -> list[Gap]:
    gaps: list[Gap] = []
    hard_saas = bool(re.search(r"(?:direct|proven|must have|required).{0,40}saas sales", lowered))
    if hard_saas:
        gaps.append(
            Gap(
                requirement="Direct SaaS Sales",
                severity="hard",
                reason="Device Sales plus separate Development experience does not verify direct SaaS Sales.",
                substitute_fact_ids=["sales.company.activity", "development.phdigital.role"],
            )
        )
    elif "saas" in lowered:
        gaps.append(
            Gap(
                requirement="Direct SaaS Sales preference",
                severity="warning",
                reason=(
                    "Direct SaaS/software Sales is not verified; B2B Sales and separate "
                    "professional Development experience may be presented without merging them."
                ),
                substitute_fact_ids=[
                    "development.phdigital.role",
                    "development.phdigital.fullstack",
                ],
            )
        )
    if re.search(
        r"(?:using|use|experience|familiarity).{0,50}\bcrm\b|\bcrm\b.{0,30}(?:tool|system)", lowered
    ):
        gaps.append(
            Gap(
                requirement="Sales CRM usage",
                severity="warning",
                reason=(
                    "Use of a named Sales CRM is not verified; canonical pipeline, Priority ERP, "
                    "and CRM-development experience may be shown instead."
                ),
                substitute_fact_ids=[
                    "sales.leadership.pipeline",
                    "sales.tool.priority",
                    "development.phdigital.crm",
                ],
            )
        )
    if re.search(
        r"strategic partnerships?|distribution partners?|strategic b2b channels?", lowered
    ):
        gaps.append(
            Gap(
                requirement="Strategic partnerships / channel Sales experience",
                severity="warning",
                reason=(
                    "Direct strategic-partnership or channel-Sales ownership is not verified; "
                    "new-business prospecting, complex deals, and strategic-customer work may be shown."
                ),
                substitute_fact_ids=[
                    "sales.cycle.prospecting",
                    "sales.achievement.complex_deals",
                    "sales.leadership.strategic_customers",
                ],
            )
        )
    if "salesforce" in lowered:
        gaps.append(
            Gap(
                requirement="Salesforce",
                severity="warning",
                reason="Salesforce is not verified; Priority ERP and pipeline experience may be presented instead.",
                substitute_fact_ids=["sales.tool.priority", "sales.leadership.pipeline"],
            )
        )
    years = [int(value) for value in re.findall(r"(\d+)\s*\+?\s*years?", lowered)]
    if years and max(years) >= 5 and track is Track.DEVELOPMENT:
        gaps.append(
            Gap(
                requirement=f"{max(years)}+ years of Development experience",
                severity="hard",
                reason="Canonical professional Development history does not meet this threshold.",
            )
        )
    return gaps
