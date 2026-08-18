"""States the domain contracts refuse to hold, checked on the models themselves.

These are the invariants no caller can restore once broken: a fact store with
two facts under one ID, a draft that rewrites the provenance it is judged
against, and a report that claims a pass its own contents deny. Each is checked
at construction rather than at a call site, so the guarantee does not depend on
which layer happens to build the value.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from cv_engine.domain.models import (
    EmphasisPolicy,
    Emphasis,
    Fact,
    FactSource,
    FactStatus,
    JobAnalysis,
    ValidationIssue,
    ValidationReport,
)


def _fact(fact_id: str, rendering: str) -> Fact:
    return Fact(
        fact_id=fact_id,
        meaning=rendering,
        renderings={"en": rendering},
        tags=["development"],
        status=FactStatus.CANONICAL,
        provenance="test",
        resume_style="bullet",
    )


def test_a_fact_source_refuses_two_facts_under_one_id() -> None:
    """One fact, one canonical location — refused where facts are stored.

    Every consumer indexes a source by `fact_id`, so a repeat would make the
    later record win silently and turn the earlier one into an uneditable
    second copy of the same claim.
    """
    with pytest.raises(ValidationError, match="repeats fact IDs"):
        FactSource(
            source_version="1",
            facts=[_fact("common.python", "Python"), _fact("common.python", "Python 3")],
        )


def test_a_draft_cannot_rewrite_the_provenance_it_is_judged_against(draft_factory) -> None:
    setup = draft_factory("Python backend developer API React")
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


@pytest.mark.parametrize(
    "groups, issues",
    [
        ({"content": False}, []),
        ({"content": True}, [ValidationIssue(group="content", code="stale-claim", message="x")]),
    ],
    ids=["failed-group", "hard-issue"],
)
def test_a_validation_report_cannot_claim_a_pass_it_did_not_earn(groups, issues) -> None:
    """`passed` gates approval and Ready on its own, so it may not contradict
    the findings it summarizes."""
    with pytest.raises(ValidationError, match="claims to have passed"):
        ValidationReport(passed=True, groups=groups, issues=issues)


def test_a_reported_warning_still_passes() -> None:
    """A soft issue is a permitted warning: it is reported, not a blocker."""
    report = ValidationReport(
        passed=True,
        groups={"profile": True},
        issues=[ValidationIssue(group="profile", code="emphasis-coverage-low", message="x", hard=False)],
    )
    assert report.passed


def test_validation_report_factory_preserves_a_soft_warning_pass() -> None:
    issue = ValidationIssue(
        group="profile",
        code="emphasis-coverage-low",
        message="x",
        hard=False,
    )

    report = ValidationReport.from_findings(
        groups={"profile": True},
        issues=[issue],
        evidence={"source": "characterization"},
    )

    assert report.passed
    assert report.evidence == {"source": "characterization"}


def test_validation_report_factory_turns_an_unpaired_hard_issue_into_failure() -> None:
    report = ValidationReport.from_findings(
        groups={"content": True},
        issues=[ValidationIssue(group="content", code="future-hard-finding", message="x")],
    )

    assert not report.passed
    assert report.groups == {"content": True}


def test_legacy_validation_report_json_round_trips_without_a_shape_change() -> None:
    legacy = {
        "passed": True,
        "groups": {"filename": True},
        "issues": [],
        "evidence": {"phase": "pre-render"},
    }

    report = ValidationReport.model_validate_json(json.dumps(legacy))

    assert report.model_dump(mode="json") == legacy
    assert "report_schema_version" not in report.model_dump(mode="json")


def test_an_emphasis_policy_refuses_a_negative_coverage_expectation() -> None:
    with pytest.raises(ValidationError):
        EmphasisPolicy(emphasis=Emphasis.NEW_BUSINESS, tag_weights={"sales": 3}, minimum_coverage=-1)


def test_an_analysis_refuses_an_override_it_cannot_act_on(draft_factory) -> None:
    """An override is what clears an approval reason. A key nothing routes on
    would sit in the record looking like a decision while resolving nothing."""
    analysis = draft_factory("Python backend developer API React").analysis
    payload = analysis.model_dump(mode="json")

    with pytest.raises(ValidationError):
        JobAnalysis.model_validate({**payload, "user_override": {"seniority": "senior"}})

    accepted = JobAnalysis.model_validate({**payload, "user_override": {"fit": "accepted-low-fit"}})
    assert accepted.user_override["fit"] == "accepted-low-fit"
