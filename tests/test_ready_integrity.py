from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from helpers import ACCOUNT_MANAGER_JOB, artifact_version_and_path

import cv_engine.infrastructure.rendering as rendering_module
from cv_engine.application.commands import AnalyzeCommand, DraftCommand
from cv_engine.application.errors import WorkflowError
from cv_engine.infrastructure.rendering import validate_rendered as real_validate_rendered
from cv_engine.util import normalized_text, sha256_file, sha256_text, verify_payload


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
    with pytest.raises(ValueError, match="engine-owned"):
        services.repository.transition_status(app_id, "ready", "manual bypass attempt")
    assert services.repository.get_application(app_id)["current_status"] == "preparing"


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
    assert services.repository.get_application(app_id)["current_status"] == "preparing"
    assert not services.rendering.ready_qualification(app_id).ready_qualified


def test_no_repository_primitive_can_assert_ready_for_unlinked_pdf(
    v1_repo: Path, approved_application
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
        fake_pdf.relative_to(v1_repo).as_posix(),
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
    assert services.repository.get_application(app_id)["current_status"] == "preparing"


def test_public_workflow_cannot_restore_ready_after_tamper_without_fresh_render(
    v1_repo: Path, ready_application
) -> None:
    """Stored validation alone cannot qualify a tampered immutable artifact."""
    services, app_id = ready_application("No Stale Restore")
    pdf_version, path = artifact_version_and_path(services, app_id, "resume_pdf", "rendered")
    path.write_bytes(path.read_bytes() + b"tampered")

    assert services.repository.get_application(app_id)["current_status"] == "preparing"
    assert not services.rendering.ready_qualification(app_id).ready_qualified
    with pytest.raises(WorkflowError, match="tampered ready state"):
        services.tracking.submit(app_id)
    # A new revision and render create new immutable evidence; the old PDF is
    # never reused or relinked.
    _start_new_draft(services, app_id)
    services.drafts.approve(app_id)
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
    v1_repo: Path, ready_application
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
    new_revision = services.drafts.approve(app_id)
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


# --- APPLIED binding ------------------------------------------------------


def test_submission_binds_current_pdf_and_remains_immutable_after_later_versions(
    ready_application,
) -> None:
    from cv_engine.infrastructure.persistence import connect

    services, app_id = ready_application("Two Cycles")
    first_pdf = services.repository.latest_artifact_version(app_id, "resume_pdf", "rendered")
    _start_new_draft(services, app_id)
    services.drafts.approve(app_id)
    second_render = services.rendering.render(app_id)
    assert second_render.validation.passed, second_render.validation.model_dump()
    second_pdf = services.repository.latest_artifact_version(app_id, "resume_pdf", "rendered")
    assert second_pdf["id"] != first_pdf["id"]
    result = services.tracking.submit(app_id)
    assert result.pdf_artifact_version_id == second_pdf["id"]
    submitted_pdf_id = result.pdf_artifact_version_id
    with connect(services.repository.path) as connection:
        before = connection.execute(
            "SELECT artifact_version_id FROM submissions WHERE application_id=?", (app_id,)
        ).fetchall()
    assert [row["artifact_version_id"] for row in before] == [submitted_pdf_id]

    # A later approved version must not rewrite or relink the existing submission.
    _start_new_draft(services, app_id)
    services.drafts.approve(app_id)
    with connect(services.repository.path) as connection:
        after = connection.execute(
            "SELECT artifact_version_id FROM submissions WHERE application_id=?", (app_id,)
        ).fetchall()
    assert [row["artifact_version_id"] for row in after] == [submitted_pdf_id]


def test_submission_and_applied_transition_roll_back_together(
    ready_application, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cv_engine.infrastructure.persistence import connect
    from cv_engine.infrastructure.persistence.applications import SqliteApplicationRepository

    services, app_id = ready_application("Atomic Submission")

    def fail_status_write(*_args, **_kwargs) -> None:
        raise RuntimeError("injected status failure")

    monkeypatch.setattr(SqliteApplicationRepository, "_set_status", fail_status_write)
    with pytest.raises(RuntimeError, match="injected status failure"):
        services.tracking.submit(app_id)

    with connect(services.repository.path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM submissions WHERE application_id=?", (app_id,)
        ).fetchone()[0]
    assert count == 0
    assert services.repository.get_application(app_id)["current_status"] == "preparing"


def test_generic_status_transition_to_applied_is_always_blocked(ready_application) -> None:
    """The generic transition rejects applied unconditionally -- even supplying
    a real, currently-valid rendered PDF artifact version id must not work,
    because the generic transition has no way to perform the fresh integrity
    verification that TrackingService.submit() does. There is no parameter that can
    talk it into treating a caller-supplied id as trustworthy."""
    services, app_id = ready_application("Direct Applied With PDF")
    pdf_version = services.repository.latest_artifact_version(app_id, "resume_pdf", "rendered")
    with pytest.raises(ValueError, match="submission-owned"):
        services.repository.transition_status(app_id, "applied", "direct bypass attempt")
    assert services.repository.get_application(app_id)["current_status"] == "preparing"

    # No caller-supplied proof can turn the generic transition into submission.
    with pytest.raises(TypeError):
        services.repository.transition_status(
            app_id,
            "applied",
            "direct bypass attempt",
            verified_pdf_artifact_version_id=pdf_version["id"],
        )
    assert services.repository.get_application(app_id)["current_status"] == "preparing"
