"""`requirements_missing_from_document`: covered mandatory demands the CV dropped."""

from __future__ import annotations

from cv_engine.domain.analysis.document_coverage import requirements_missing_from_document
from cv_engine.domain.contracts.analysis import Coverage, Importance, JobAnalysis, Requirement
from cv_engine.domain.contracts.drafts import ClaimLine, DraftDocument, ResumeSection
from cv_engine.domain.contracts.taxonomy import Emphasis, ProfileName, Track


def _claim(claim_id: str, *fact_ids: str) -> ClaimLine:
    return ClaimLine(
        claim_id=claim_id,
        style="bullet",
        text=claim_id,
        fact_ids=list(fact_ids),
        claim_type="canonical",
        text_hash="h",
    )


def _content(*cited: str) -> DraftDocument:
    return DraftDocument(
        application_id="app",
        job_text_hash="b" * 64,
        job_analysis_id="analysis",
        language="en",
        track=Track.DEVELOPMENT,
        profile=ProfileName.DEVELOPMENT,
        emphasis=Emphasis.DEVELOPMENT_BALANCED,
        name="Candidate",
        headline=ClaimLine(
            claim_id="headline",
            style="headline",
            text="headline",
            claim_type="headline",
            text_hash="h",
        ),
        contacts=[],
        sections=[
            ResumeSection(
                name="Experience",
                claims=[_claim(f"c{index}", fact_id) for index, fact_id in enumerate(cited)],
            )
        ],
        fact_store_version="v1",
    )


def _requirement(
    requirement_id: str,
    *supporting: str,
    importance: Importance = "mandatory",
    coverage: Coverage = "matched",
) -> Requirement:
    return Requirement(
        requirement_id=requirement_id,
        text=f"{requirement_id} text",
        importance=importance,
        coverage=coverage,
        supporting_fact_ids=list(supporting),
    )


def _analysis(*requirements: Requirement) -> JobAnalysis:
    return JobAnalysis(
        track=Track.DEVELOPMENT,
        profile=ProfileName.DEVELOPMENT,
        emphasis=Emphasis.DEVELOPMENT_BALANCED,
        language="en",
        summary="fixture",
        requirements=list(requirements),
    )


def _missing_ids(analysis: JobAnalysis, content: DraftDocument | None) -> list[str]:
    return [r.requirement_id for r in requirements_missing_from_document(analysis, content)]


def test_a_matched_or_partial_mandatory_requirement_whose_facts_were_dropped_is_returned() -> None:
    analysis = _analysis(
        _requirement("python", "fact-python"),
        _requirement("sql", "fact-sql", coverage="partial"),
    )
    assert _missing_ids(analysis, _content("fact-other")) == ["python", "sql"]


def test_a_preferred_or_unknown_importance_requirement_is_not_returned() -> None:
    analysis = _analysis(
        _requirement("preferred", "fact-a", importance="preferred"),
        _requirement("unknown", "fact-b", importance="unknown"),
    )
    assert _missing_ids(analysis, _content("fact-other")) == []


def test_an_unsupported_or_unknown_coverage_requirement_is_not_returned() -> None:
    analysis = _analysis(
        _requirement("unsupported", "fact-a", coverage="unsupported"),
        _requirement("unknown", "fact-b", coverage="unknown"),
    )
    assert _missing_ids(analysis, _content("fact-other")) == []


def test_one_supporting_fact_still_cited_is_enough() -> None:
    analysis = _analysis(_requirement("python", "fact-dropped", "fact-kept"))
    assert _missing_ids(analysis, _content("fact-kept")) == []


def test_a_requirement_with_no_supporting_facts_is_not_returned() -> None:
    analysis = _analysis(_requirement("python"))
    assert _missing_ids(analysis, _content("fact-other")) == []


def test_a_document_without_content_has_dropped_nothing() -> None:
    analysis = _analysis(_requirement("python", "fact-python"))
    assert _missing_ids(analysis, None) == []
