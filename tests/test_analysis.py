import ast
import inspect
import json
from pathlib import Path
from typing import get_args

import pytest
from helpers import AMBIGUOUS_HEBREW_JOB, PAYME_TECH_SALES_JOB

from cv_engine.domain.analysis.approval import (
    ACCEPTED_INCOMPLETE_ANALYSIS,
    ANALYSIS_INCOMPLETE,
    APPROVAL_REASONS,
    CONFIDENCE_APPROVAL_THRESHOLD,
    unresolved_approval_reasons,
)
from cv_engine.domain.analysis.classification import (
    PROFILE_TERMS,
    classification_confidence,
    classify_job,
    requirement_profile_scores,
)
from cv_engine.domain.analysis.gaps import FIT_SEVERITY, derive_fit, derive_gaps, merge_fit
from cv_engine.domain.analysis.requirements.concepts import (
    RequirementConceptError,
    RequirementConceptStore,
    heading_key,
)
from cv_engine.domain.analysis.requirements.confidence import (
    concept_classification_completeness,
    extraction_completeness,
    extraction_confidence,
    extraction_failed,
    extraction_state,
)
from cv_engine.domain.analysis.requirements.coverage import cover_requirements
from cv_engine.domain.analysis.requirements.extraction import (
    extract_requirements,
    normalize_span,
)
from cv_engine.domain.analysis.requirements.segmentation import (
    requirement_lines,
    statement_lines,
)
from cv_engine.domain.models import (
    FactStatus,
    FitLevel,
    Gap,
    JobAnalysis,
    Language,
    ProfileName,
    Track,
)


def test_direct_saas_requirement_is_hard_gap(classify) -> None:
    result = classify(
        "Account Executive. Must have proven direct SaaS Sales experience and closing quota."
    )
    assert result.fit.value == "low"
    assert any(
        gap.requirement == "Direct SaaS Sales" and gap.severity == "hard" for gap in result.gaps
    )


def test_hebrew_language_detection_and_override(classify) -> None:
    result = classify("דרוש מנהל תיקי לקוחות לעבודה מול לקוחות עסקיים ושימור קשרים")
    assert result.language == "he"
    overridden = classify("developer Python API", language_override="he")
    assert overridden.language == "he"
    assert overridden.user_override["language"] == "he"


def test_tech_sales_analysis_records_preference_gaps_and_selection_concepts(classify) -> None:
    result = classify(
        PAYME_TECH_SALES_JOB,
        track_override="tech-sales",
        profile_override="tech-sales",
        emphasis_override="new-business",
    )

    assert result.fit.value == "medium"
    gaps = {gap.requirement: gap for gap in result.gaps}
    assert gaps["Direct SaaS Sales preference"].severity == "warning"
    assert gaps["Sales CRM usage"].substitute_fact_ids == [
        "sales.leadership.pipeline",
        "sales.tool.priority",
        "development.phdigital.crm",
    ]
    assert gaps["Strategic partnerships / channel Sales experience"].severity == "warning"
    assert {
        "closing",
        "communication",
        "crm",
        "discovery",
        "integrations",
        "new-business",
        "onboarding",
        "pipeline",
        "prospecting",
        "technical",
    } <= set(result.keywords)


def test_every_gap_policy_substitute_resolves_to_a_canonical_fact(fact_store) -> None:
    expected = {
        "sales.company.activity",
        "development.phdigital.role",
        "development.phdigital.fullstack",
        "sales.leadership.pipeline",
        "sales.tool.priority",
        "development.phdigital.crm",
        "sales.cycle.prospecting",
        "sales.achievement.complex_deals",
        "sales.leadership.strategic_customers",
    }
    policy_cases = [
        "must have direct saas sales experience using crm, strategic partnerships, and salesforce",
        "saas sales experience preferred",
    ]
    substitutes = {
        fact_id
        for job_text in policy_cases
        for gap in derive_gaps(job_text, Track.SALES)
        for fact_id in gap.substitute_fact_ids
    }

    assert substitutes == expected
    assert substitutes <= set(fact_store.facts)
    assert all(fact_store.get(fact_id, canonical_only=True) for fact_id in substitutes)


# --------------------------------------------------------------------------
# Requirement extraction and coverage (Stage 1)
# --------------------------------------------------------------------------

#: Faithful to the real Riverside snapshot in every part these tests measure:
#: the responsibilities paragraph, the section heading, all four requirement
#: bullets, and the closing pitch. An abridged copy made the denominator differ
#: from production, which is the one thing a fixture for a coverage metric must
#: not do.
RIVERSIDE_JOB = """About the job
Riverside built an AI-powered platform for content creators.

On your day-to-day:

You will manage the full sales cycle, from lead to close, while driving revenue growth
by refining sales processes and collaborating with Product and Marketing.

Requirements:

What Will Make You Stand Out?

1+ years of sales closing experience in the market (ideally European market) at a
technology company, with a track record of top performance (must).
Native English speaker (multiple languages are a plus).
Quick learner, creative, detail-oriented, positive, and an enthusiastic team player.
Self-starter with strong time management skills, able to work independently.
Excellent verbal and written communication skills, with the ability to engage diverse
stakeholders.
Strong interest in technology, with the ability to thrive in a fast-paced, ambiguous
environment; prior experience in the media industry is a plus.

Bottom line? If you wanna take part in transforming how people share their stories
globally, Riverside's your place.
"""


def _riverside(fact_store, profile_store, requirement_concepts):
    return classify_job(
        RIVERSIDE_JOB,
        facts=fact_store,
        profiles=profile_store,
        concepts=requirement_concepts,
        normalized_hash="riverside",
    )


def _by_concept(analysis):
    return {requirement.concept: requirement for requirement in analysis.requirements}


def test_requirement_ids_are_stable_for_one_snapshot(requirement_concepts) -> None:
    """Re-analysing the same immutable text must not invalidate acceptance."""
    first = extract_requirements(
        RIVERSIDE_JOB, normalized_hash="riverside", concepts=requirement_concepts
    )
    second = extract_requirements(
        RIVERSIDE_JOB, normalized_hash="riverside", concepts=requirement_concepts
    )
    ids = [item.requirement_id for item in first]
    assert ids == [item.requirement_id for item in second]
    assert len(ids) == len(set(ids))


def test_requirement_ids_are_local_to_their_snapshot(requirement_concepts) -> None:
    """Two postings never share a requirement entity, however alike they read."""
    here = {
        item.requirement_id
        for item in extract_requirements(
            RIVERSIDE_JOB, normalized_hash="one", concepts=requirement_concepts
        )
    }
    there = {
        item.requirement_id
        for item in extract_requirements(
            RIVERSIDE_JOB, normalized_hash="two", concepts=requirement_concepts
        )
    }
    assert here.isdisjoint(there)


def test_similar_requirements_in_one_posting_stay_distinct(requirement_concepts) -> None:
    text = "Requirements:\nNative English speaker (must).\nFluent English speaker (must).\n"
    found = extract_requirements(text, normalized_hash="two-demands", concepts=requirement_concepts)
    assert {item.demanded for item in found} == {"native", "fluent"}
    assert len({item.requirement_id for item in found}) == 2


def test_identity_normalization_keeps_qualifiers() -> None:
    """`native`, `3+ years`, `European` are part of what a requirement *is*."""
    assert normalize_span("  Native   English\nspeaker ") == "native english speaker"
    assert normalize_span("3+ Years") == "3+ years"
    assert normalize_span("native english") != normalize_span("fluent english")


def test_extraction_never_receives_the_fact_store() -> None:
    """The boundary is in the signature, not only in the docstring."""
    assert "facts" not in inspect.signature(extract_requirements).parameters
    assert "text" not in inspect.signature(cover_requirements).parameters


def test_threshold_below_demand_is_unsupported_and_still_lists_evidence(
    fact_store, profile_store, requirement_concepts
) -> None:
    """Falling short is not half-met. English is Fluent; the posting wants Native."""
    english = _by_concept(_riverside(fact_store, profile_store, requirement_concepts))[
        "english-proficiency"
    ]
    assert english.mandatory
    assert english.coverage == "unsupported"
    assert english.supporting_fact_ids == ["common.language.english"]


def test_threshold_at_or_above_demand_is_matched(
    fact_store, profile_store, requirement_concepts
) -> None:
    years = _by_concept(_riverside(fact_store, profile_store, requirement_concepts))[
        "sales-closing-experience-years"
    ]
    assert years.mandatory
    assert years.coverage == "matched"


def test_compositional_requirement_with_one_component_missing_is_partial(
    fact_store, profile_store, requirement_concepts
) -> None:
    """One sales fact plus one technology fact does not make technology-company sales."""
    technology = _by_concept(_riverside(fact_store, profile_store, requirement_concepts))[
        "technology-company-sales"
    ]
    assert technology.mandatory
    assert technology.coverage == "partial"
    assert [item.component_id for item in technology.missing_components] == [
        "technology-company-sales-context"
    ]
    assert technology.boundary_fact_ids == ["sales.tech_sales.boundary"]


def test_a_clause_qualifier_governs_its_own_clause_only(
    fact_store, profile_store, requirement_concepts
) -> None:
    """ "(ideally European market)" inside a "(must)" bullet is preferred, not mandatory."""
    by_concept = _by_concept(_riverside(fact_store, profile_store, requirement_concepts))
    assert by_concept["european-market-experience"].mandatory is False
    assert by_concept["media-industry-experience"].mandatory is False
    # The span that swallows the aside must not inherit its "ideally".
    assert by_concept["technology-company-sales"].mandatory is True


def test_mandatory_partial_and_unsupported_both_produce_hard_gaps(
    fact_store, profile_store, requirement_concepts
) -> None:
    analysis = _riverside(fact_store, profile_store, requirement_concepts)
    hard = {gap.requirement for gap in analysis.gaps if gap.severity == "hard"}
    by_concept = _by_concept(analysis)
    assert by_concept["english-proficiency"].text in hard
    assert by_concept["technology-company-sales"].text in hard
    assert analysis.fit.value == "low"


def test_matched_requirements_produce_no_gap(
    fact_store, profile_store, requirement_concepts
) -> None:
    analysis = _riverside(fact_store, profile_store, requirement_concepts)
    matched = {
        requirement.text
        for requirement in analysis.requirements
        if requirement.coverage == "matched"
    }
    assert matched
    assert matched.isdisjoint({gap.requirement for gap in analysis.gaps})


def test_gap_carries_the_requirement_it_projects(
    fact_store, profile_store, requirement_concepts
) -> None:
    """Per-gap acceptance in Stage 3 needs this identity to exist."""
    analysis = _riverside(fact_store, profile_store, requirement_concepts)
    known = {requirement.requirement_id for requirement in analysis.requirements}
    projected = [gap for gap in analysis.gaps if gap.requirement_id is not None]
    assert projected
    assert all(gap.requirement_id in known for gap in projected)


def test_boundary_fact_supplies_the_authoritative_reason(
    fact_store, profile_store, requirement_concepts
) -> None:
    """Canonical Knowledge explains the gap; the engine does not narrate it."""
    analysis = _riverside(fact_store, profile_store, requirement_concepts)
    technology = _by_concept(analysis)["technology-company-sales"]
    gap = next(gap for gap in analysis.gaps if gap.requirement_id == technology.requirement_id)
    assert gap.reason == fact_store.get("sales.tech_sales.boundary").meaning


def test_legacy_analysis_keeps_its_stored_gaps(fact_store) -> None:
    """Immutable history must project exactly as it did before requirements existed."""
    legacy = JobAnalysis.model_validate(
        {
            "track": "sales",
            "profile": "account-executive",
            "emphasis": "new-business",
            "confidence": 0.8,
            "rationale": "stored before requirement coverage existed",
            "fit": "medium",
            "gaps": [
                {"requirement": "Salesforce", "severity": "warning", "reason": "not verified"}
            ],
            "mandatory_requirements": [],
            "preferred_requirements": ["Salesforce"],
            "keywords": [],
            "language": "en",
        }
    )
    assert legacy.extraction_version == "0"
    assert legacy.requirements == []
    assert [gap.requirement for gap in legacy.gaps] == ["Salesforce"]
    assert legacy.gaps[0].requirement_id is None


# --------------------------------------------------------------------------
# Boundary facts limit coverage; they are never evidence for it
# --------------------------------------------------------------------------


def _concept_store(payload_concept: dict) -> RequirementConceptStore:
    return RequirementConceptStore.from_payload(
        {
            "policy_version": "test",
            "extraction_version": "test",
            "requirement_block_markers": ["requirements:"],
            "mandatory_markers": ["(must)"],
            "preferred_markers": ["a plus"],
            "requirement_cues": {"en": ["experience", "native"]},
            "concepts": {"subject": payload_concept},
        },
        origin="boundary regression",
    )


def _coverage(concept_payload: dict, fact_store) -> str:
    concepts = _concept_store(concept_payload)
    extracted = extract_requirements(
        "Requirements:\nWidget selling experience (must).\n",
        normalized_hash="boundary",
        concepts=concepts,
    )
    covered = cover_requirements(extracted, facts=fact_store, concepts=concepts)
    assert covered, "the fixture must extract exactly one requirement"
    return covered[0].coverage


PRESENCE = {
    "label": "Widget selling",
    "kind": "presence",
    "patterns": ["widget selling experience"],
    "satisfied_by_fact_ids": [],
    "satisfied_by_tags": [],
}


def test_a_boundary_fact_cannot_lift_unsupported_to_partial(fact_store) -> None:
    """With no positive evidence, naming a boundary fact changes nothing."""
    without = _coverage({**PRESENCE}, fact_store)
    with_boundary = _coverage(
        {**PRESENCE, "boundary_fact_ids": ["sales.tech_sales.boundary"]}, fact_store
    )
    assert without == "unsupported"
    assert with_boundary == "unsupported"


def test_a_boundary_fact_cannot_satisfy_a_requirement_that_names_it(fact_store) -> None:
    """Naming a boundary fact as its own satisfier must not make it evidence."""
    coverage = _coverage(
        {
            **PRESENCE,
            "satisfied_by_fact_ids": ["sales.tech_sales.boundary"],
            "boundary_fact_ids": ["sales.tech_sales.boundary"],
        },
        fact_store,
    )
    assert coverage == "unsupported"


def test_a_boundary_fact_cannot_satisfy_a_component(fact_store) -> None:
    """The same rule inside a compositional requirement: no free component."""
    compositional = {
        "label": "Widget selling",
        "kind": "compositional",
        "patterns": ["widget selling experience"],
        "components": [
            {
                "component_id": "sales-experience",
                "label": "Sales experience",
                "satisfied_by_tags": ["sales"],
            },
            {
                "component_id": "widget-context",
                "label": "Widget context",
                "satisfied_by_fact_ids": ["sales.tech_sales.boundary"],
            },
        ],
        "boundary_fact_ids": ["sales.tech_sales.boundary"],
    }
    # The first component is genuinely satisfied; the second names only the
    # boundary fact, so it must stay missing and cap the whole at partial.
    assert _coverage(compositional, fact_store) == "partial"


def test_a_boundary_fact_caps_matched_down_to_partial(fact_store) -> None:
    """The one direction a boundary fact may move coverage is downward."""
    satisfied = {**PRESENCE, "satisfied_by_fact_ids": ["sales.summary.new_business"]}
    assert _coverage(satisfied, fact_store) == "matched"
    assert (
        _coverage({**satisfied, "boundary_fact_ids": ["sales.tech_sales.boundary"]}, fact_store)
        == "partial"
    )


def test_a_boundary_fact_cannot_meet_a_threshold(fact_store) -> None:
    """A boundary fact named as a threshold's value source raises no level."""
    threshold = {
        "label": "English proficiency",
        "kind": "threshold",
        "patterns": ["native english speaker"],
        "scale": "language_proficiency",
        "demand_terms": {"native": ["native"]},
        "value_fact_ids": ["common.language.english"],
        "boundary_fact_ids": ["common.language.english"],
    }
    concepts = RequirementConceptStore.from_payload(
        {
            "policy_version": "test",
            "extraction_version": "test",
            "scales": {"language_proficiency": ["basic", "conversational", "fluent", "native"]},
            "requirement_block_markers": ["requirements:"],
            "mandatory_markers": ["(must)"],
            "preferred_markers": ["a plus"],
            "requirement_cues": {"en": ["experience", "native"]},
            "concepts": {"subject": threshold},
        },
        origin="boundary threshold",
    )
    extracted = extract_requirements(
        "Requirements:\nNative English speaker (must).\n",
        normalized_hash="boundary",
        concepts=concepts,
    )
    covered = cover_requirements(extracted, facts=fact_store, concepts=concepts)
    assert covered[0].coverage == "unsupported"


def test_boundary_facts_are_never_listed_as_supporting_evidence(
    fact_store, profile_store, requirement_concepts
) -> None:
    """The two lists must stay disjoint on every requirement, not just this one."""
    analysis = _riverside(fact_store, profile_store, requirement_concepts)
    for requirement in analysis.requirements:
        assert not set(requirement.supporting_fact_ids) & set(requirement.boundary_fact_ids)
    technology = _by_concept(analysis)["technology-company-sales"]
    assert technology.boundary_fact_ids == ["sales.tech_sales.boundary"]
    assert "sales.tech_sales.boundary" not in technology.supporting_fact_ids


def test_no_concept_shadows_a_legacy_rule_gap(fact_store, requirement_concepts) -> None:
    """Concepts and `derive_gaps` rules must not both claim one requirement.

    A concept whose span matches a rule's wording produces a second gap for the
    same requirement, at whatever severity the concept implies - which silently
    hardened the Salesforce and SaaS rules and dropped their substitute facts.
    Derived from the two vocabularies rather than listed, so a newly added
    concept that overlaps a surviving rule fails here instead of shipping.
    """
    rule_probes = [
        "must have proven direct saas sales experience",
        "saas sales experience preferred",
        "experience using a crm system",
        "salesforce experience required",
        "strategic partnerships and distribution partners",
    ]
    for probe in rule_probes:
        rule_gaps = {gap.requirement.casefold() for gap in derive_gaps(probe, Track.SALES)}
        if not rule_gaps:
            continue
        extracted = extract_requirements(
            probe, normalized_hash="shadow-probe", concepts=requirement_concepts
        )
        covered = cover_requirements(extracted, facts=fact_store, concepts=requirement_concepts)
        concept_gaps = {
            requirement.text.casefold()
            for requirement in covered
            if requirement.coverage != "matched"
        }
        overlap = {
            rule
            for rule in rule_gaps
            for concept in concept_gaps
            if rule in concept or concept in rule
        }
        assert not overlap, (
            f"concept vocabulary shadows legacy rule gap(s) {sorted(overlap)} for {probe!r}; "
            "either remove the rule or make the concept carry its substitutes"
        )


# --------------------------------------------------------------------------
# Fit that was never assessed (Stage 2)
# --------------------------------------------------------------------------

#: A posting that plainly states requirements in wording no concept models.
UNREADABLE_JOB = """Senior Account Executive

Requirements:

You must have a demonstrated history of orchestrating stakeholder alignment.
You must have exceptional gravitas in boardroom settings.
Comfort operating amid organisational flux is essential (must).
"""

#: Short, legitimate, and stating no requirements block at all.
THIN_JOB = "Account Executive wanted. Closing and prospecting for new business."


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (FitLevel.UNKNOWN, FitLevel.HIGH, FitLevel.UNKNOWN),
        (FitLevel.HIGH, FitLevel.UNKNOWN, FitLevel.UNKNOWN),
        (FitLevel.UNKNOWN, FitLevel.MEDIUM, FitLevel.UNKNOWN),
        (FitLevel.MEDIUM, FitLevel.UNKNOWN, FitLevel.UNKNOWN),
        (FitLevel.UNKNOWN, FitLevel.UNKNOWN, FitLevel.UNKNOWN),
        (FitLevel.UNKNOWN, FitLevel.LOW, FitLevel.LOW),
        (FitLevel.LOW, FitLevel.UNKNOWN, FitLevel.LOW),
    ],
)
def test_merge_fit_combinations_involving_unknown(left, right, expected) -> None:
    assert merge_fit(left, right) is expected


def test_merge_fit_keeps_the_existing_ordering_for_assessed_levels() -> None:
    assert merge_fit(FitLevel.HIGH, FitLevel.MEDIUM) is FitLevel.MEDIUM
    assert merge_fit(FitLevel.HIGH, FitLevel.HIGH) is FitLevel.HIGH
    assert merge_fit(FitLevel.MEDIUM, FitLevel.LOW) is FitLevel.LOW


def test_low_always_wins_over_unknown() -> None:
    """Evidence of poor Fit is knowledge; a failed assessment must not erase it."""
    for other in FitLevel:
        if other is FitLevel.LOW:
            continue
        assert merge_fit(FitLevel.LOW, other) is FitLevel.LOW
        assert merge_fit(other, FitLevel.LOW) is FitLevel.LOW


def test_unknown_is_not_ranked_on_the_severity_scale() -> None:
    """Giving UNKNOWN a number would let it be compared silently."""
    assert FitLevel.UNKNOWN not in FIT_SEVERITY


def test_a_hard_gap_outranks_a_failed_extraction() -> None:
    hard = [Gap(requirement="Native English", severity="hard", reason="not verified")]
    assert derive_fit(hard, extraction_failed=True) is FitLevel.LOW


def test_extraction_failure_produces_unknown_fit(
    fact_store, profile_store, requirement_concepts
) -> None:
    analysis = classify_job(
        UNREADABLE_JOB,
        facts=fact_store,
        profiles=profile_store,
        concepts=requirement_concepts,
        normalized_hash="unreadable",
    )
    assert analysis.requirements == []
    assert analysis.fit is FitLevel.UNKNOWN


def test_extraction_failure_records_the_reason(
    fact_store, profile_store, requirement_concepts
) -> None:
    analysis = classify_job(
        UNREADABLE_JOB,
        facts=fact_store,
        profiles=profile_store,
        concepts=requirement_concepts,
        normalized_hash="unreadable",
    )
    assert "extraction-failed" in analysis.approval_reasons


def test_extraction_failure_blocks_drafting(
    fact_store, profile_store, requirement_concepts
) -> None:
    """Through the existing ambiguity gate, with no new review code."""
    analysis = classify_job(
        UNREADABLE_JOB,
        facts=fact_store,
        profiles=profile_store,
        concepts=requirement_concepts,
        normalized_hash="unreadable",
    )
    assert analysis.classification_requires_approval is True
    assert "extraction-failed" in unresolved_approval_reasons(analysis)


def test_no_classification_override_settles_a_failed_extraction(
    fact_store, profile_store, requirement_concepts
) -> None:
    """Naming the job does not recover the requirements that could not be read.

    Every override the review form can submit is tried. None may clear it:
    letting one through would unblock drafting from a posting the engine has
    just said it could not understand, which is the failure the reason exists
    to catch. It clears by a later analysis that reads the requirements, and
    otherwise by a deliberate acceptance decision that does not exist yet.
    """
    for override in (
        {"profile_override": "tech-sales"},
        {"track_override": "sales"},
        {"emphasis_override": "balanced-sales"},
        {"language_override": "en"},
    ):
        analysis = classify_job(
            UNREADABLE_JOB,
            facts=fact_store,
            profiles=profile_store,
            concepts=requirement_concepts,
            normalized_hash="unreadable",
            **override,
        )
        assert "extraction-failed" in unresolved_approval_reasons(analysis), override


def test_only_accepting_an_incomplete_analysis_resolves_extraction_failure() -> None:
    """No classification decision answers it, and it answers nothing else.

    The table used to omit `extraction-failed` entirely to say "nothing
    resolves this", which made an absent entry mean two different things - that,
    or a reason someone forgot to register. Now the entry is explicit and names
    the one override that settles it.
    """
    entry = APPROVAL_REASONS["extraction-failed"]
    assert entry.overrides == frozenset({"analysis"})
    assert entry.review_code == ANALYSIS_INCOMPLETE
    # The blanket bypass Stage 3 removed must not come back through this door.
    assert not entry.overrides & {"track", "profile", "emphasis", "language", "fit"}
    assert all(
        "analysis" not in other.overrides
        for name, other in APPROVAL_REASONS.items()
        if name != "extraction-failed"
    )


def test_every_approval_reason_the_engine_records_is_registered() -> None:
    """Derived from the code that emits reasons, not from the table itself.

    A test that iterates the table can only see reasons already in it, so it
    cannot catch the case it exists for: a reason added later and never
    registered. That reason would fall through to the unregistered default and
    be reported as a posting that could not be read, silently, even though a
    decision might well have answered it.

    So the vocabulary is read out of the two modules that record reasons: any
    string assigned to or appended to a `reasons` list is one the projection
    must know how to report.
    """
    emitted: set[str] = set()
    for module in ("classification.py", "approval.py"):
        path = Path(__file__).resolve().parents[1] / "cv_engine" / "domain" / "analysis" / module
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            collect: ast.AST | None = None
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "reasons" for target in node.targets
            ):
                collect = node.value
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "append"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "reasons"
            ):
                collect = node
            if collect is None:
                continue
            emitted.update(
                child.value
                for child in ast.walk(collect)
                if isinstance(child, ast.Constant) and isinstance(child.value, str)
            )

    assert "extraction-failed" in emitted, "the reason vocabulary was not found; fix this guard"
    unregistered = sorted(emitted - set(APPROVAL_REASONS))
    assert not unregistered, (
        "these approval reasons are recorded but not registered in APPROVAL_REASONS, so "
        f"the projection cannot say what resolves them: {unregistered}"
    )


def test_accepting_an_incomplete_analysis_resolves_it_and_nothing_else(
    fact_store, profile_store, requirement_concepts
) -> None:
    """The override answers extraction, leaves Fit unknown, and is its own key."""
    analysis = classify_job(
        UNREADABLE_JOB,
        facts=fact_store,
        profiles=profile_store,
        concepts=requirement_concepts,
        normalized_hash="unreadable",
    )
    assert "extraction-failed" in unresolved_approval_reasons(analysis)

    accepted = JobAnalysis.model_validate(
        {
            **analysis.model_dump(mode="json"),
            "user_override": {"analysis": ACCEPTED_INCOMPLETE_ANALYSIS},
        }
    )
    # It settles extraction and leaves everything else exactly where it was.
    # An unread posting also scores no confidence, and that is a different
    # question with a different answer: this decision does not pretend to know
    # what the job is, so `low-confidence` still stands.
    assert "extraction-failed" not in unresolved_approval_reasons(accepted)
    assert "low-confidence" in unresolved_approval_reasons(accepted)
    # It is a decision to proceed, not a claim that the posting was understood.
    assert accepted.fit is FitLevel.UNKNOWN
    assert accepted.requirements == analysis.requirements
    assert accepted.gaps == analysis.gaps
    # And no classification override reaches it.
    for key in ("track", "profile", "emphasis", "language", "fit"):
        overridden = JobAnalysis.model_validate(
            {**analysis.model_dump(mode="json"), "user_override": {key: "anything"}}
        )
        assert "extraction-failed" in unresolved_approval_reasons(overridden), key


def test_successful_extraction_never_records_extraction_failed(
    fact_store, profile_store, requirement_concepts
) -> None:
    for text, digest in ((RIVERSIDE_JOB, "riverside"), (THIN_JOB, "thin")):
        analysis = classify_job(
            text,
            facts=fact_store,
            profiles=profile_store,
            concepts=requirement_concepts,
            normalized_hash=digest,
        )
        assert "extraction-failed" not in analysis.approval_reasons
        assert analysis.fit is not FitLevel.UNKNOWN


def test_a_short_posting_is_not_punished_for_being_short(fact_store, requirement_concepts) -> None:
    """Nothing was required, so nothing was missed."""
    extracted = extract_requirements(
        THIN_JOB, normalized_hash="thin", concepts=requirement_concepts
    )
    assert extraction_completeness(THIN_JOB, extracted, requirement_concepts) is None
    assert extraction_state(THIN_JOB, extracted, requirement_concepts) == "absent"
    assert extraction_confidence(THIN_JOB, extracted, requirement_concepts) == 1.0


def test_weak_extraction_lowers_confidence_even_when_classification_is_strong(
    fact_store, profile_store, requirement_concepts
) -> None:
    """The product must not let a confident classification carry an unread posting."""
    analysis = classify_job(
        UNREADABLE_JOB,
        facts=fact_store,
        profiles=profile_store,
        concepts=requirement_concepts,
        normalized_hash="unreadable",
    )
    extracted = extract_requirements(
        UNREADABLE_JOB, normalized_hash="unreadable", concepts=requirement_concepts
    )
    strong = classification_confidence(top=4, second=0)
    assert strong > CONFIDENCE_APPROVAL_THRESHOLD
    assert extraction_confidence(UNREADABLE_JOB, extracted, requirement_concepts) == 0.0
    assert analysis.confidence == 0.0


def test_the_two_confidence_components_are_separately_diagnosable(
    fact_store, profile_store, requirement_concepts
) -> None:
    """A low stored confidence must be attributable to one half or the other."""
    analysis = classify_job(
        RIVERSIDE_JOB,
        facts=fact_store,
        profiles=profile_store,
        concepts=requirement_concepts,
        normalized_hash="riverside",
    )
    extracted = extract_requirements(
        RIVERSIDE_JOB, normalized_hash="riverside", concepts=requirement_concepts
    )
    extraction = extraction_confidence(RIVERSIDE_JOB, extracted, requirement_concepts)
    assert 0.0 < extraction < 1.0
    assert analysis.confidence == pytest.approx(
        extraction * (analysis.confidence / extraction), rel=1e-9
    )
    # The product is the stored contract; neither half is recoverable from it
    # alone, which is why both functions stay callable.
    assert analysis.confidence < extraction


def test_a_legacy_analysis_is_never_reinterpreted_as_unknown() -> None:
    """UNKNOWN is for a run that failed, not for records predating the extractor."""
    legacy = JobAnalysis.model_validate(
        {
            "track": "sales",
            "profile": "account-executive",
            "emphasis": "new-business",
            "confidence": 0.8,
            "rationale": "stored before the extractor existed",
            "fit": "medium",
            "gaps": [{"requirement": "Salesforce", "severity": "warning", "reason": "x"}],
            "mandatory_requirements": [],
            "preferred_requirements": ["Salesforce"],
            "keywords": [],
            "language": "en",
        }
    )
    assert legacy.extraction_version == "0"
    assert legacy.requirements == []
    assert legacy.fit is FitLevel.MEDIUM
    assert "extraction-failed" not in legacy.approval_reasons
    # An empty requirement list is not evidence that extraction failed.
    assert derive_fit(legacy.gaps) is FitLevel.MEDIUM
    assert merge_fit(derive_fit(legacy.gaps), legacy.fit) is FitLevel.MEDIUM


# --------------------------------------------------------------------------
# Extraction quality is about understanding, not formatting (Stage 2 revision)
# --------------------------------------------------------------------------

#: Requirements stated entirely in prose, with no block and no `(must)`.
#: Formerly scored 1.0 because no structural marker was found - the false green
#: this rewrite exists to close.
PROSE_JOB = (
    "Account Executive.\n"
    "You have experience closing complex B2B deals, understand enterprise "
    "procurement, and negotiate with senior stakeholders.\n"
)

#: A long responsibilities section and no candidate qualifications at all.
RESPONSIBILITIES_JOB = (
    "About the role.\n"
    "You will own the pipeline and forecast it weekly.\n"
    "You will manage renewals across the book of business.\n"
    "You will work with Marketing on campaign follow-up.\n"
)


def test_requirements_in_prose_are_not_a_free_pass(
    fact_store, profile_store, requirement_concepts
) -> None:
    """No `Requirements:` block does not mean nothing was required."""
    extracted = extract_requirements(
        PROSE_JOB, normalized_hash="prose", concepts=requirement_concepts
    )
    assert requirement_lines(PROSE_JOB, requirement_concepts), "prose still states a requirement"
    assert extraction_state(PROSE_JOB, extracted, requirement_concepts) == "unparsed"

    analysis = classify_job(
        PROSE_JOB,
        facts=fact_store,
        profiles=profile_store,
        concepts=requirement_concepts,
        normalized_hash="prose",
    )
    assert analysis.fit is FitLevel.UNKNOWN
    assert "extraction-failed" in analysis.approval_reasons
    assert analysis.confidence == 0.0


@pytest.mark.parametrize(
    ("job", "state"),
    [
        ("Requirements:\nNative English speaker (must).\n", "parsed"),
        (RIVERSIDE_JOB, "partial"),
        (UNREADABLE_JOB, "unparsed"),
        (PROSE_JOB, "unparsed"),
        (THIN_JOB, "absent"),
        (RESPONSIBILITIES_JOB, "absent"),
    ],
)
def test_the_four_extraction_states(job, state, requirement_concepts) -> None:
    extracted = extract_requirements(job, normalized_hash="states", concepts=requirement_concepts)
    assert extraction_state(job, extracted, requirement_concepts) == state


def test_only_unparsed_is_an_extraction_failure(
    fact_store, profile_store, requirement_concepts
) -> None:
    """`absent` is not a failure: a posting that requires nothing missed nothing."""
    for job, digest in ((THIN_JOB, "thin"), (RESPONSIBILITIES_JOB, "resp"), (RIVERSIDE_JOB, "riv")):
        analysis = classify_job(
            job,
            facts=fact_store,
            profiles=profile_store,
            concepts=requirement_concepts,
            normalized_hash=digest,
        )
        assert "extraction-failed" not in analysis.approval_reasons, job[:40]
        assert analysis.fit is not FitLevel.UNKNOWN


def test_a_responsibility_does_not_enter_the_requirement_denominator(
    requirement_concepts,
) -> None:
    """A long responsibilities section must not make a posting look understood.

    "You will manage the full sales cycle" describes the job, not the
    candidate. It is kept as a statement so the signal survives, but counting
    it as a requirement the extractor understood would inflate completeness for
    every posting with a day-to-day section.
    """
    kinds = {line.kind for line in statement_lines(RESPONSIBILITIES_JOB, requirement_concepts)}
    assert kinds == {"responsibility"}
    assert requirement_lines(RESPONSIBILITIES_JOB, requirement_concepts) == []

    riverside = statement_lines(RIVERSIDE_JOB, requirement_concepts)
    sales_cycle = [line for line in riverside if line.text.startswith("You will manage")]
    assert sales_cycle and sales_cycle[0].kind == "responsibility"


def test_a_you_will_line_alone_is_never_a_requirement(requirement_concepts) -> None:
    """The cue must be a qualification, not a sentence opener."""
    for line in ("You will own the pipeline and forecast it weekly.",):
        found = statement_lines(line, requirement_concepts)
        assert [item.kind for item in found] == ["responsibility"]


@pytest.mark.parametrize("heading", ["Responsibilities:", "Responsibilities"])
def test_a_responsibilities_heading_closes_the_requirement_block(
    heading, requirement_concepts
) -> None:
    """A `Requirements:` heading does not govern the rest of the posting.

    "Own the full sales cycle", printed under `Responsibilities`, is what the
    role does. It was read as a mandatory requirement because the block marker
    above it was still open at that offset and nothing closed it - the section
    was a substring search over everything before the match, not a state the
    posting could leave.

    Punctuated and bare, because postings write it both ways and only the
    colon was recognised at first - which left the bare form latching the
    requirements block open and reproducing the whole defect.
    """
    job = (
        "Requirements:\n"
        "3+ years of sales experience (must).\n"
        "\n"
        f"{heading}\n"
        "Own the full sales cycle from lead to close.\n"
    )
    sections = {line.section for line in requirement_lines(job, requirement_concepts)}
    assert sections == {"requirements"}
    extracted = extract_requirements(job, normalized_hash="sections", concepts=requirement_concepts)
    assert [(item.concept, item.mandatory) for item in extracted] == [
        ("sales-closing-experience-years", True)
    ]


def test_a_requirement_misfiled_under_responsibilities_is_read_but_not_mandatory(
    requirement_concepts,
) -> None:
    """The cue outranks the section; the section still decides what is demanded.

    A qualification stated under the wrong heading is still a qualification,
    so losing it would be the flattering error. It is simply not mandatory for
    having been printed there - only an explicit marker or a requirements
    heading can do that.
    """
    job = (
        "Requirements:\n"
        "3+ years of sales experience (must).\n"
        "\n"
        "Responsibilities\n"
        "You will need experience owning the full sales cycle.\n"
    )
    extracted = extract_requirements(job, normalized_hash="misfiled", concepts=requirement_concepts)
    cycle = next(item for item in extracted if item.concept == "full-sales-cycle")
    assert cycle.mandatory is False


def test_every_configured_heading_works_without_punctuation(requirement_concepts) -> None:
    """Derived from the vocabulary, so a marker cannot be recognised in one form only.

    Only a colon-terminated line was treated as a heading. `Responsibilities`,
    `Nice to have` and `What will make you stand out` are routinely written
    bare, and each one left the section above it latched open: the bullets
    under a bare `Nice to have` came out mandatory, and the bullets under a
    bare `Responsibilities` came out as requirements.
    """
    for heading, expected in requirement_concepts.heading_sections.items():
        job = f"About the job.\n\n{heading}\n- Native English speaker\n"
        under = [
            line
            for line in statement_lines(job, requirement_concepts)
            if line.text == "Native English speaker"
        ]
        assert under, f"{heading!r} swallowed the statement under it"
        assert under[0].section == expected, heading


def test_a_bare_heading_must_be_the_marker_rather_than_contain_it(
    requirement_concepts,
) -> None:
    """The loose match is licensed by the colon, and by nothing else.

    Without that, a requirement ending in "preferred" or "is an advantage" is
    read as a preferred *heading* and disappears from the posting entirely -
    trading one false green for a worse one.
    """
    job = (
        "Requirements:\n"
        "Native English speaker (must).\n"
        "Direct SaaS sales experience is an advantage.\n"
    )
    texts = [line.text for line in requirement_lines(job, requirement_concepts)]
    assert "Direct SaaS sales experience is an advantage." in texts
    assert heading_key("Direct SaaS sales experience is an advantage.") not in (
        requirement_concepts.heading_sections
    )


def test_a_requirement_asked_as_a_question_is_not_a_heading(requirement_concepts) -> None:
    """A question mark alone announces nothing.

    Every `?`-terminated line was discarded as a heading, so a posting that
    asks "Do you have 3+ years of sales experience?" stated no requirements,
    missed none, and scored full confidence. A `?` heading is still recognised
    when it says what the vocabulary knows a heading says.
    """
    asked = "Do you have 3+ years of sales experience?\n"
    assert [line.text for line in requirement_lines(asked, requirement_concepts)] == [asked.strip()]
    extracted = extract_requirements(asked, normalized_hash="asked", concepts=requirement_concepts)
    assert [item.concept for item in extracted] == ["sales-closing-experience-years"]
    assert extraction_state(asked, extracted, requirement_concepts) == "parsed"
    # Riverside's own "What Will Make You Stand Out?" is configured, so it
    # stays a heading and stays out of the denominator.
    assert not any(
        line.text.endswith("?") for line in statement_lines(RIVERSIDE_JOB, requirement_concepts)
    )


def test_headings_and_closing_copy_are_not_requirements(requirement_concepts) -> None:
    """The denominator must be statements, not lines.

    A `?`-terminated heading and the posting's closing pitch were both counted
    once, which made Riverside look less understood than it was.
    """
    texts = [line.text for line in statement_lines(RIVERSIDE_JOB, requirement_concepts)]
    assert not any(text.endswith("?") for text in texts)
    assert not any(text.startswith("Bottom line") for text in texts)


def test_soft_skill_requirements_count_against_completeness(requirement_concepts) -> None:
    """Unmodelled soft skills are missed requirements, not invisible ones."""
    soft = (
        "Requirements:\n"
        "Quick learner, detail-oriented, and an enthusiastic team player.\n"
        "Self-starter with strong time management skills.\n"
    )
    lines = requirement_lines(soft, requirement_concepts)
    assert len(lines) == 2
    extracted = extract_requirements(soft, normalized_hash="soft", concepts=requirement_concepts)
    assert extraction_completeness(soft, extracted, requirement_concepts) == 0.0


def test_marketing_prose_is_not_promoted_into_a_requirement(requirement_concepts) -> None:
    """Explicit cues only - no "adjective-heavy sentence" heuristic."""
    pitch = (
        "The work is challenging, the culture is fast-paced, and the people are "
        "exceptionally brilliant, creative, and driven.\n"
    )
    assert statement_lines(pitch, requirement_concepts) == []


def test_the_two_completeness_measures_are_independently_callable(
    requirement_concepts,
) -> None:
    """A confidence drop must be attributable to one half or the other."""
    extracted = extract_requirements(
        RIVERSIDE_JOB, normalized_hash="riverside", concepts=requirement_concepts
    )
    completeness = extraction_completeness(RIVERSIDE_JOB, extracted, requirement_concepts)
    classified = concept_classification_completeness(extracted)
    assert completeness == 0.5
    assert classified == 1.0
    # Riverside's drop is entirely "read half of what was required", not
    # "read plenty and understood none of it".
    assert extraction_confidence(RIVERSIDE_JOB, extracted, requirement_concepts) == 0.7


def test_a_failed_extraction_earns_no_partial_credit(requirement_concepts) -> None:
    """The coverage floor is credit for reading something; nothing was read."""
    extracted = extract_requirements(
        UNREADABLE_JOB, normalized_hash="unreadable", concepts=requirement_concepts
    )
    assert extraction_completeness(UNREADABLE_JOB, extracted, requirement_concepts) == 0.0
    assert extraction_confidence(UNREADABLE_JOB, extracted, requirement_concepts) == 0.0


def test_a_wrapped_requirement_counts_once(requirement_concepts) -> None:
    """Hard-wrapping a bullet must not make a posting look less understood."""
    one_line = "Requirements:\nNative English speaker with excellent communication skills.\n"
    wrapped = "Requirements:\nNative English speaker with excellent\ncommunication skills.\n"
    assert len(requirement_lines(one_line, requirement_concepts)) == 1
    assert len(requirement_lines(wrapped, requirement_concepts)) == 1
    assert requirement_lines(wrapped, requirement_concepts)[0].text == (
        "Native English speaker with excellent communication skills."
    )


def test_unpunctuated_bullets_are_separate_requirements(requirement_concepts) -> None:
    """A list is a list even when the posting does not punctuate its items.

    Merged into one statement, a run of bullets was one denominator entry that
    any single understood concept satisfied - so a posting stating three
    requirements the vocabulary reads one of scored fully understood. The
    glyph opens the item and is not part of it.
    """
    listed = (
        "Requirements:\n"
        "- Native English speaker\n"
        "- Deep familiarity with programmatic ad tech ecosystems\n"
        "- Comfortable with board-level negotiation\n"
    )
    assert [line.text for line in requirement_lines(listed, requirement_concepts)] == [
        "Native English speaker",
        "Deep familiarity with programmatic ad tech ecosystems",
        "Comfortable with board-level negotiation",
    ]
    extracted = extract_requirements(
        listed, normalized_hash="bullets", concepts=requirement_concepts
    )
    assert [item.concept for item in extracted] == ["english-proficiency"]
    assert extraction_completeness(listed, extracted, requirement_concepts) == pytest.approx(1 / 3)


def test_a_requirement_wrapped_across_a_line_is_counted_as_read(requirement_concepts) -> None:
    """Coverage is offset overlap, not a search for the normalized span.

    Riverside wraps its technology-company requirement across a line. The
    extracted span had that newline collapsed, so searching the posting for it
    found nothing and the requirement it had just been read from was counted
    unread. The bias was conservative and never produced a false green, but it
    understated every posting that hard-wraps a requirement.
    """
    extracted = extract_requirements(
        RIVERSIDE_JOB, normalized_hash="riverside", concepts=requirement_concepts
    )
    technology = next(item for item in extracted if item.concept == "technology-company-sales")
    assert RIVERSIDE_JOB.find(technology.span) == -1, "the span is normalized; the posting is not"
    assert "\n" in RIVERSIDE_JOB[technology.start : technology.end]
    statement = next(
        line
        for line in requirement_lines(RIVERSIDE_JOB, requirement_concepts)
        if line.start <= technology.start < line.end
    )
    assert statement.text.startswith("1+ years of sales closing experience")


def test_the_fixture_denominator_matches_production(requirement_concepts) -> None:
    """The Riverside fixture must measure what the real snapshot measures.

    A coverage metric tested against an abridged copy of its own input proves
    nothing about the input it actually runs on.
    """
    lines = statement_lines(RIVERSIDE_JOB, requirement_concepts)
    assert sum(1 for line in lines if line.kind == "requirement") == 6
    assert sum(1 for line in lines if line.kind == "responsibility") == 1
    extracted = extract_requirements(
        RIVERSIDE_JOB, normalized_hash="riverside", concepts=requirement_concepts
    )
    assert extraction_completeness(RIVERSIDE_JOB, extracted, requirement_concepts) == 0.5


def test_a_requirement_only_the_legacy_rules_understand_is_not_a_failure(
    fact_store, profile_store, requirement_concepts
) -> None:
    """The rules are the other half of requirement understanding, for now.

    A posting whose requirements the concept vocabulary does not model but the
    deterministic gap rules do has been read - incompletely modelled is not
    unreadable. Declaring it failed would block drafting for every posting the
    concepts have not caught up with yet.
    """
    job = "Account Manager.\nYou must have proven direct saas sales experience and salesforce.\n"
    extracted = extract_requirements(job, normalized_hash="rules", concepts=requirement_concepts)
    # The concept vocabulary reads nothing here, and says so on its own terms:
    # the state and the unflagged call are the requirement model's view, and
    # both must keep reporting that it covered none of this posting.
    assert extraction_state(job, extracted, requirement_concepts) == "unparsed"
    assert extraction_failed(job, extracted, requirement_concepts) is True
    # The rules did read it, and only the caller that knows about them may say
    # so - which is why the flag is a parameter rather than a lookup.
    assert (
        extraction_failed(job, extracted, requirement_concepts, understood_elsewhere=True) is False
    )
    # So the analysis is assessed rather than unknown.
    analysis = classify_job(
        job,
        facts=fact_store,
        profiles=profile_store,
        concepts=requirement_concepts,
        normalized_hash="rules",
    )
    assert analysis.gaps
    assert analysis.fit is not FitLevel.UNKNOWN
    assert "extraction-failed" not in analysis.approval_reasons


def test_rule_understanding_earns_the_floor_and_no_more(fact_store, requirement_concepts) -> None:
    """Credit for reading something, without claiming the model covered it."""
    job = "Account Manager.\nYou must have proven direct saas sales experience and salesforce.\n"
    extracted = extract_requirements(job, normalized_hash="rules", concepts=requirement_concepts)
    assert extraction_completeness(job, extracted, requirement_concepts) == 0.0
    assert (
        extraction_confidence(job, extracted, requirement_concepts, understood_elsewhere=True)
        == 0.4
    )
    assert extraction_confidence(job, extracted, requirement_concepts) == 0.0


# --------------------------------------------------------------------------
# Hebrew is a first-class posting language, not an English fallback
# --------------------------------------------------------------------------

#: A Hebrew posting with an explicit requirements block and mandatory markers.
HEBREW_BLOCK_JOB = (
    "דרוש מנהל לקוחות.\n\n"
    "דרישות:\n"
    "ניסיון של 3 שנים במכירות B2B - חובה.\n"
    "שליטה מלאה באנגלית - חובה.\n"
)

#: Hebrew requirements stated in prose, with no block and no marker at all.
HEBREW_PROSE_JOB = (
    "אנחנו מחפשים איש מכירות.\nאתה בעל ניסיון בסגירת עסקאות מורכבות מול ארגונים גדולים.\n"
)

#: Hebrew requirements the concept vocabulary does not model.
HEBREW_UNREADABLE_JOB = (
    "דרישות:\n"
    "נדרשת נוכחות ניהולית יוצאת דופן בחדרי ישיבות.\n"
    "יכולת לתמרן במורכבות ארגונית גבוהה - חובה.\n"
)

#: Hebrew responsibilities and nothing asked of the candidate.
HEBREW_RESPONSIBILITIES_JOB = (
    "על התפקיד.\nהתפקיד כולל אחריות על ניהול צנרת המכירות.\nבמסגרת התפקיד תעבוד מול שיווק ומוצר.\n"
)


def test_hebrew_mandatory_language_is_requirement_bearing(requirement_concepts) -> None:
    """`חובה` and `ניסיון` state a requirement as plainly as `(must)` does."""
    lines = requirement_lines(HEBREW_BLOCK_JOB, requirement_concepts)
    assert len(lines) == 2
    assert all(line.kind == "requirement" for line in lines)


def test_hebrew_prose_requirements_are_not_absent(
    fact_store, profile_store, requirement_concepts
) -> None:
    """No `דרישות:` heading does not mean nothing was required.

    The English false green had a Hebrew twin: a posting whose requirements the
    cue dictionary could not read scored as a posting that required nothing.
    """
    extracted = extract_requirements(
        HEBREW_PROSE_JOB, normalized_hash="he-prose", concepts=requirement_concepts
    )
    assert requirement_lines(HEBREW_PROSE_JOB, requirement_concepts)
    assert extraction_state(HEBREW_PROSE_JOB, extracted, requirement_concepts) != "absent"

    analysis = classify_job(
        HEBREW_PROSE_JOB,
        facts=fact_store,
        profiles=profile_store,
        concepts=requirement_concepts,
        normalized_hash="he-prose",
    )
    assert analysis.language == "he"
    assert analysis.fit is not FitLevel.HIGH


def test_hebrew_unmodelled_requirements_are_unknown_not_high(
    fact_store, profile_store, requirement_concepts
) -> None:
    extracted = extract_requirements(
        HEBREW_UNREADABLE_JOB, normalized_hash="he-unread", concepts=requirement_concepts
    )
    assert extraction_state(HEBREW_UNREADABLE_JOB, extracted, requirement_concepts) == "unparsed"

    analysis = classify_job(
        HEBREW_UNREADABLE_JOB,
        facts=fact_store,
        profiles=profile_store,
        concepts=requirement_concepts,
        normalized_hash="he-unread",
    )
    assert analysis.fit is FitLevel.UNKNOWN
    assert "extraction-failed" in analysis.approval_reasons
    assert analysis.confidence == 0.0


def test_hebrew_responsibilities_do_not_inflate_the_denominator(requirement_concepts) -> None:
    """`התפקיד כולל` describes the role, exactly as `you will` does."""
    lines = statement_lines(HEBREW_RESPONSIBILITIES_JOB, requirement_concepts)
    assert lines
    assert {line.kind for line in lines} == {"responsibility"}
    assert requirement_lines(HEBREW_RESPONSIBILITIES_JOB, requirement_concepts) == []


def test_a_hebrew_title_line_is_not_a_requirement(requirement_concepts) -> None:
    """`דרוש X` opens a posting the way `X wanted` does - it announces the role."""
    assert requirement_lines("דרוש איש מכירות.", requirement_concepts) == []


def test_cue_vocabularies_cover_every_supported_language(requirement_concepts) -> None:
    """Derived from the language contract, so adding a language fails here first.

    `absent` must mean no requirement-bearing language was found in a language
    this product supports - never that the dictionary only knows English.
    """
    payload = json.loads(
        (Path(__file__).resolve().parents[1] / "config" / "requirements.json").read_text(
            encoding="utf-8"
        )
    )
    supported = set(get_args(Language))
    for key in ("requirement_cues", "soft_skill_cues", "responsibility_cues"):
        declared = set(payload[key])
        assert supported <= declared, f"{key} is missing cues for {sorted(supported - declared)}"
        for language in supported:
            assert payload[key][language], f"{key}.{language} is empty"


def test_a_store_with_no_requirement_cues_is_refused() -> None:
    """A vocabulary that cannot read a requirement must not report `absent`.

    With no cues, every posting states nothing, misses nothing and scores full
    confidence - the flattering answer, produced by a store that is simply
    misconfigured. Refusing it at construction is why no caller has to guess
    whether `absent` means "required nothing" or "read nothing".
    """
    with pytest.raises(RequirementConceptError, match="no requirement cues"):
        RequirementConceptStore.from_payload(
            {
                "policy_version": "t",
                "extraction_version": "t",
                "concepts": {"subject": {"kind": "presence", "patterns": ["widget selling"]}},
            },
            origin="cue-less",
        )


def test_english_and_hebrew_cues_are_unioned_not_selected(requirement_concepts) -> None:
    """A mixed-language posting is the normal case, not the exception."""
    mixed = "דרישות:\nניסיון עם Salesforce - חובה.\nNative English speaker required.\n"
    kinds = [line.kind for line in statement_lines(mixed, requirement_concepts)]
    assert kinds == ["requirement", "requirement"]


def test_only_canonical_facts_are_reported_as_supporting_evidence(fact_store) -> None:
    """The same fact, at each status, and only canonical is evidence.

    Asserting that everything returned happens to be canonical proves nothing
    when every candidate in the shipped vocabulary already is - the old code,
    which re-added named facts regardless of status, would have passed it too.
    So the fact is moved through pending, confirmed and canonical and the
    question is asked again at each.
    """
    from cv_engine.domain.analysis.requirements.coverage import _candidate_fact_ids
    from cv_engine.domain.facts import FactStore

    concept = RequirementConceptStore.from_payload(
        {
            "policy_version": "t",
            "extraction_version": "t",
            "requirement_block_markers": ["requirements:"],
            "mandatory_markers": ["(must)"],
            "preferred_markers": ["a plus"],
            "requirement_cues": {"en": ["experience", "native"]},
            "concepts": {
                "subject": {
                    "label": "Subject",
                    "kind": "presence",
                    "patterns": ["widget selling"],
                    "satisfied_by_fact_ids": [],
                    "satisfied_by_tags": [],
                    # Named outright *and* reachable by tag: the old bug lived
                    # in the named branch, so both have to be exercised.
                    "candidate_fact_ids": ["sales.tool.priority"],
                    "candidate_tags": ["widget"],
                }
            },
        },
        origin="status regression",
    ).concepts["subject"]

    named = fact_store.get("sales.tool.priority")
    tagged = fact_store.get("sales.tool.excel").model_copy(
        update={"fact_id": "sales.tool.widget", "tags": ["widget"]}
    )
    for status in (FactStatus.PENDING, FactStatus.CONFIRMED, FactStatus.CANONICAL):
        store = FactStore(
            facts={
                "sales.tool.priority": named.model_copy(update={"status": status}),
                "sales.tool.widget": tagged.model_copy(update={"status": status}),
            },
            source_versions={"sales.md": "v1"},
        )
        found = _candidate_fact_ids(concept, store)
        if status is FactStatus.CANONICAL:
            assert found == ["sales.tool.priority", "sales.tool.widget"], status
        else:
            assert found == [], f"{status.value} facts are not evidence"


def test_the_three_hard_gap_gates_ask_one_question() -> None:
    """State, generation and validation must not be able to disagree.

    They did: the projection reported the blocker while generation drafted past
    it, because each phrased the check itself.

    The guard is deliberately narrow. Filtering gaps by severity is ordinary and
    appears in several honest places - deriving the mandatory requirement list,
    checking that an id names a hard gap. What must exist only once is the
    *combination*: severity together with acceptance. Any module that reads both
    is asking this question, and it must ask it through the one function.
    """
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "cv_engine"
    callers: set[str] = set()
    second_opinions: list[str] = []
    for path in sorted(root.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        name = path.relative_to(root).as_posix()
        if "unaccepted_hard_gaps" in source:
            callers.add(name)
            continue
        if '== "hard"' in source and "accepted_gaps" in source:
            second_opinions.append(name)
        ast.parse(source)
    assert not second_opinions, (
        "these combine gap severity with acceptance themselves instead of using "
        f"unaccepted_hard_gaps: {second_opinions}"
    )
    assert {
        "application/state.py",
        "application/services/drafts/generation.py",
        "domain/validation.py",
        "domain/analysis/gaps.py",
    } <= callers


# --------------------------------------------------------------------------
# The Profile is chosen by what the posting requires (Stage 4)
# --------------------------------------------------------------------------


def test_the_profile_follows_the_evidence_the_posting_calls_for(
    fact_store, profile_store, requirement_concepts
) -> None:
    """Requirement coverage outranks the words in the title.

    Riverside is titled like a closing role, so the vocabulary picked
    `account-executive`. What it actually demands is sales at a technology
    company, and the facts that evidence that are not in that Profile's pool at
    all - so the CV it produced could not speak to the posting's own mandatory
    requirement. The Profile that can is the one chosen now.
    """
    analysis = _riverside(fact_store, profile_store, requirement_concepts)
    assert analysis.profile is ProfileName.TECH_SALES

    # The vocabulary on its own still says otherwise, which is the point: this
    # is not the two signals agreeing, it is coverage outranking the title.
    lowered = RIVERSIDE_JOB.casefold()
    terms = {
        profile: sum(lowered.count(term) for term in vocabulary)
        for profile, vocabulary in PROFILE_TERMS.items()
    }
    assert max(terms, key=lambda name: terms[name]) is ProfileName.ACCOUNT_EXECUTIVE

    scores = requirement_profile_scores(analysis.requirements, profile_store)
    assert scores[ProfileName.TECH_SALES] > scores[ProfileName.ACCOUNT_EXECUTIVE]


def test_a_mandatory_requirement_outweighs_a_preferred_one(
    fact_store, profile_store, requirement_concepts
) -> None:
    """Weighted, so a Profile that answers what is demanded outranks one that
    answers what is merely liked."""
    analysis = _riverside(fact_store, profile_store, requirement_concepts)
    mandatory = [requirement for requirement in analysis.requirements if requirement.mandatory]
    preferred = [requirement for requirement in analysis.requirements if not requirement.mandatory]
    assert mandatory and preferred
    assert (
        requirement_profile_scores(mandatory, profile_store)[ProfileName.TECH_SALES]
        > (requirement_profile_scores(preferred, profile_store)[ProfileName.TECH_SALES])
    )


def test_the_vocabulary_still_decides_a_posting_with_no_requirements_read(
    fact_store, profile_store, requirement_concepts
) -> None:
    """Demoted to a tie-breaker, not removed - and the tie-break is unchanged.

    For a posting the requirement model cannot read, coverage is zero for every
    Profile and the title terms are the only signal there is. Those postings
    must classify exactly as they did, including which Profile wins a tie:
    ordering ties any other way silently reclassifies all of them.
    """
    analysis = classify_job(
        AMBIGUOUS_HEBREW_JOB,
        facts=fact_store,
        profiles=profile_store,
        concepts=requirement_concepts,
        normalized_hash="ambiguous",
    )
    assert analysis.requirements == []
    assert all(score == 0 for score in requirement_profile_scores([], profile_store).values())
    # A three-way tie in the vocabulary, settled by declaration order as it
    # always was.
    assert analysis.profile is ProfileName.ACCOUNT_MANAGER
    assert "ambiguous-signals" in analysis.approval_reasons


def test_coverage_is_decided_before_the_profile_is(
    fact_store, profile_store, requirement_concepts
) -> None:
    """The ordering that keeps the choice from justifying itself.

    Requirements are covered against the whole fact store, so what the posting
    requires and what evidence exists for it are the same answer whichever
    Profile is chosen. If coverage were computed from the chosen Profile's own
    pool, every Profile would look like the right one for the posting it had
    just been used to read.
    """
    default = classify_job(
        RIVERSIDE_JOB,
        facts=fact_store,
        profiles=profile_store,
        concepts=requirement_concepts,
        normalized_hash="riverside",
    )
    for override in ("account-manager", "sdr-bdr", "development"):
        forced = classify_job(
            RIVERSIDE_JOB,
            facts=fact_store,
            profiles=profile_store,
            concepts=requirement_concepts,
            normalized_hash="riverside",
            profile_override=override,
        )
        assert forced.profile.value == override
        assert forced.requirements == default.requirements, override
