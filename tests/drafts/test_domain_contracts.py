"""Irrecoverable domain contradictions checked on the models themselves."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cv_engine.domain.contracts.analysis import JobAnalysis
from cv_engine.domain.contracts.validation import (
    ValidationIssue,
    ValidationReport,
)


def test_a_draft_cannot_rewrite_the_provenance_it_is_judged_against(draft_factory) -> None:
    setup = draft_factory("Python backend developer API React", profile_override="development")
    draft = setup.draft

    for field, value in (
        ("schema_version", "1.0"),
        ("fact_store_version", "0" * 64),
        ("application_id", "another-application"),
        ("job_snapshot_id", "another-snapshot"),
        ("job_analysis_id", "another-analysis"),
    ):
        with pytest.raises(ValidationError, match="frozen"):
            setattr(draft, field, value)

    # The digest is derived from the Markdown, so it stays assignable: the
    # controlled mutation paths reseal it, and the validation boundary is what
    # catches a digest that no longer describes the document — not this model.
    draft.content_hash = "0" * 64

    without_analysis = draft.model_dump(mode="json")
    without_analysis.pop("job_analysis_id")
    with pytest.raises(ValidationError, match="job_analysis_id"):
        type(draft).model_validate(without_analysis)

    old_schema = draft.model_dump(mode="json")
    old_schema["schema_version"] = "1.1"
    with pytest.raises(ValidationError, match="schema_version"):
        type(draft).model_validate(old_schema)


def test_a_validation_reports_pass_is_derived_from_its_findings() -> None:
    """`passed` gates approval and Ready on its own, so it may not contradict
    the findings it summarizes.

    A report may not claim a pass over a failed group or a hard issue; the
    factory keeps a pass that only soft warnings accompany, and turns a hard
    issue no group recorded into a failure without inventing the group.
    """
    for groups, issues in [
        ({"content": False}, []),
        ({"content": True}, [ValidationIssue(group="content", code="stale-claim", message="x")]),
    ]:
        with pytest.raises(ValidationError, match="claims to have passed"):
            ValidationReport(passed=True, groups=groups, issues=issues)

    soft = ValidationReport.from_findings(
        groups={"profile": True},
        issues=[
            ValidationIssue(
                group="profile",
                code="future-soft-finding",
                message="x",
                hard=False,
            )
        ],
        evidence={"source": "characterization"},
    )
    assert soft.passed
    assert soft.evidence == {"source": "characterization"}

    unpaired = ValidationReport.from_findings(
        groups={"content": True},
        issues=[ValidationIssue(group="content", code="future-hard-finding", message="x")],
    )
    assert not unpaired.passed
    assert unpaired.groups == {"content": True}


def test_an_analysis_refuses_an_override_it_cannot_act_on(draft_factory) -> None:
    """A key nothing routes on would sit in the record looking like a decision.

    `fit` and `analysis` used to be accepted because they cleared the low-Fit
    and incomplete-analysis approval reasons. Neither reason exists, so both
    keys are refused along with any other the engine has no use for.
    """
    analysis = draft_factory(
        "Python backend developer API React", profile_override="development"
    ).analysis
    payload = analysis.model_dump(mode="json")

    with pytest.raises(ValidationError):
        JobAnalysis.model_validate({**payload, "user_override": {"seniority": "senior"}})

    with pytest.raises(ValidationError):
        JobAnalysis.model_validate({**payload, "user_override": {"fit": "accepted-low-fit"}})

    accepted = JobAnalysis.model_validate({**payload, "user_override": {"profile": "development"}})
    assert accepted.user_override["profile"] == "development"
