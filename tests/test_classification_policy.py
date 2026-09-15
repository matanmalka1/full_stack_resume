"""Classification policy is provider-primary and structurally validated."""

from cv_engine.domain.analysis.assembly import build_analysis
from cv_engine.domain.contracts.analysis import JobClassificationProposal, UnderstandingSources


def test_classification_confidence_does_not_create_a_review_reason(profile_store, fact_store):
    proposal = JobClassificationProposal(
        track="sales",
        profile="account-manager",
        emphasis="account-growth",
        language="en",
        confidence=0.01,
        rationale="uncertain",
        keywords=[],
    )
    analysis = build_analysis(
        requirements=[],
        extraction_version="ai:test",
        extraction_failed=False,
        requirements_absent=False,
        requirements_unmapped=False,
        proposal=proposal,
        profiles=profile_store,
        facts=fact_store,
        unmapped_statements=[],
        understanding=UnderstandingSources(by_ai=0),
    )
    assert analysis.classification_requires_approval is False
    assert analysis.approval_reasons == []
