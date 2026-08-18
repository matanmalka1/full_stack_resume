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


def test_set_ready_primitive_rejects_unlinked_pdf_version(
    v1_repo: Path, approved_application
) -> None:
    """Even the internal _set_ready primitive re-derives proof from DB state;
    it cannot be fooled by a PDF version lacking a passing post-render
    validation, even when called directly."""
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
    )
    with pytest.raises(ValueError, match="post-render validation"):
        services.repository._set_ready(app_id, fake_version_id, "bypass attempt")
    assert services.repository.get_application(app_id)["current_status"] == "preparing"


def test_public_workflow_cannot_restore_ready_after_tamper_without_fresh_render(
    v1_repo: Path, ready_application
) -> None:
    """A historical passing post-render validation must never be sufficient to
    restore READY after filesystem or workflow drift. The only public path back
    to READY is a full RenderingService.render() call, which always creates brand-new
    artifact versions rather than reusing an old, possibly-stale id; neither
    ready_report() nor submit() may resurrect the old ready state from history."""
    services, app_id = ready_application("No Stale Restore")
    pdf_version, path = artifact_version_and_path(services, app_id, "resume_pdf", "rendered")
    services.repository.transition_status(app_id, "preparing", "reverting for edits")
    path.write_bytes(path.read_bytes() + b"tampered")

    assert services.repository.get_application(app_id)["current_status"] == "preparing"
    with pytest.raises(WorkflowError, match="not ready"):
        services.rendering.ready_report(app_id)
    with pytest.raises(WorkflowError, match="currently valid ready"):
        services.tracking.submit(app_id)
    # The only supported route back to ready is a full fresh render, which
    # writes a brand-new PDF artifact version rather than reusing the tampered
    # historical one.
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


def test_new_revision_snapshot_or_analysis_stales_prior_ready(ready_application) -> None:
    services, app_id = ready_application("Superseded")
    _start_new_draft(services, app_id)
    services.drafts.approve(app_id)
    from cv_engine.infrastructure.persistence import connect

    with connect(services.repository.path) as connection:
        reason = connection.execute(
            "SELECT reason FROM status_history WHERE application_id=? ORDER BY id DESC LIMIT 1",
            (app_id,),
        ).fetchone()["reason"]
    assert reason == "new approved version requires fresh rendering and ready validation"
    with pytest.raises(WorkflowError, match="not ready"):
        services.rendering.ready_report(app_id)

    services, app_id = ready_application("New Snapshot")
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
    report = services.rendering.ready_report(app_id)
    assert any(issue.code == "new-job-snapshot-since-approval" for issue in report.issues)

    services, app_id = ready_application("New Analysis")
    _reanalyze(services, app_id)
    with connect(services.repository.path) as connection:
        reason = connection.execute(
            "SELECT reason FROM status_history WHERE application_id=? ORDER BY id DESC LIMIT 1",
            (app_id,),
        ).fetchone()["reason"]
    assert reason == "new analysis invalidated the prior ready version"
    with pytest.raises(WorkflowError, match="not ready"):
        services.rendering.ready_report(app_id)


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
    assert services.repository.get_application(app_id)["current_status"] == "ready"

    # The dedicated internal primitive is the only thing that can persist a
    # submission, and it is not reachable from transition_status at all.
    with pytest.raises(TypeError):
        services.repository.transition_status(
            app_id,
            "applied",
            "direct bypass attempt",
            verified_pdf_artifact_version_id=pdf_version["id"],
        )
    assert services.repository.get_application(app_id)["current_status"] == "ready"
