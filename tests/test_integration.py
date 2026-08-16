from __future__ import annotations

import json
from pathlib import Path

from cv_engine.db import connect
from cv_engine.workflow import Engine
from helpers import ACCOUNT_MANAGER_JOB, working_claim as _working_claim


def test_default_flow_stops_for_review_then_reaches_ready(engine: Engine) -> None:
    app_id, snapshot_id = engine.ingest(
        "Acme",
        "Account Manager",
        ACCOUNT_MANAGER_JOB,
    )
    engine.analyze(app_id)
    markdown, manifest, report = engine.draft(app_id)
    assert report.passed
    assert markdown.is_file() and manifest.is_file()
    assert engine.repo.get_application(app_id)["current_status"] == "preparing"
    assert engine.repo.artifact_versions(app_id) == []
    approved = engine.approve(app_id)
    assert approved["version"] == 1
    pdf, ready = engine.render(app_id)
    assert ready.passed, ready.model_dump()
    assert pdf.name == "Matan Malka - Account Manager - CV.pdf"
    assert engine.repo.get_application(app_id)["current_status"] == "ready"
    assert engine.ready_report(app_id).passed
    decision = engine.repo.latest_decision(app_id)
    assert decision["job_snapshot_id"] == snapshot_id
    submission_result = engine.submit(app_id, "submitted to employer")
    assert submission_result["current_status"] == "applied"
    with connect(engine.repo.path) as connection:
        submission = connection.execute("SELECT artifact_version_id FROM submissions WHERE application_id=?", (app_id,)).fetchone()
    assert submission is not None
    assert submission["artifact_version_id"] == submission_result["pdf_artifact_version_id"]


def test_csv_export(engine: Engine, tmp_path: Path) -> None:
    from cv_engine.cli import export_csv

    app_id, _ = engine.ingest("Acme", "Developer", "Python developer role")
    output = export_csv(engine.repo, tmp_path / "applications.csv")
    text = output.read_text(encoding="utf-8")
    assert "current_status" in text
    assert app_id in text


def test_validate_extracts_safe_manual_markdown_wording(drafted_application) -> None:
    setup = drafted_application("Manual Edit")
    engine, app_id = setup
    markdown = setup.markdown
    claim = _working_claim(engine, app_id, "sales.metric.performance")
    markdown.write_text(
        markdown.read_text(encoding="utf-8").replace(claim.text, claim.text.rstrip("."), 1),
        encoding="utf-8",
    )

    report = engine.validate_working(app_id)

    assert report.passed, report.model_dump()
    assert _working_claim(engine, app_id, "sales.metric.performance").claim_type == "derived"


def test_validate_preserves_unsupported_manual_markdown_as_pending(drafted_application) -> None:
    setup = drafted_application("Pending Edit")
    engine, app_id = setup
    markdown = setup.markdown
    claim = _working_claim(engine, app_id, "sales.metric.performance")
    markdown.write_text(
        markdown.read_text(encoding="utf-8").replace(
            claim.text,
            "Delivered 30% improvement in direct SaaS Sales.",
            1,
        ),
        encoding="utf-8",
    )

    report = engine.validate_working(app_id)

    assert not report.passed
    assert any(issue.code == "pending-claim" for issue in report.issues)
    assert _working_claim(engine, app_id, "sales.metric.performance").claim_type == "pending"


def test_cli_exposes_style_safe_composite_edit(drafted_application, cli_runner) -> None:
    engine, app_id = drafted_application("Composite CLI")
    claim = _working_claim(engine, app_id, "sales.metric.recurring_customers")

    result = cli_runner(
        "edit-claim",
        app_id,
        claim.claim_id,
        "--template",
        "canonical-renderings",
        "--fact-id",
        "sales.metric.recurring_customers",
        "--fact-id",
        "sales.metric.performance",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert _working_claim(engine, app_id, "sales.metric.recurring_customers").claim_type == "composite"


def test_render_revalidates_approved_markdown_before_browser(approved_application) -> None:
    from cv_engine.workflow import WorkflowError

    setup = approved_application("Acme", "Developer", "Python backend developer API React")
    engine, app_id = setup
    approved = setup.approved
    markdown = approved["directory"] / "resume.md"
    markdown.write_text(markdown.read_text(encoding="utf-8") + "\nUnsupported claim.\n", encoding="utf-8")
    try:
        engine.render(app_id)
    except WorkflowError as exc:
        assert "approved Markdown" in str(exc)
    else:
        raise AssertionError("modified approved source reached rendering")


def test_cli_fast_mode_completes_definition_of_done(cli_runner) -> None:
    result = cli_runner(
        "fast",
        "--company",
        "CLI Example",
        "--role",
        "Account Manager",
        "--job-text",
        ACCOUNT_MANAGER_JOB,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ready"] is True
    assert Path(payload["pdf"]).is_file()
