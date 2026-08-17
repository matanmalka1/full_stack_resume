from __future__ import annotations

from pathlib import Path

import pytest

import cv_engine.infrastructure.rendering as rendering_module
from cv_engine.infrastructure.rendering import validate_rendered as real_validate_rendered
from cv_engine.util import sha256_file
from cv_engine.application.services import WorkflowError
from helpers import ACCOUNT_MANAGER_JOB, artifact_version_and_path


# --- READY ownership ---------------------------------------------------


def test_repository_cannot_manually_set_ready(analyzed_application) -> None:
    engine, app_id = analyzed_application("Repo Ready")
    with pytest.raises(ValueError, match="engine-owned"):
        engine.repo.transition_status(app_id, "ready", "manual bypass attempt")
    assert engine.repo.get_application(app_id)["current_status"] == "preparing"


@pytest.mark.browser
def test_failed_post_render_validation_does_not_set_ready(approved_application, monkeypatch: pytest.MonkeyPatch) -> None:
    engine, app_id = approved_application("Render Failure")

    def failing_validate_rendered(*args, **kwargs):
        report = real_validate_rendered(*args, **kwargs)
        return report.model_copy(update={
            "passed": False,
            "groups": {**report.groups, "ats": False},
        })

    monkeypatch.setattr(rendering_module, "validate_rendered", failing_validate_rendered)
    pdf, report = engine.render(app_id)
    assert not report.passed
    assert engine.repo.get_application(app_id)["current_status"] == "preparing"


def test_set_ready_primitive_rejects_unlinked_pdf_version(v1_repo: Path, approved_application) -> None:
    """Even the internal _set_ready primitive re-derives proof from DB state;
    it cannot be fooled by a PDF version lacking a passing post-render
    validation, even when called directly."""
    engine, app_id = approved_application("Set Ready Bypass")
    _manifest, manifest_path = artifact_version_and_path(
        engine, app_id, v1_repo, "claim_manifest", "approved"
    )
    directory = manifest_path.parent
    fake_pdf = directory / "fake.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")
    fake_version_id = engine.repo.register_artifact_version(
        app_id, "resume_pdf", "resume", fake_pdf.relative_to(v1_repo).as_posix(),
        sha256_file(fake_pdf), "rendered",
    )
    with pytest.raises(ValueError, match="post-render validation"):
        engine.repo._set_ready(app_id, fake_version_id, "bypass attempt")
    assert engine.repo.get_application(app_id)["current_status"] == "preparing"


def test_public_workflow_cannot_restore_ready_after_tamper_without_fresh_render(v1_repo: Path, ready_application) -> None:
    """A historical passing post-render validation must never be sufficient to
    restore READY after filesystem or workflow drift. The only public path back
    to READY is a full Engine.render() call, which always creates brand-new
    artifact versions rather than reusing an old, possibly-stale id; neither
    ready_report() nor submit() may resurrect the old ready state from history."""
    engine, app_id = ready_application("No Stale Restore")
    pdf_version, path = artifact_version_and_path(engine, app_id, v1_repo, "resume_pdf", "rendered")
    engine.repo.transition_status(app_id, "preparing", "reverting for edits")
    path.write_bytes(path.read_bytes() + b"tampered")

    assert engine.repo.get_application(app_id)["current_status"] == "preparing"
    with pytest.raises(WorkflowError, match="not ready"):
        engine.ready_report(app_id)
    with pytest.raises(WorkflowError, match="currently valid ready"):
        engine.submit(app_id)
    # The only supported route back to ready is a full fresh render, which
    # writes a brand-new PDF artifact version rather than reusing the tampered
    # historical one.
    engine.approve(app_id)
    _, report = engine.render(app_id)
    assert report.passed
    new_pdf_version = engine.repo.latest_artifact_version(app_id, "resume_pdf", "rendered")
    assert new_pdf_version["id"] != pdf_version["id"]


# --- Fresh ready verification -------------------------------------------


def test_untouched_ready_application_passes(ready_application) -> None:
    engine, app_id = ready_application("Untouched")
    report = engine.ready_report(app_id)
    assert report.passed, report.model_dump()
    assert all(report.groups.values())


def test_ready_integrity_rejects_missing_or_tampered_registered_artifacts(
    v1_repo: Path, ready_application
) -> None:
    cases = [
        ("resume_pdf", "rendered", "tamper", "pdf-tampered"),
        ("resume_markdown", "approved", "tamper", "approved-markdown-tampered"),
        ("claim_manifest", "approved", "tamper", "approved-manifest-tampered"),
        ("resume_html", "rendered", "tamper", "html-tampered"),
        ("visual_evidence", "rendered", "tamper", "visual-tampered"),
        ("resume_pdf", "rendered", "missing", "pdf-missing"),
        ("resume_html", "rendered", "missing", "html-missing"),
        ("visual_evidence", "rendered", "missing", "visual-missing"),
    ]
    for index, (artifact_type, state, mutation, issue_code) in enumerate(cases):
        engine, app_id = ready_application(f"Artifact Integrity {index}")
        _version, path = artifact_version_and_path(
            engine, app_id, v1_repo, artifact_type, state
        )
        if mutation == "missing":
            path.unlink()
        else:
            path.write_bytes(path.read_bytes() + b"tampered")
        report = engine.ready_report(app_id)
        assert not report.passed, issue_code
        assert any(issue.code == issue_code for issue in report.issues), issue_code


def test_new_revision_snapshot_or_analysis_stales_prior_ready(ready_application) -> None:
    engine, app_id = ready_application("Superseded")
    engine.approve(app_id)
    with pytest.raises(WorkflowError, match="not ready"):
        engine.ready_report(app_id)

    engine, app_id = ready_application("New Snapshot")
    engine.repo.add_job_snapshot(app_id, ACCOUNT_MANAGER_JOB + " Updated requirements.")
    report = engine.ready_report(app_id)
    assert any(issue.code == "new-job-snapshot-since-approval" for issue in report.issues)

    engine, app_id = ready_application("New Analysis")
    engine.analyze(app_id)
    with pytest.raises(WorkflowError, match="not ready"):
        engine.ready_report(app_id)


# --- APPLIED binding ------------------------------------------------------


def test_submission_binds_current_pdf_and_remains_immutable_after_later_versions(
    ready_application
) -> None:
    from cv_engine.infrastructure.db import connect

    engine, app_id = ready_application("Two Cycles")
    first_pdf = engine.repo.latest_artifact_version(app_id, "resume_pdf", "rendered")
    engine.approve(app_id)
    second_pdf_path, second_report = engine.render(app_id)
    assert second_report.passed, second_report.model_dump()
    second_pdf = engine.repo.latest_artifact_version(app_id, "resume_pdf", "rendered")
    assert second_pdf["id"] != first_pdf["id"]
    result = engine.submit(app_id)
    assert result["pdf_artifact_version_id"] == second_pdf["id"]
    submitted_pdf_id = result["pdf_artifact_version_id"]
    with connect(engine.repo.path) as connection:
        before = connection.execute(
            "SELECT artifact_version_id FROM submissions WHERE application_id=?", (app_id,)
        ).fetchall()
    assert [row["artifact_version_id"] for row in before] == [submitted_pdf_id]

    # A later approved version must not rewrite or relink the existing submission.
    engine.approve(app_id)
    with connect(engine.repo.path) as connection:
        after = connection.execute(
            "SELECT artifact_version_id FROM submissions WHERE application_id=?", (app_id,)
        ).fetchall()
    assert [row["artifact_version_id"] for row in after] == [submitted_pdf_id]


def test_generic_status_transition_to_applied_is_always_blocked(ready_application) -> None:
    """The generic transition rejects applied unconditionally -- even supplying
    a real, currently-valid rendered PDF artifact version id must not work,
    because the generic transition has no way to perform the fresh integrity
    verification that Engine.submit() does. There is no parameter that can
    talk it into treating a caller-supplied id as trustworthy."""
    engine, app_id = ready_application("Direct Applied With PDF")
    pdf_version = engine.repo.latest_artifact_version(app_id, "resume_pdf", "rendered")
    with pytest.raises(ValueError, match="submission-owned"):
        engine.repo.transition_status(app_id, "applied", "direct bypass attempt")
    assert engine.repo.get_application(app_id)["current_status"] == "ready"

    # The dedicated internal primitive is the only thing that can persist a
    # submission, and it is not reachable from transition_status at all.
    with pytest.raises(TypeError):
        engine.repo.transition_status(
            app_id, "applied", "direct bypass attempt",
            verified_pdf_artifact_version_id=pdf_version["id"],
        )
    assert engine.repo.get_application(app_id)["current_status"] == "ready"
