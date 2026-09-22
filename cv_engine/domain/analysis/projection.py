"""Fit and gaps, derived from requirements every time they are needed.

They used to be stored on `JobAnalysis` beside the requirements they come
from, which made one fact of the matter into several fields that could
disagree - a correction applied to `requirements` and not to `gaps` left a
record asserting both. Nothing here is a property on the model either: a
computed property serializes, and a serialized derivation is a stored one
again under a different name.

Pure functions of the requirements and the fact store. Same input, same
answer, and no way to persist one without deciding to.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..contracts.analysis import FitLevel, Importance, Requirement
from ..facts import FactStore

#: Why a requirement is not met, when no boundary fact gives the authoritative
#: account. Deterministic labels rather than generated prose: the reason is
#: displayed, never matched on.
_COVERAGE_REASON = {
    "partial": "Canonical facts cover part of this requirement; the rest is not verified.",
    "unsupported": "Canonical facts do not verify this requirement.",
    #: Distinct from `unsupported` on purpose: the engine could not decide
    #: coverage at all, so it makes no claim about whether canonical facts
    #: verify the requirement. Reporting it as "not verified" would assert
    #: something nobody checked.
    "unknown": "The engine could not determine coverage for this requirement.",
}

#: A mandatory requirement counts double toward the score: failing to verify
#: something the posting demanded should move it more than falling short on
#: something the posting only preferred. An `unknown` importance is weighted as
#: a preference - the posting did not say it was required, and weighting it as
#: if it had would let silence about a demand lower the score.
_IMPORTANCE_WEIGHT: dict[Importance, int] = {"mandatory": 2, "preferred": 1, "unknown": 1}

#: `unknown` earns no credit, on purpose: an unassessed requirement must not
#: score like a met one, or an incompletely read posting would outscore a fully
#: read one.
_COVERAGE_VALUE = {"matched": 1.0, "partial": 0.5, "unsupported": 0.0, "unknown": 0.0}

#: Score thresholds the Fit level is drawn from. Named constants rather than
#: inline literals because they are a tunable product decision, not an
#: arithmetic fact.
FIT_SCORE_HIGH_THRESHOLD = 0.85
FIT_SCORE_MEDIUM_THRESHOLD = 0.55


@dataclass(frozen=True)
class Gap:
    """One requirement canonical facts do not fully answer.

    `severity` is `hard` only for a mandatory requirement the facts actively
    fail to verify. `unknown` coverage is never hard: "we could not tell" is
    not "you lack this", and treating it as a hard gap would ask the user to
    accept a deficiency nobody established.
    """

    requirement_id: str
    requirement: str
    severity: str
    reason: str
    substitute_fact_ids: list[str]


def fit_score(requirements: Sequence[Requirement]) -> float | None:
    """The weighted fraction of requirement coverage this reading found.

    `None` when nothing was assessed - no requirements at all. A posting whose
    requirements were never read has no Fit, and reporting one would claim an
    assessment that did not happen.
    """
    if not requirements:
        return None
    weights = [_IMPORTANCE_WEIGHT[requirement.importance] for requirement in requirements]
    earned = sum(
        weight * _COVERAGE_VALUE[requirement.coverage]
        for weight, requirement in zip(weights, requirements, strict=True)
    )
    return earned / sum(weights)


def fit_level(requirements: Sequence[Requirement]) -> FitLevel:
    """The Fit band, read off the score and lowered by any hard gap.

    A hard gap caps the level at LOW however well everything else scored: a
    demanded requirement the facts contradict is not offset by unrelated
    strengths.
    """
    score = fit_score(requirements)
    if score is None:
        return FitLevel.UNKNOWN
    if any(gap.severity == "hard" for gap in _bare_gaps(requirements)):
        return FitLevel.LOW
    if score >= FIT_SCORE_HIGH_THRESHOLD:
        return FitLevel.HIGH
    if score >= FIT_SCORE_MEDIUM_THRESHOLD:
        return FitLevel.MEDIUM
    return FitLevel.LOW


def _bare_gaps(requirements: Sequence[Requirement]) -> list[Gap]:
    """Gaps without their authoritative wording, for severity questions only."""
    return [
        Gap(
            requirement_id=requirement.requirement_id,
            requirement=requirement.text,
            severity=_severity(requirement),
            reason="",
            substitute_fact_ids=list(requirement.supporting_fact_ids),
        )
        for requirement in requirements
        if requirement.coverage != "matched"
    ]


def _severity(requirement: Requirement) -> str:
    """Only an established material shortfall in a demand is hard."""
    if requirement.importance != "mandatory":
        return "warning"
    if requirement.coverage == "unsupported":
        return "hard"
    if requirement.coverage != "partial":
        return "warning"
    # Immutable analyses created before this field existed retain their former
    # conservative projection. New uncertain assessments do not become a hard
    # gap merely because the provider could not determine materiality.
    return "hard" if requirement.shortfall_severity in (None, "material") else "warning"


def gaps(requirements: Sequence[Requirement], facts: FactStore) -> list[Gap]:
    """Every requirement the facts do not fully answer, and why.

    The boundary meanings are read from the facts here rather than taken as a
    prepared mapping, so a gap is explained in the candidate's own confirmed
    words where one applies.
    """
    projected: list[Gap] = []
    for requirement in requirements:
        if requirement.coverage == "matched":
            continue
        authoritative = next(
            (
                facts.facts[fact_id].meaning
                for fact_id in requirement.boundary_fact_ids
                if fact_id in facts.facts
            ),
            None,
        )
        projected.append(
            Gap(
                requirement_id=requirement.requirement_id,
                requirement=requirement.text,
                severity=_severity(requirement),
                reason=(
                    authoritative
                    or requirement.shortfall_reason
                    or _COVERAGE_REASON[requirement.coverage]
                ),
                substitute_fact_ids=list(requirement.supporting_fact_ids),
            )
        )
    return projected


def hard_gaps(requirements: Sequence[Requirement], facts: FactStore) -> list[Gap]:
    return [gap for gap in gaps(requirements, facts) if gap.severity == "hard"]
