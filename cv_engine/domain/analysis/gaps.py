from __future__ import annotations

from collections.abc import Sequence

from ..contracts.analysis import FitLevel, Gap, JobAnalysis, Requirement
from ..contracts.selection import SelectionPlan
from ..facts import FactStore

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
    could beat. "We could not tell" earns no score credit, without making a
    false claim that the candidate definitely lacks the requirement.

    An empty requirement list scores 1.0, not `None`: nothing was demanded, so
    nothing is missing - the same "not punished for being short" reading a thin,
    legitimately requirement-free posting should receive. This function cannot on its own
    tell that case apart from an extraction that produced nothing because it
    failed. `fit_score_for` is where that distinction is made, and is the only
    caller in the engine; the raw score stays separately callable because it is
    the arithmetic on its own, testable without the two signals that decide
    whether asking for it is meaningful at all.
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


def fit_score_for(
    requirements: Sequence[Requirement],
    *,
    extraction_failed: bool,
    requirements_absent: bool,
) -> float | None:
    """The Fit score, or `None` where there is nothing to score.

    `fit_score_from_requirements` returns 1.0 for an empty list - correct in
    isolation, "nothing demanded, nothing missing" - and that is exactly the
    answer that must not be reported when the list is empty because the
    extraction failed or the posting stated nothing readable. Neither of those
    is visible from the list, so both are passed in.

    The same function is used for initial analysis and later corrections, so
    both preserve the same unknown-Fit policy.
    """
    if extraction_failed or requirements_absent:
        return None
    return fit_score_from_requirements(requirements)


def fit_level_from_score(fit_score: float | None, gaps: Sequence[Gap]) -> FitLevel:
    """`fit_score` is canonical; `fit_level` is read off it, gap-overridden.

    Order matters:

    1. A hard gap projected from a mandatory verified requirement forces LOW
       outright, even with no score at all.
       `apply_analysis_decisions(accept_incomplete_analysis=True)` depends on
       exactly this: "Fit remains unknown unless an independently established
       hard gap requires low" (state-and-use-cases.md §12,
       `apply_analysis_decisions`) - a known poor Fit is knowledge that an
       otherwise-unassessed analysis must not erase. This is unchanged from the
       the same policy applies after an interpretation correction.
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


def gaps_from_requirements(requirements: Sequence[Requirement], facts: FactStore) -> list[Gap]:
    """Project the unmet requirements as gaps.

    The boundary meanings are read here, from the facts, rather than taken as
    a prepared mapping. Both callers built that mapping with the same five
    lines - a duplicated derivation with no decision in it, which only gave a
    later edit somewhere to land on one path and not the other.

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
    gaps: list[Gap] = []
    for requirement in requirements:
        if requirement.coverage == "matched":
            continue
        # The first boundary fact that applies gives the authoritative account of
        # what is not verified; the generic label is the fallback when none does.
        authoritative = next(
            (
                facts.facts[fact_id].meaning
                for fact_id in requirement.boundary_fact_ids
                if fact_id in facts.facts
            ),
            None,
        )
        hard = requirement.mandatory and requirement.coverage != "undetermined"
        gaps.append(
            Gap(
                requirement=requirement.text,
                severity="hard" if hard else "warning",
                reason=authoritative or _COVERAGE_REASON[requirement.coverage],
                substitute_fact_ids=list(requirement.supporting_fact_ids),
                requirement_id=requirement.requirement_id,
            )
        )
    return gaps


def has_undetermined_mandatory(requirements: Sequence[Requirement]) -> bool:
    """Whether coverage could not be decided for something the posting demanded.

    The `coverage-undetermined` approval reason, asked once for both paths.
    "We could not tell" about a *preferred* requirement is not a decision the
    user must be stopped to make; the posting did not demand it.
    """
    return any(
        requirement.coverage == "undetermined" and requirement.mandatory
        for requirement in requirements
    )


def unaccepted_hard_gaps(
    analysis: JobAnalysis, plan: SelectionPlan | None, *, job_analysis_id: str | None
) -> list[Gap]:
    """The hard gaps still awaiting an explicit decision.

    One function, three consumers: the state projection that reports the
    blocker, the draft generation that refuses to build past it, and the
    validation that refuses to pass a draft built past it. All three use one
    policy for whether an acceptance applies.

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
