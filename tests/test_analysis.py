"""Fit and gaps as projections of the requirements they come from.

They used to be stored on the analysis beside those requirements, and the tests
here checked the assembly that filled them in. There is nothing to assemble
now: the same inputs are asked the same question wherever the answer is needed,
so what is worth pinning is the arithmetic and the two judgements inside it -
what an unread requirement scores, and what counts as a hard gap.
"""

from __future__ import annotations

import pytest

from cv_engine.domain.analysis.projection import (
    FIT_SCORE_HIGH_THRESHOLD,
    fit_level,
    fit_score,
    gaps,
    hard_gaps,
)
from cv_engine.domain.contracts.analysis import FitLevel, Requirement


def _requirement(**changes) -> Requirement:
    return Requirement.model_validate(
        {
            "requirement_id": changes.pop("requirement_id", "r1"),
            "text": "Own enterprise accounts",
            "importance": "mandatory",
            "coverage": "matched",
            **changes,
        }
    )


def test_a_posting_nothing_was_read_from_has_no_fit() -> None:
    """`None`, not zero and not 1.0.

    A score claims an assessment happened. Nothing was assessed here, and both
    a flattering default and a punishing one would assert something about the
    candidate that no reading produced.
    """
    assert fit_score([]) is None
    assert fit_level([]) is FitLevel.UNKNOWN


def test_an_unread_requirement_earns_no_credit_but_stays_in_the_denominator() -> None:
    """Otherwise an incompletely read posting outscores a fully read one.

    Dropping `unknown` from the denominator would make "we could not tell"
    score exactly like "we checked and it is met".
    """
    one_of_two = [_requirement(), _requirement(requirement_id="r2", coverage="unknown")]
    assert fit_score(one_of_two) == 0.5
    assert fit_score([_requirement()]) == 1.0


def test_an_unstated_importance_is_weighted_as_a_preference() -> None:
    """Silence is not a demand.

    A requirement the posting never marked as required is weighted like one it
    marked preferred: weighting it as mandatory would let the posting's silence
    move the score as much as its demands.
    """
    unknown_importance = [
        _requirement(importance="unknown", coverage="unsupported"),
        _requirement(requirement_id="r2", coverage="matched"),
    ]
    mandatory = [
        _requirement(importance="mandatory", coverage="unsupported"),
        _requirement(requirement_id="r2", coverage="matched"),
    ]
    assert fit_score(unknown_importance) > fit_score(mandatory)


@pytest.mark.parametrize(
    ("importance", "coverage", "shortfall_severity", "severity"),
    [
        ("mandatory", "unsupported", "material", "hard"),
        ("mandatory", "partial", "material", "hard"),
        ("mandatory", "partial", "minor", "warning"),
        ("mandatory", "partial", "unknown", "warning"),
        # "We could not tell" is not "you lack this", so it is never hard -
        # asking the user to accept a deficiency nobody established is the
        # question this rule exists to stop asking.
        ("mandatory", "unknown", "unknown", "warning"),
        ("preferred", "unsupported", "material", "warning"),
        ("unknown", "unsupported", "material", "warning"),
    ],
)
def test_only_an_established_failure_of_a_demand_is_a_hard_gap(
    fact_store, importance, coverage, shortfall_severity, severity
) -> None:
    projected = gaps(
        [
            _requirement(
                importance=importance,
                coverage=coverage,
                shortfall_severity=shortfall_severity,
            )
        ],
        fact_store,
    )
    assert [gap.severity for gap in projected] == [severity]


def test_a_pre_severity_partial_demand_keeps_its_historical_hard_gap(fact_store) -> None:
    projected = gaps(
        [_requirement(coverage="partial", shortfall_severity=None)],
        fact_store,
    )
    assert [gap.severity for gap in projected] == ["hard"]


def test_a_matched_requirement_projects_no_gap(fact_store) -> None:
    assert gaps([_requirement()], fact_store) == []


def test_a_hard_gap_caps_the_level_however_well_the_rest_scored(fact_store) -> None:
    """One demanded requirement the facts contradict is not offset by strengths.

    Nine matched requirements and one unsupported demand still score above the
    high threshold; the level is LOW anyway, because the posting asked for
    something the candidate cannot show.
    """
    requirements = [_requirement(requirement_id=f"r{index}") for index in range(9)]
    requirements.append(_requirement(requirement_id="gap", coverage="unsupported"))
    assert fit_score(requirements) > FIT_SCORE_HIGH_THRESHOLD
    assert fit_level(requirements) is FitLevel.LOW
    assert [gap.requirement_id for gap in hard_gaps(requirements, fact_store)] == ["gap"]


def test_a_minor_partial_demand_does_not_cap_an_otherwise_high_fit() -> None:
    requirements = [_requirement(requirement_id=f"r{index}") for index in range(9)]
    requirements.append(
        _requirement(
            requirement_id="minor-gap",
            coverage="partial",
            shortfall_severity="minor",
        )
    )

    assert fit_score(requirements) > FIT_SCORE_HIGH_THRESHOLD
    assert fit_level(requirements) is FitLevel.HIGH


def test_a_gap_exposes_the_analysis_shortfall_reason(fact_store) -> None:
    reason = "The verified duration is slightly below the requested threshold."
    projected = gaps(
        [
            _requirement(
                coverage="partial",
                shortfall_severity="minor",
                shortfall_reason=reason,
            )
        ],
        fact_store,
    )

    assert projected[0].reason == reason


def test_a_boundary_fact_explains_the_gap_in_the_candidates_own_words(fact_store) -> None:
    """The reason is the candidate's confirmed meaning, not a generic label.

    A boundary fact is what the candidate said about the limit themselves, so
    where one applies it is the authoritative account of why the requirement is
    not verified.
    """
    boundary = "sales.tech_sales.boundary"
    requirement = _requirement(coverage="partial", boundary_fact_ids=[boundary])
    projected = gaps([requirement], fact_store)

    assert projected[0].reason == fact_store.facts[boundary].meaning
    assert (
        projected[0].reason
        != "Canonical facts cover part of this requirement; the rest is not verified."
    )
