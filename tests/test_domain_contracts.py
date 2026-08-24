"""Irrecoverable domain contradictions checked on the models themselves."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cv_engine.domain.models import (
    DraftDocument,
    JobAnalysis,
    ReadyQualification,
    SelectionManifest,
    SelectionPlan,
    ValidationIssue,
    ValidationReport,
    ValidationRunLineage,
    WorkingDraft,
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


def test_a_validation_report_cannot_claim_a_pass_it_did_not_earn() -> None:
    cases = [
        ({"content": False}, []),
        ({"content": True}, [ValidationIssue(group="content", code="stale-claim", message="x")]),
    ]
    """`passed` gates approval and Ready on its own, so it may not contradict
    the findings it summarizes."""
    for groups, issues in cases:
        with pytest.raises(ValidationError, match="claims to have passed"):
            ValidationReport(passed=True, groups=groups, issues=issues)


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


def test_ready_qualification_cannot_claim_a_result_its_evidence_did_not_earn() -> None:
    failed = ValidationReport.from_findings(groups={"rendered_artifacts": False}, issues=[])
    with pytest.raises(ValidationError, match="derived from its validation evidence"):
        ReadyQualification(
            application_id="application-1",
            approved_revision_id="revision-1",
            pdf_artifact_version_id="pdf-1",
            ready_qualified=True,
            validation=failed,
        )

    passed = ValidationReport.from_findings(groups={"rendered_artifacts": True}, issues=[])
    with pytest.raises(ValidationError, match="exact PDF"):
        ReadyQualification(
            application_id="application-1",
            approved_revision_id="revision-1",
            ready_qualified=True,
            validation=passed,
        )


def test_preparation_records_preserve_exact_domain_lineage(draft_factory) -> None:
    draft: DraftDocument = draft_factory("Python backend developer API React").draft
    manifest = draft.selection
    assert isinstance(manifest, SelectionManifest)

    plan = SelectionPlan(
        id="plan-1",
        application_id=draft.application_id,
        job_analysis_id=draft.job_analysis_id or "",
        version_number=1,
        plan=manifest,
        candidate_context_version="candidate-v1",
        candidate_context_hash="candidate-hash",
        profile_version="profile-v1",
        selection_policy_version="selection-v1",
        track_emphasis_dependencies={
            "track": "track-v1",
            "emphasis": "emphasis-v1",
        },
        created_at="2026-08-18T00:00:00Z",
    )
    working = WorkingDraft(
        id="draft-1",
        application_id=draft.application_id,
        job_analysis_id=plan.job_analysis_id,
        selection_plan_id=plan.id,
        source=draft,
        edit_version=3,
        content_hash="caller-supplied-hash",
        active=True,
        created_at="2026-08-18T00:00:00Z",
        updated_at="2026-08-18T00:01:00Z",
    )
    lineage = ValidationRunLineage(
        working_draft_id=working.id,
        edit_version=working.edit_version,
        content_hash=working.content_hash,
        job_snapshot_id=draft.job_snapshot_id,
        job_analysis_id=working.job_analysis_id,
        selection_plan_id=working.selection_plan_id,
        knowledge_context_hash="knowledge-hash",
        validator_versions={"draft": "2.0"},
    )

    assert plan.plan is manifest
    assert working.source is draft
    assert working.parent_revision_id is None
    assert working.content_hash == "caller-supplied-hash"
    assert lineage.model_dump() == {
        "working_draft_id": "draft-1",
        "edit_version": 3,
        "content_hash": "caller-supplied-hash",
        "job_snapshot_id": draft.job_snapshot_id,
        "job_analysis_id": plan.job_analysis_id,
        "selection_plan_id": "plan-1",
        "knowledge_context_hash": "knowledge-hash",
        "validator_versions": {"draft": "2.0"},
    }


def test_an_analysis_refuses_an_override_it_cannot_act_on(draft_factory) -> None:
    """An override is what clears an approval reason. A key nothing routes on
    would sit in the record looking like a decision while resolving nothing."""
    analysis = draft_factory("Python backend developer API React").analysis
    payload = analysis.model_dump(mode="json")

    with pytest.raises(ValidationError):
        JobAnalysis.model_validate({**payload, "user_override": {"seniority": "senior"}})

    accepted = JobAnalysis.model_validate({**payload, "user_override": {"fit": "accepted-low-fit"}})
    assert accepted.user_override["fit"] == "accepted-low-fit"
