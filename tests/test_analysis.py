"""Focused tests for the active, AI-only analysis domain."""

from __future__ import annotations

import pytest

from cv_engine.domain.analysis.assembly import build_analysis, rebase_requirements
from cv_engine.domain.analysis.gaps import fit_score_for
from cv_engine.domain.contracts.analysis import (
    JobClassificationProposal,
    Requirement,
    UnderstandingSources,
)


def _proposal(**changes) -> JobClassificationProposal:
    return JobClassificationProposal.model_validate(
        {
            "track": "sales",
            "profile": "account-manager",
            "emphasis": "account-growth",
            "language": "en",
            "confidence": 0.91,
            "rationale": "provider rationale",
            "keywords": ["retention"],
            **changes,
        }
    )


def test_fit_score_for_is_the_single_empty_analysis_policy() -> None:
    assert fit_score_for([], extraction_failed=True, requirements_absent=False) is None
    assert fit_score_for([], extraction_failed=False, requirements_absent=True) is None
    assert fit_score_for([], extraction_failed=False, requirements_absent=False) == 1.0


def test_ai_analysis_is_built_without_rule_or_concept_gaps(profile_store, fact_store) -> None:
    requirement = Requirement(
        requirement_id="r1",
        text="Own enterprise accounts",
        kind="presence",
        mandatory=True,
        coverage="unsupported",
    )
    analysis = build_analysis(
        requirements=[requirement],
        extraction_version="ai:test",
        extraction_failed=False,
        requirements_absent=False,
        requirements_unmapped=False,
        proposal=_proposal(),
        profiles=profile_store,
        facts=fact_store,
        unmapped_statements=[],
        understanding=UnderstandingSources(by_ai=1),
    )
    assert analysis.analysis_version == "2.0"
    assert [gap.requirement_id for gap in analysis.gaps] == ["r1"]
    assert analysis.fit.value == "low"
    assert analysis.language == "en"


def test_inconsistent_provider_classification_is_refused(profile_store, fact_store) -> None:
    with pytest.raises(ValueError, match="inconsistent"):
        build_analysis(
            requirements=[],
            extraction_version="ai:test",
            extraction_failed=False,
            requirements_absent=True,
            requirements_unmapped=False,
            proposal=_proposal(track="development"),
            profiles=profile_store,
            facts=fact_store,
            unmapped_statements=[],
            understanding=UnderstandingSources(by_ai=0),
        )


def test_rebase_uses_fit_score_for(profile_store, fact_store) -> None:
    analysis = build_analysis(
        requirements=[],
        extraction_version="ai:test",
        extraction_failed=False,
        requirements_absent=True,
        requirements_unmapped=False,
        proposal=_proposal(),
        profiles=profile_store,
        facts=fact_store,
        unmapped_statements=[],
        understanding=UnderstandingSources(by_ai=0),
    )
    rebased = rebase_requirements(
        analysis,
        requirements=[],
        extraction_version=analysis.extraction_version,
        facts=fact_store,
        extraction_failed=True,
        requirements_absent=False,
        requirements_unmapped=False,
    )
    assert rebased.fit_score is None
    assert rebased.fit.value == "unknown"


def test_low_classification_confidence_does_not_create_a_review_reason(
    profile_store, fact_store
) -> None:
    analysis = build_analysis(
        requirements=[],
        extraction_version="ai:test",
        extraction_failed=False,
        requirements_absent=False,
        requirements_unmapped=False,
        proposal=_proposal(confidence=0.01, rationale="uncertain", keywords=[]),
        profiles=profile_store,
        facts=fact_store,
        unmapped_statements=[],
        understanding=UnderstandingSources(by_ai=0),
    )
    assert analysis.approval_reasons == []
