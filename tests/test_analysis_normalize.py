"""The tolerant analysis boundary: what a flawed reading costs, and what it does not.

One live run lost sixteen correctly-read requirements to a span that reached a
character past its sentence; another lost fifteen to a one-word context quote
the interpretation never needed. These tests hold the rule that replaced that
behaviour: every check still runs, each failure lowers what the analysis claims
about the candidate, and none of them discards the rest of the reading.
"""

from __future__ import annotations

from cv_engine.domain.analysis.normalize import normalize_analysis_proposal
from cv_engine.domain.contracts.analysis_proposal import AnalysisProposal, ProposedRequirement
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
    coverage falls with it - to `undetermined`, not `unsupported`: the evidence
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
    assert requirement.coverage == "undetermined"
    # The incompleteness hint fires too - this posting states three
    # requirement lines and the proposal read one - and it is a hint, not a
    # finding about the entry under test.
    assert {"unknown_fact", "coverage_without_evidence"} <= {
        issue.code for issue in analysis.issues
    }


def test_a_quote_the_posting_does_not_carry_is_kept_as_a_warning(
    fact_store, profile_store, requirement_concepts
) -> None:
    """A requirement the engine could not locate is still a requirement.

    The posting is what the engine can check, and failing to match wording is a
    statement about the match, not about the requirement. It is kept, left
    without an attestation, and disclosed.
    """
    analysis = _normalize(
        _proposal(ProposedRequirement(text="Willingness to relocate to Mars.")),
        fact_store,
        profile_store,
        requirement_concepts,
    )

    assert len(analysis.requirements) == 1
    assert analysis.requirements[0].attestation is None
    assert {issue.code for issue in analysis.issues} == {
        "quote_not_found",
        "analysis_may_be_incomplete",
    }


def test_a_quote_the_posting_repeats_stays_verified_without_offsets(
    fact_store, profile_store, requirement_concepts
) -> None:
    """Repetition does not make the text less present.

    The old gate refused a repeated quote outright. Here the claim the engine
    can prove - the posting says this - is kept, and the one it cannot - which
    occurrence - is simply not asserted.
    """
    posting = "Requirements:\n- required\n- Something else, required\n"
    analysis = _normalize(
        _proposal(ProposedRequirement(text="required")),
        fact_store,
        profile_store,
        requirement_concepts,
        source_text=posting,
    )

    assert analysis.requirements[0].attestation is None
    assert "quote_ambiguous" in {issue.code for issue in analysis.issues}
    assert "quote_not_found" not in {issue.code for issue in analysis.issues}
    # Verified, and counted as verified: the missing span is not the question.
    assert analysis.requirements[0].source.match == "ambiguous"
    assert analysis.requirements[0].source.verified is True
    assert analysis.source_coverage == 1.0


def test_a_posting_that_wraps_the_quote_is_matched_without_being_called_ambiguous(
    fact_store, profile_store, requirement_concepts
) -> None:
    """Different whitespace is not two occurrences.

    Both answers come back without offsets, and inferring the reason from that
    absence reported a wrapped line as an ambiguous one and, worse, counted it
    as unanchored.
    """
    analysis = _normalize(
        _proposal(ProposedRequirement(text="Comfortable presenting    to customers.")),
        fact_store,
        profile_store,
        requirement_concepts,
    )

    assert analysis.requirements[0].source.match == "normalized"
    assert analysis.requirements[0].source.verified is True
    assert "quote_ambiguous" not in {issue.code for issue in analysis.issues}
    assert "quote_not_found" not in {issue.code for issue in analysis.issues}
    assert analysis.source_coverage == 1.0


def test_a_wrapped_quote_that_repeats_is_ambiguous_not_merely_normalized(
    fact_store, profile_store, requirement_concepts
) -> None:
    """Repetition is repetition in either spelling.

    Matching after collapsing whitespace used to ask only whether the text was
    in there. A quote the posting wraps *and* states twice answered yes on its
    first occurrence and came back as a clean single match, so the analysis
    claimed a definite source for a requirement stated in two places.
    """
    # Same wording twice, wrapped differently, and in the same case: matching
    # is case-sensitive by design, so a capital would have made these two
    # different strings rather than one repeated one.
    posting = "Requirements:\n- presenting   to customers.\n- Also: presenting to\n  customers.\n"
    analysis = _normalize(
        _proposal(ProposedRequirement(text="presenting to customers.")),
        fact_store,
        profile_store,
        requirement_concepts,
        source_text=posting,
    )

    assert analysis.requirements[0].source is not None
    assert analysis.requirements[0].source.match == "ambiguous"
    assert "quote_ambiguous" in {issue.code for issue in analysis.issues}


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
    # The provider reported no classification confidence and none is invented.
    assert restored.confidence is None


def test_an_analysis_written_before_these_fields_still_reads(
    fact_store, profile_store, requirement_concepts
) -> None:
    """Old records keep what they carried and gain nothing they did not.

    `structured_json` is a JSONB document, so these fields arrived without a
    migration - which is exactly the case where a reader can quietly invent
    values for records that never had them.
    """
    analysis = _normalize(
        _proposal(ProposedRequirement(text="- Comfortable presenting to customers.")),
        fact_store,
        profile_store,
        requirement_concepts,
    )
    document = analysis.model_dump(mode="json")
    for field in ("issues", "source_coverage"):
        document.pop(field)
    for requirement in document["requirements"]:
        requirement.pop("source")

    historical = type(analysis).model_validate(document)

    assert historical.issues == []
    assert historical.source_coverage is None
    assert historical.requirements[0].source is None


def test_a_restated_requirement_keeps_the_stronger_demand(
    fact_store, profile_store, requirement_concepts
) -> None:
    """Importance merges upward while coverage merges downward.

    They are claims about different parties. Taking the lower importance
    relieved the candidate of a requirement the posting stated: the Fit
    weighting dropped and a hard gap disappeared, and the analysis got more
    flattering for no reason but a restatement.
    """
    analysis = _normalize(
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

    requirement = analysis.requirements[0]
    assert requirement.mandatory is True
    assert requirement.coverage == "unsupported"
    assert [gap.severity for gap in analysis.gaps] == ["hard"]


def test_a_duplicate_issue_points_at_the_proposal_the_provider_sent(
    fact_store, profile_store, requirement_concepts
) -> None:
    """`requirement_index` addresses the provider's list, not a merged one.

    The preserved response is the only list a reader can open, so an index into
    the post-merge list would name entries that exist nowhere.
    """
    analysis = _normalize(
        _proposal(
            ProposedRequirement(text="- Comfortable presenting to customers."),
            ProposedRequirement(text="- Sales experience in the software industry."),
            ProposedRequirement(text="- Comfortable presenting to customers."),
        ),
        fact_store,
        profile_store,
        requirement_concepts,
    )

    duplicate = next(issue for issue in analysis.issues if issue.code == "duplicate_requirement")
    assert duplicate.requirement_index == 2
    assert duplicate.details["merged_into_index"] == "0"


def test_two_readings_of_one_sentence_merge_to_the_lower_claim(
    fact_store, profile_store, requirement_concepts
) -> None:
    """A provider restating a requirement is one requirement.

    Merging takes the lower coverage, because two readings that disagree are
    not evidence for the more flattering one; the higher importance, because
    that disagreement is about what the employer demanded; and the union of the
    evidence, because both citations were offered for the same sentence.
    """
    analysis = _normalize(
        _proposal(
            ProposedRequirement(
                text="- Comfortable presenting to customers.",
                importance="mandatory",
                coverage="matched",
                fact_ids=[CANONICAL_FACT],
            ),
            ProposedRequirement(
                text="-  Comfortable presenting to customers. ",
                importance="preferred",
                coverage="partial",
                fact_ids=["sales.cycle.account_management"],
            ),
        ),
        fact_store,
        profile_store,
        requirement_concepts,
    )

    requirement = analysis.requirements[0]
    assert len(analysis.requirements) == 1
    assert requirement.coverage == "partial"
    assert requirement.mandatory is True
    assert set(requirement.supporting_fact_ids) == {
        CANONICAL_FACT,
        "sales.cycle.account_management",
    }
    assert "duplicate_requirement" in {issue.code for issue in analysis.issues}


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
