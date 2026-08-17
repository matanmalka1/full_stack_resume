from __future__ import annotations

import json
from pathlib import Path

import pytest

import cv_engine.workflow as workflow_module
from cv_engine.rendering import validate_rendered as real_validate_rendered
from cv_engine.util import sha256_file, sha256_text
from cv_engine.workflow import WorkflowError
from helpers import ACCOUNT_MANAGER_JOB, artifact_version_and_path


# --- READY ownership ---------------------------------------------------


def test_cli_cannot_manually_set_ready(v1_repo: Path, analyzed_application, cli_runner) -> None:
    engine, app_id = analyzed_application("CLI Ready")
    result = cli_runner("status", app_id, "ready")
    assert result.returncode != 0
    assert "invalid choice" in result.stderr or "invalid choice" in result.stdout
    assert engine.repo.get_application(app_id)["current_status"] == "preparing"


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

    monkeypatch.setattr(workflow_module, "validate_rendered", failing_validate_rendered)
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


def test_registering_unvalidated_pdf_after_ready_does_not_pass_inspection(v1_repo: Path, ready_application) -> None:
    """A newer resume_pdf artifact registered without its own passing post-render
    validation must not be treated as ready, even though it sorts as 'latest'."""
    engine, app_id = ready_application("Stray Artifact")
    _manifest, manifest_path = artifact_version_and_path(
        engine, app_id, v1_repo, "claim_manifest", "approved"
    )
    directory = manifest_path.parent
    stray_pdf = directory / "stray.pdf"
    stray_pdf.write_bytes(b"%PDF-1.4 stray")
    engine.repo.register_artifact_version(
        app_id, "resume_pdf", "resume", stray_pdf.relative_to(v1_repo).as_posix(),
        sha256_file(stray_pdf), "rendered",
    )
    report = engine.ready_report(app_id)
    assert not report.passed
    assert any(issue.code == "no-post-render-validation" for issue in report.issues)
    with pytest.raises(WorkflowError, match="stale or tampered"):
        engine.submit(app_id)


# --- Fresh ready verification -------------------------------------------


def test_untouched_ready_application_passes(ready_application) -> None:
    engine, app_id = ready_application("Untouched")
    report = engine.ready_report(app_id)
    assert report.passed, report.model_dump()
    assert all(report.groups.values())


def test_deleted_pdf_fails_ready_inspection(v1_repo: Path, ready_application) -> None:
    engine, app_id = ready_application("Deleted PDF")
    _pdf_version, path = artifact_version_and_path(engine, app_id, v1_repo, "resume_pdf", "rendered")
    path.unlink()
    report = engine.ready_report(app_id)
    assert not report.passed
    assert any(issue.code == "pdf-missing" for issue in report.issues)


def test_tampered_pdf_bytes_fail_ready_inspection(v1_repo: Path, ready_application) -> None:
    engine, app_id = ready_application("Tampered PDF")
    _pdf_version, path = artifact_version_and_path(engine, app_id, v1_repo, "resume_pdf", "rendered")
    path.write_bytes(path.read_bytes() + b"tampered")
    report = engine.ready_report(app_id)
    assert not report.passed
    assert any(issue.code == "pdf-tampered" for issue in report.issues)


def test_tampered_approved_markdown_fails_ready_inspection(v1_repo: Path, ready_application) -> None:
    engine, app_id = ready_application("Tampered Markdown")
    _markdown_version, path = artifact_version_and_path(
        engine, app_id, v1_repo, "resume_markdown", "approved"
    )
    path.write_text(path.read_text(encoding="utf-8") + "\nUnsupported extra claim.\n", encoding="utf-8")
    report = engine.ready_report(app_id)
    assert not report.passed
    assert any(issue.code == "approved-markdown-tampered" for issue in report.issues)


def test_tampered_approved_manifest_fails_ready_inspection(v1_repo: Path, ready_application) -> None:
    engine, app_id = ready_application("Tampered Manifest")
    _manifest_version, path = artifact_version_and_path(
        engine, app_id, v1_repo, "claim_manifest", "approved"
    )
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    report = engine.ready_report(app_id)
    assert not report.passed
    assert any(issue.code == "approved-manifest-tampered" for issue in report.issues)


def test_tampered_html_fails_ready_inspection(v1_repo: Path, ready_application) -> None:
    engine, app_id = ready_application("Tampered HTML")
    _html_version, path = artifact_version_and_path(engine, app_id, v1_repo, "resume_html", "rendered")
    path.write_text(path.read_text(encoding="utf-8") + "<!-- tampered -->", encoding="utf-8")
    report = engine.ready_report(app_id)
    assert not report.passed
    assert any(issue.code == "html-tampered" for issue in report.issues)


def test_tampered_visual_evidence_fails_ready_inspection(v1_repo: Path, ready_application) -> None:
    engine, app_id = ready_application("Tampered Visual")
    _visual_version, path = artifact_version_and_path(
        engine, app_id, v1_repo, "visual_evidence", "rendered"
    )
    path.write_bytes(path.read_bytes() + b"tampered")
    report = engine.ready_report(app_id)
    assert not report.passed
    assert any(issue.code == "visual-tampered" for issue in report.issues)


def test_missing_html_fails_ready_inspection(v1_repo: Path, ready_application) -> None:
    engine, app_id = ready_application("Missing HTML")
    _html_version, path = artifact_version_and_path(engine, app_id, v1_repo, "resume_html", "rendered")
    path.unlink()
    report = engine.ready_report(app_id)
    assert not report.passed
    assert any(issue.code == "html-missing" for issue in report.issues)


def test_missing_visual_evidence_fails_ready_inspection(v1_repo: Path, ready_application) -> None:
    engine, app_id = ready_application("Missing Visual")
    _visual_version, path = artifact_version_and_path(
        engine, app_id, v1_repo, "visual_evidence", "rendered"
    )
    path.unlink()
    report = engine.ready_report(app_id)
    assert not report.passed
    assert any(issue.code == "visual-missing" for issue in report.issues)


def test_newer_approved_version_stales_prior_ready(ready_application) -> None:
    """A newer approved version demotes ready until that version is rendered."""
    engine, app_id = ready_application("Superseded")
    engine.approve(app_id)  # approves a second version without re-rendering it
    assert engine.repo.get_application(app_id)["current_status"] == "preparing"
    with pytest.raises(WorkflowError, match="not ready"):
        engine.ready_report(app_id)


def test_new_job_snapshot_stales_prior_ready(ready_application) -> None:
    engine, app_id = ready_application("New Snapshot")
    engine.repo.add_job_snapshot(app_id, ACCOUNT_MANAGER_JOB + " Updated requirements.")
    report = engine.ready_report(app_id)
    assert not report.passed
    assert any(issue.code == "new-job-snapshot-since-approval" for issue in report.issues)


def test_new_analysis_stales_prior_ready(ready_application) -> None:
    engine, app_id = ready_application("New Analysis")
    engine.analyze(app_id)
    assert engine.repo.get_application(app_id)["current_status"] == "preparing"
    with pytest.raises(WorkflowError, match="not ready"):
        engine.ready_report(app_id)


# --- APPLIED binding ------------------------------------------------------


def test_applied_binds_to_current_version_after_two_ready_cycles(ready_application) -> None:
    engine, app_id = ready_application("Two Cycles")
    first_pdf = engine.repo.latest_artifact_version(app_id, "resume_pdf", "rendered")
    engine.approve(app_id)
    second_pdf_path, second_report = engine.render(app_id)
    assert second_report.passed, second_report.model_dump()
    second_pdf = engine.repo.latest_artifact_version(app_id, "resume_pdf", "rendered")
    assert second_pdf["id"] != first_pdf["id"]
    result = engine.submit(app_id)
    assert result["pdf_artifact_version_id"] == second_pdf["id"]


def test_submitted_artifact_remains_immutable_after_later_version(ready_application) -> None:
    from cv_engine.db import connect

    engine, app_id = ready_application("Immutable Submission")
    result = engine.submit(app_id)
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


def test_fabricated_headline_typed_claim_cannot_reach_ready(v1_repo: Path, drafted_application) -> None:
    """A fabricated bullet marked claim_type='headline' with no fact_ids must never be approved."""
    setup = drafted_application("Headline Bypass")
    engine, app_id = setup.engine, setup.application_id
    working = v1_repo / "artifacts/working" / app_id
    payload = json.loads((working / "resume.claims.json").read_text(encoding="utf-8"))
    text = 'Closed a NIS 4.2M SaaS enterprise deal.'
    payload["sections"][-1]["claims"].append({
        "claim_id": "injected-fabrication",
        "style": "bullet",
        "text": text,
        "fact_ids": [],
        "claim_type": "headline",
        "text_hash": sha256_text(text),
        "template_id": None,
        "template_version": None,
        "derivation_id": None,
        "derivation_version": None,
        "pending_reason": None,
    })
    (working / "resume.claims.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="only the document headline"):
        engine.approve(app_id)
    assert engine.repo.get_application(app_id)["current_status"] == "preparing"
    approved = v1_repo / "artifacts" / app_id
    assert not approved.exists()
