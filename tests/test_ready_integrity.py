from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from helpers import ACCOUNT_MANAGER_JOB, approve_active_draft, artifact_version_and_path
from sqlalchemy import func, select

import cv_engine.infrastructure.rendering as rendering_module
from cv_engine.application.commands import (
    AnalyzeCommand,
    DraftCommand,
    ExternalSubmissionCommand,
    RecruitmentCorrectionCommand,
    RecruitmentStatusCommand,
    SubmissionCommand,
)
from cv_engine.application.errors import WorkflowError
from cv_engine.infrastructure.persistence.tables import submissions
from cv_engine.infrastructure.rendering import validate_rendered as real_validate_rendered
from cv_engine.util import normalized_text, sha256_file, sha256_text, verify_payload


def _submission_command(services, application_id: str) -> SubmissionCommand:
    revision = services.repository.latest_approved_revision(application_id)
    pdf = services.repository.artifact_version_for_revision(revision.id, "resume_pdf", "rendered")
    return SubmissionCommand(
        application_id=application_id,
        approved_revision_id=revision.id,
        pdf_artifact_version_id=pdf["id"],
        submitted_at="2026-08-19T10:00:00+00:00",
    )


def _reanalyze(services, application_id: str):
    return services.analysis.analyze(
        AnalyzeCommand(
            application_id=application_id,
            job_snapshot_id=services.repository.latest_snapshot(application_id)["id"],
        )
    )


def _start_new_draft(services, application_id: str):
    analysis_id, _analysis = services.repository.latest_analysis(application_id)
    plan = services.repository.latest_selection_plan(application_id)
    return services.drafts.draft(
        DraftCommand(
            application_id=application_id,
            job_analysis_id=analysis_id,
            selection_plan_id=plan.id,
        )
    )


def test_payload_verification_classifies_ok_missing_and_tampered(tmp_path: Path) -> None:
    path = tmp_path / "payload"
    assert verify_payload(path, "unused") == "missing"
    path.write_bytes(b"original")
    expected = sha256_file(path)
    assert verify_payload(path, expected) == "ok"
    path.write_bytes(b"tampered")
    assert verify_payload(path, expected) == "tampered"


# --- READY ownership ---------------------------------------------------


def test_repository_cannot_manually_set_ready(analyzed_application) -> None:
    services, app_id = analyzed_application("Repo Ready")
    assert not hasattr(services.repository, "transition_status")
    with pytest.raises(WorkflowError):
        services.tracking.transition_status(
            RecruitmentStatusCommand(application_id=app_id, target_status="ready")
        )
    assert services.repository.get_application(app_id)["current_status"] == "saved"


@pytest.mark.browser
def test_failed_post_render_validation_does_not_set_ready(
    approved_application, monkeypatch: pytest.MonkeyPatch
) -> None:
    services, app_id = approved_application("Render Failure")

    def failing_validate_rendered(*args, **kwargs):
        report = real_validate_rendered(*args, **kwargs)
        return report.model_copy(
            update={
                "passed": False,
                "groups": {**report.groups, "ats": False},
            }
        )

    monkeypatch.setattr(rendering_module, "validate_rendered", failing_validate_rendered)
    rendered = services.rendering.render(app_id)
    assert not rendered.validation.passed
    assert services.repository.get_application(app_id)["current_status"] == "saved"
    assert not services.rendering.ready_qualification(app_id).ready_qualified


def test_no_repository_primitive_can_assert_ready_for_unlinked_pdf(
    workspace_root: Path, approved_application
) -> None:
    """Ready has no write primitive and exact stored proof is always re-derived."""
    services, app_id = approved_application("Set Ready Bypass")
    _manifest, manifest_path = artifact_version_and_path(
        services, app_id, "claim_manifest", "approved"
    )
    directory = manifest_path.parent
    fake_pdf = directory / "fake.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")
    fake_version_id = services.repository.register_artifact_version(
        app_id,
        "resume_pdf",
        "resume",
        fake_pdf.relative_to(workspace_root).as_posix(),
        sha256_file(fake_pdf),
        "rendered",
        revision_id=services.repository.latest_approved_revision(app_id).id,
    )
    assert not hasattr(services.repository, "set_ready")
    assert not hasattr(services.repository, "_set_ready")
    qualification = services.rendering.ready_qualification(
        app_id,
        pdf_artifact_version_id=fake_version_id,
    )
    assert not qualification.ready_qualified
    assert any(
        issue.code == "no-post-render-validation" for issue in qualification.validation.issues
    )
    assert services.repository.get_application(app_id)["current_status"] == "saved"


def test_public_workflow_cannot_restore_ready_after_tamper_without_fresh_render(
    workspace_root: Path, ready_application
) -> None:
    """Stored validation alone cannot qualify a tampered immutable artifact."""
    services, app_id = ready_application("No Stale Restore")
    pdf_version, path = artifact_version_and_path(services, app_id, "resume_pdf", "rendered")
    path.write_bytes(path.read_bytes() + b"tampered")

    assert services.repository.get_application(app_id)["current_status"] == "saved"
    assert not services.rendering.ready_qualification(app_id).ready_qualified
    with pytest.raises(WorkflowError, match="tampered Ready evidence"):
        services.tracking.submit_application(_submission_command(services, app_id))
    # A new revision and render create new immutable evidence; the old PDF is
    # never reused or relinked.
    _start_new_draft(services, app_id)
    approve_active_draft(services, app_id)
    rendered = services.rendering.render(app_id)
    assert rendered.validation.passed
    new_pdf_version = services.repository.latest_artifact_version(app_id, "resume_pdf", "rendered")
    assert new_pdf_version["id"] != pdf_version["id"]


# --- Fresh ready verification -------------------------------------------


def test_untouched_ready_application_passes(ready_application) -> None:
    services, app_id = ready_application("Untouched")
    report = services.rendering.ready_report(app_id)
    assert report.passed, report.model_dump()
    assert all(report.groups.values())


def test_ready_integrity_rejects_missing_or_tampered_registered_artifacts(
    workspace_root: Path, ready_application
) -> None:
    cases = [
        ("resume_pdf", "rendered", "tamper", "pdf-tampered", "rendered_artifacts"),
        ("resume_markdown", "approved", "tamper", "approved-markdown-tampered", "approved_source"),
        ("claim_manifest", "approved", "tamper", "approved-manifest-tampered", "approved_source"),
        ("resume_html", "rendered", "tamper", "html-tampered", "rendered_artifacts"),
        ("visual_evidence", "rendered", "tamper", "visual-tampered", "rendered_artifacts"),
        ("resume_pdf", "rendered", "missing", "pdf-missing", "rendered_artifacts"),
        ("resume_html", "rendered", "missing", "html-missing", "rendered_artifacts"),
        ("visual_evidence", "rendered", "missing", "visual-missing", "rendered_artifacts"),
    ]
    for index, (artifact_type, state, mutation, issue_code, issue_group) in enumerate(cases):
        services, app_id = ready_application(f"Artifact Integrity {index}")
        _version, path = artifact_version_and_path(services, app_id, artifact_type, state)
        if mutation == "missing":
            path.unlink()
        else:
            path.write_bytes(path.read_bytes() + b"tampered")
        report = services.rendering.ready_report(app_id)
        assert not report.passed, issue_code
        issue = next(issue for issue in report.issues if issue.code == issue_code)
        assert issue.group == issue_group
        assert report.groups[issue_group] is False


def test_ready_qualification_is_independent_of_active_context(ready_application) -> None:
    services, app_id = ready_application("Superseded")
    old_revision = services.repository.latest_approved_revision(app_id)
    old_pdf = services.repository.artifact_version_for_revision(
        old_revision.id, "resume_pdf", "rendered"
    )
    _start_new_draft(services, app_id)
    new_revision = approve_active_draft(services, app_id)
    assert not services.rendering.ready_qualification(app_id).ready_qualified
    old_qualification = services.rendering.ready_qualification(
        app_id, old_revision.id, old_pdf["id"]
    )
    assert old_qualification.ready_qualified

    new_text = ACCOUNT_MANAGER_JOB + " Updated requirements."
    snapshot_id = str(uuid.uuid4())
    payload = services.payloads.commit_snapshot(app_id, snapshot_id, new_text)
    services.repository.add_job_snapshot(
        app_id,
        payload.reference,
        payload.sha256,
        sha256_text(normalized_text(new_text)),
        snapshot_id=snapshot_id,
    )
    _reanalyze(services, app_id)
    assert services.rendering.ready_qualification(
        app_id, old_revision.id, old_pdf["id"]
    ).ready_qualified
    assert services.repository.latest_approved_revision(app_id).id == new_revision.revision_id
    submitted = services.tracking.submit_application(
        SubmissionCommand(
            application_id=app_id,
            approved_revision_id=old_revision.id,
            pdf_artifact_version_id=old_pdf["id"],
            submitted_at="2026-08-19T10:00:00+00:00",
        )
    )
    assert submitted.current_status == "applied"
    assert submitted.warnings == [
        "READY_REVISION_FOR_OLDER_SNAPSHOT",
        "READY_REVISION_FOR_OLDER_ANALYSIS",
    ]


# --- APPLIED binding ------------------------------------------------------


def test_submission_binds_current_pdf_and_remains_immutable_after_later_versions(
    ready_application,
) -> None:
    services, app_id = ready_application("Two Cycles")
    first_pdf = services.repository.latest_artifact_version(app_id, "resume_pdf", "rendered")
    _start_new_draft(services, app_id)
    approve_active_draft(services, app_id)
    second_render = services.rendering.render(app_id)
    assert second_render.validation.passed, second_render.validation.model_dump()
    second_pdf = services.repository.latest_artifact_version(app_id, "resume_pdf", "rendered")
    assert second_pdf["id"] != first_pdf["id"]
    revision = services.repository.latest_approved_revision(app_id)
    result = services.tracking.submit_application(
        SubmissionCommand(
            application_id=app_id,
            approved_revision_id=revision.id,
            pdf_artifact_version_id=second_pdf["id"],
            submitted_at="2026-08-19T10:00:00+00:00",
        )
    )
    assert result.pdf_artifact_version_id == second_pdf["id"]
    submitted_pdf_id = result.pdf_artifact_version_id
    with services.repository.read_connection() as connection:
        before = (
            connection.execute(
                select(submissions.c.artifact_version_id).where(
                    submissions.c.application_id == app_id
                )
            )
            .scalars()
            .all()
        )
    assert before == [submitted_pdf_id]

    # A later approved version must not rewrite or relink the existing submission.
    _start_new_draft(services, app_id)
    approve_active_draft(services, app_id)
    with services.repository.read_connection() as connection:
        after = (
            connection.execute(
                select(submissions.c.artifact_version_id).where(
                    submissions.c.application_id == app_id
                )
            )
            .scalars()
            .all()
        )
    assert after == [submitted_pdf_id]


def test_submission_and_applied_transition_roll_back_together(
    ready_application, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cv_engine.infrastructure.persistence.tracking import SqlAlchemyTrackingRepository

    services, app_id = ready_application("Atomic Submission")

    def fail_status_write(*_args, **_kwargs) -> None:
        raise RuntimeError("injected status failure")

    monkeypatch.setattr(SqlAlchemyTrackingRepository, "insert_recruitment_event", fail_status_write)
    with pytest.raises(RuntimeError, match="injected status failure"):
        services.tracking.submit_application(_submission_command(services, app_id))

    with services.repository.read_connection() as connection:
        count = connection.execute(
            select(func.count())
            .select_from(submissions)
            .where(submissions.c.application_id == app_id)
        ).scalar_one()
    assert count == 0
    assert services.repository.get_application(app_id)["current_status"] == "saved"


def test_generic_status_transition_to_applied_is_always_blocked(ready_application) -> None:
    """The generic transition rejects applied unconditionally -- even supplying
    a real, currently-valid rendered PDF artifact version id must not work,
    because the generic transition has no way to perform the fresh integrity
    verification that TrackingService.submit() does. There is no parameter that can
    talk it into treating a caller-supplied id as trustworthy."""
    services, app_id = ready_application("Direct Applied With PDF")
    with pytest.raises(WorkflowError, match="submission-owned"):
        services.tracking.transition_status(
            RecruitmentStatusCommand(
                application_id=app_id,
                target_status="applied",
                reason="direct bypass attempt",
            )
        )
    assert services.repository.get_application(app_id)["current_status"] == "saved"


def test_external_submission_never_fabricates_revision_or_artifact(analyzed_application) -> None:
    services, app_id = analyzed_application("External Submission")
    first = services.tracking.record_external_submission(
        ExternalSubmissionCommand(
            application_id=app_id,
            submitted_at="2026-08-19T10:00:00+00:00",
            metadata={"source": "email confirmation"},
        )
    )
    second = services.tracking.record_external_submission(
        ExternalSubmissionCommand(
            application_id=app_id,
            submitted_at="2026-08-19T11:00:00+00:00",
        )
    )
    assert first.current_status == second.current_status == "applied"
    submissions = services.repository.submissions(app_id)
    assert len(submissions) == 2
    assert all(row["submission_type"] == "external" for row in submissions)
    assert all(row["approved_revision_id"] is None for row in submissions)
    assert all(row["artifact_version_id"] is None for row in submissions)
    applied_events = [
        row
        for row in services.repository.recruitment_events(app_id)
        if row["to_status"] == "applied"
    ]
    assert len(applied_events) == 1


def test_correction_is_append_only_and_terminal_outcome_survives_closed(
    analyzed_application,
) -> None:
    services, app_id = analyzed_application("Correction History")
    withdrawn = services.tracking.transition_status(
        RecruitmentStatusCommand(
            application_id=app_id,
            target_status="withdrawn",
            reason="mistaken entry",
            occurred_at="2026-08-19T10:00:00+00:00",
        )
    )
    assert withdrawn.terminal_outcome == "withdrawn"
    with pytest.raises(WorkflowError, match="reason is required"):
        services.tracking.correct_recruitment_status(
            RecruitmentCorrectionCommand(
                application_id=app_id,
                target_status="interview",
                corrects_event_id=withdrawn.event_id or "",
                reason=" ",
            )
        )
    corrected = services.tracking.correct_recruitment_status(
        RecruitmentCorrectionCommand(
            application_id=app_id,
            target_status="interview",
            corrects_event_id=withdrawn.event_id or "",
            reason="status was entered on the wrong application",
            occurred_at="2026-08-19T10:05:00+00:00",
        )
    )
    assert corrected.current_status == "interview"
    assert corrected.terminal_outcome is None
    events = services.repository.recruitment_events(app_id)
    original = next(row for row in events if row["id"] == withdrawn.event_id)
    correction = next(row for row in events if row["id"] == corrected.event_id)
    assert original["to_status"] == "withdrawn"
    assert correction["corrects_event_id"] == original["id"]
    assert correction["reason"] == "status was entered on the wrong application"

    for target in ("offer", "accepted", "closed"):
        closed = services.tracking.transition_status(
            RecruitmentStatusCommand(application_id=app_id, target_status=target)
        )
    assert closed.current_status == "closed"
    assert closed.terminal_outcome == "accepted"


def test_approval_audit_and_decision_markdown_are_exact(approved_application) -> None:
    setup = approved_application("Decision Export")
    revision_id = setup.approved.revision_id
    exported = setup.services.drafts.export_decision_markdown(setup.application_id, revision_id)
    assert exported.approved_revision_id == revision_id
    assert f"`{revision_id}`" in exported.content
    assert "## Exact lineage" in exported.content
    assert sha256_text(exported.content) == exported.content_hash
    audits = setup.services.repository.audit_records(setup.application_id)
    approval = next(row for row in audits if row["action"] == "approve_draft")
    assert approval["entity_id"] == revision_id
