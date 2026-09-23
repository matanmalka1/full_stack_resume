"""The tolerant analysis boundary: what a flawed reading costs, and what it does not.

One live run lost sixteen correctly-read requirements to a span that reached a
character past its sentence; another lost fifteen to a one-word context quote
the interpretation never needed. These tests hold the rule that replaced that
behaviour: every check still runs, each failure lowers what the analysis claims
about the candidate, and none of them discards the rest of the reading.
"""

from __future__ import annotations

import pytest

from cv_engine.domain.analysis.normalize import normalize_analysis_proposal
from cv_engine.domain.analysis.projection import gaps
from cv_engine.domain.contracts.analysis import Coverage
from cv_engine.domain.contracts.analysis_proposal import (
    AnalysisProposal,
    Importance,
    ProposedRequirement,
)
from cv_engine.domain.contracts.knowledge import FactStatus
from cv_engine.domain.facts import FactStore
from cv_engine.util import sha256_text

JOB = (
    "Requirements:\n"
    "- Experience working with Web-based systems - required.\n"
    "- Comfortable presenting to customers.\n"
    "- Sales experience in the software industry.\n"
)

CANONICAL_FACT = "development.phdigital.fullstack"


def _proposal(*requirements: ProposedRequirement, **overrides) -> AnalysisProposal:
    return AnalysisProposal(
        **{
            "track": "tech-sales",
            "profile": "pre-sales-solutions-consultant",
            "emphasis": "tech-consultative-sales",
            "language": "en",
            "summary": "a reading",
            "requirements": list(requirements),
            **overrides,
        }
    )


def _normalize(proposal, fact_store, profile_store, requirement_concepts, source_text=JOB):
    return normalize_analysis_proposal(
        proposal,
        source_text=source_text,
        facts=fact_store,
        profiles=profile_store,
        concepts=requirement_concepts,
        normalized_hash=sha256_text(source_text),
    )


def test_profile_supplies_track_when_provider_returns_an_impossible_pair(
    fact_store, profile_store, requirement_concepts
) -> None:
    analysis = _normalize(
        _proposal(profile="account-executive", track="tech-sales"),
        fact_store,
        profile_store,
        requirement_concepts,
    )

    assert analysis.profile == "account-executive"
    assert analysis.track == "sales"


def test_one_unusable_requirement_does_not_cost_the_others(
    fact_store, profile_store, requirement_concepts
) -> None:
    """The failure that motivated the whole contract change.

    A proposal is a list of readings, not one indivisible claim. One entry the
    engine cannot use is one entry lost.
    """
    analysis = _normalize(
        _proposal(
            ProposedRequirement(
                text="- Experience working with Web-based systems - required.",
                importance="mandatory",
                coverage="matched",
                fact_ids=[CANONICAL_FACT],
            ),
            ProposedRequirement(text="   "),
            ProposedRequirement(text="- Comfortable presenting to customers.", coverage="unknown"),
        ),
        fact_store,
        profile_store,
        requirement_concepts,
    )

    assert [requirement.text for requirement in analysis.requirements] == [
        "- Experience working with Web-based systems - required.",
        "- Comfortable presenting to customers.",
    ]
    assert [issue.code for issue in analysis.issues if issue.code == "requirement_unusable"] == [
        "requirement_unusable"
    ]


def test_a_fact_the_store_does_not_have_is_dropped_and_disclosed(
    fact_store, profile_store, requirement_concepts
) -> None:
    """An invented citation never reaches the analysis, and never silently.

    Dropping the id alone would leave `matched` standing on nothing, so the
    coverage falls with it - to `unknown`, not `unsupported`: the evidence
    failed, which is not a finding that the candidate lacks the thing.
    """
    analysis = _normalize(
        _proposal(
            ProposedRequirement(
                text="- Comfortable presenting to customers.",
                coverage="matched",
                fact_ids=["fact.that.does.not.exist"],
            )
        ),
        fact_store,
        profile_store,
        requirement_concepts,
    )

    requirement = analysis.requirements[0]
    assert requirement.supporting_fact_ids == []
    assert requirement.coverage == "unknown"
    assert {"unknown_fact", "coverage_without_evidence"} <= {
        issue.code for issue in analysis.issues
    }


def test_a_noncanonical_fact_is_dropped_and_positive_coverage_becomes_unknown(
    fact_store, profile_store, requirement_concepts
) -> None:
    facts = dict(fact_store.facts)
    facts[CANONICAL_FACT] = facts[CANONICAL_FACT].model_copy(
        update={"status": FactStatus.CONFIRMED}
    )
    noncanonical = FactStore(facts, dict(fact_store.source_versions))

    analysis = _normalize(
        _proposal(
            ProposedRequirement(
                text="- Experience working with Web-based systems - required.",
                coverage="matched",
                fact_ids=[CANONICAL_FACT],
            )
        ),
        noncanonical,
        profile_store,
        requirement_concepts,
    )

    requirement = analysis.requirements[0]
    assert requirement.supporting_fact_ids == []
    assert requirement.coverage == "unknown"
    assert {issue.code for issue in analysis.issues} == {
        "fact_not_canonical",
        "coverage_without_evidence",
    }


# Five spellings of a quote against a posting, each a distinct outcome:
# exact carries offsets; not found keeps the requirement unattested and
# disclosed; a repeat stays verified without asserting which occurrence;
# different whitespace is not two occurrences; and a quote wrapped *and*
# repeated is ambiguous in either spelling. Matching is case-sensitive by
# design, which is why the repeated postings keep one case.
@pytest.mark.parametrize(
    ("posting", "quote", "match", "quote_issues"),
    [
        (JOB, "- Comfortable presenting to customers.", "exact", set()),
        (JOB, "Willingness to relocate to Mars.", "not_found", {"quote_not_found"}),
        (
            "Requirements:\n- required\n- Something else, required\n",
            "required",
            "ambiguous",
            {"quote_ambiguous"},
        ),
        (JOB, "Comfortable presenting    to customers.", "normalized", set()),
        (
            "Requirements:\n- presenting   to customers.\n- Also: presenting to\n  customers.\n",
            "presenting to customers.",
            "ambiguous",
            {"quote_ambiguous"},
        ),
    ],
    ids=["exact", "not-found", "repeated", "wrapped", "wrapped-and-repeated"],
)
def test_quote_attestation_matrix(
    fact_store, profile_store, requirement_concepts, posting, quote, match, quote_issues
) -> None:
    """A requirement the engine could not locate is still a requirement.

    Failing to match wording is a statement about the match, not about the
    requirement, so every case keeps it. Only `exact` carries offsets; the
    other verified answers deliberately assert no span, and still count toward
    source coverage - the missing span is not the question.
    """
    analysis = _normalize(
        _proposal(ProposedRequirement(text=quote)),
        fact_store,
        profile_store,
        requirement_concepts,
        source_text=posting,
    )

    assert len(analysis.requirements) == 1
    source = analysis.requirements[0].source
    assert source is not None
    assert source.match == match
    verified = match != "not_found"
    assert source.verified is verified
    assert analysis.source_coverage == (1.0 if verified else 0.0)
    issue_codes = {issue.code for issue in analysis.issues}
    assert {code for code in issue_codes if code.startswith("quote_")} == quote_issues
    if match == "not_found":
        assert issue_codes == {"quote_not_found"}
    if match == "exact":
        start = posting.index(quote)
        assert (source.start, source.end) == (start, start + len(quote))
        assert posting[source.start : source.end] == quote
    else:
        assert source.start is None and source.end is None


def test_the_record_carries_why_the_reading_was_narrowed(
    fact_store, profile_store, requirement_concepts
) -> None:
    """Issues and grounding are stored, not returned and forgotten.

    A user looking at an analysis asks why it claims less than the posting
    seems to ask for. That answer has to survive the save: held only in memory
    it is gone by the time anyone opens the record.
    """
    analysis = _normalize(
        _proposal(
            ProposedRequirement(
                text="- Comfortable presenting to customers.",
                coverage="matched",
                fact_ids=["fact.that.does.not.exist"],
            )
        ),
        fact_store,
        profile_store,
        requirement_concepts,
    )

    restored = type(analysis).model_validate(analysis.model_dump(mode="json"))
    assert {issue.code for issue in restored.issues} >= {
        "unknown_fact",
        "coverage_without_evidence",
    }
    assert restored.source_coverage == 1.0
    assert restored.requirements[0].source is not None
    assert restored.requirements[0].source.match == "exact"


def test_duplicate_merge_uses_the_full_importance_and_coverage_orders(
    fact_store, profile_store, requirement_concepts
) -> None:
    """Importance merges upward while coverage merges downward.

    They are claims about different parties. Taking the lower importance
    relieved the candidate of a requirement the posting stated: the Fit
    weighting dropped and a hard gap disappeared, and the analysis got more
    flattering for no reason but a restatement.
    """
    restated = _normalize(
        _proposal(
            ProposedRequirement(
                text="- Experience working with Web-based systems - required.",
                importance="mandatory",
                coverage="unsupported",
            ),
            ProposedRequirement(
                text="- Experience working with Web-based systems - required.",
                importance="unknown",
                coverage="matched",
                fact_ids=[CANONICAL_FACT],
            ),
        ),
        fact_store,
        profile_store,
        requirement_concepts,
    )
    assert restated.requirements[0].importance == "mandatory"
    assert restated.requirements[0].coverage == "unsupported"
    assert [gap.severity for gap in gaps(restated.requirements, fact_store)] == ["hard"]

    quote = "- Comfortable presenting to customers."
    importance_cases: list[tuple[Importance, Importance, Importance]] = [
        ("unknown", "preferred", "preferred"),
        ("preferred", "mandatory", "mandatory"),
    ]
    coverage_cases: list[tuple[Coverage, Coverage, Coverage]] = [
        ("matched", "partial", "partial"),
        ("partial", "unsupported", "unsupported"),
        ("unsupported", "unknown", "unknown"),
    ]

    for first, second, expected in importance_cases:
        analysis = _normalize(
            _proposal(
                ProposedRequirement(
                    text=quote,
                    importance=first,
                    coverage="matched",
                    fact_ids=[CANONICAL_FACT],
                ),
                ProposedRequirement(
                    text=quote,
                    importance=second,
                    coverage="matched",
                    fact_ids=[CANONICAL_FACT],
                ),
            ),
            fact_store,
            profile_store,
            requirement_concepts,
        )
        assert analysis.requirements[0].importance == expected

    for first, second, expected in coverage_cases:
        analysis = _normalize(
            _proposal(
                ProposedRequirement(text=quote, coverage=first, fact_ids=[CANONICAL_FACT]),
                ProposedRequirement(text=quote, coverage=second, fact_ids=[CANONICAL_FACT]),
            ),
            fact_store,
            profile_store,
            requirement_concepts,
        )
        assert analysis.requirements[0].coverage == expected


def test_two_readings_of_one_sentence_merge_to_the_lower_claim(
    fact_store, profile_store, requirement_concepts
) -> None:
    """A provider restating a requirement is one requirement.

    Merging takes the lower coverage, because two readings that disagree are
    not evidence for the more flattering one; the higher importance, because
    that disagreement is about what the employer demanded; and the union of the
    evidence, because both citations were offered for the same sentence.

    The duplicate issue's `requirement_index` addresses the provider's list,
    not the merged one: the preserved response is the only list a reader can
    open, so an index into the post-merge list would name entries that exist
    nowhere.
    """
    analysis = _normalize(
        _proposal(
            ProposedRequirement(
                text="- Comfortable presenting to customers.",
                importance="mandatory",
                coverage="matched",
                fact_ids=[CANONICAL_FACT],
            ),
            ProposedRequirement(text="- Sales experience in the software industry."),
            ProposedRequirement(
                text="-  Comfortable presenting to customers. ",
                importance="preferred",
                coverage="partial",
                shortfall_severity="material",
                shortfall_reason="A material part of the demand is not verified.",
                fact_ids=["sales.cycle.account_management"],
            ),
        ),
        fact_store,
        profile_store,
        requirement_concepts,
    )

    requirement = analysis.requirements[0]
    assert len(analysis.requirements) == 2
    assert requirement.coverage == "partial"
    assert requirement.shortfall_severity == "material"
    assert requirement.importance == "mandatory"
    assert set(requirement.supporting_fact_ids) == {
        CANONICAL_FACT,
        "sales.cycle.account_management",
    }
    duplicate = next(issue for issue in analysis.issues if issue.code == "duplicate_requirement")
    assert duplicate.requirement_index == 2
    assert duplicate.details["merged_into_index"] == "0"


def test_a_canonical_boundary_still_caps_a_match(
    fact_store, profile_store, requirement_concepts
) -> None:
    """The one deterministic veto the simplified contract keeps.

    Without it a provider could cite adjacent verified sales facts, call a
    software-industry sales requirement `matched`, and have every remaining
    check pass - which is how unverified experience reaches a CV.
    """
    analysis = _normalize(
        _proposal(
            ProposedRequirement(
                text="- Sales experience in the software industry.",
                importance="mandatory",
                coverage="matched",
                fact_ids=["sales.cycle.account_management"],
            )
        ),
        fact_store,
        profile_store,
        requirement_concepts,
    )

    requirement = analysis.requirements[0]
    assert requirement.boundary_fact_ids
    assert requirement.coverage == "partial"
    assert requirement.shortfall_severity == "material"


@pytest.mark.parametrize(
    ("coverage", "shortfall_severity", "shortfall_reason", "expected_severity", "inconsistent"),
    [
        (
            "partial",
            "minor",
            "The verified duration is slightly below the requested threshold.",
            "minor",
            False,
        ),
        ("matched", "minor", None, "none", True),
        ("partial", "material", None, "unknown", True),
    ],
    ids=["explained-minor-partial", "matched-with-shortfall", "unexplained-material-partial"],
)
def test_a_shortfall_survives_only_when_consistent_with_its_coverage(
    fact_store,
    profile_store,
    requirement_concepts,
    coverage,
    shortfall_severity,
    shortfall_reason,
    expected_severity,
    inconsistent,
) -> None:
    analysis = _normalize(
        _proposal(
            ProposedRequirement(
                text="- Comfortable presenting to customers.",
                importance="mandatory",
                coverage=coverage,
                shortfall_severity=shortfall_severity,
                shortfall_reason=shortfall_reason,
                fact_ids=[CANONICAL_FACT],
            )
        ),
        fact_store,
        profile_store,
        requirement_concepts,
    )

    requirement = analysis.requirements[0]
    assert requirement.shortfall_severity == expected_severity
    if shortfall_reason is not None:
        assert requirement.shortfall_reason == shortfall_reason
    issue_codes = {issue.code for issue in analysis.issues}
    assert ("shortfall_inconsistent" in issue_codes) is inconsistent
