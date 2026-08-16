from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from cv_engine.db import connect
from cv_engine.drafts import load_draft
from cv_engine.workflow import Engine


def test_default_flow_stops_for_review_then_reaches_ready(v1_repo: Path) -> None:
    engine = Engine(v1_repo)
    app_id, snapshot_id = engine.ingest(
        "Acme",
        "Account Manager",
        "Account Manager responsible for retention, portfolio growth, negotiation, and customer relationships.",
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
    engine.repo.transition_status(app_id, "applied", "submitted to employer")
    with connect(engine.repo.path) as connection:
        submission = connection.execute("SELECT artifact_version_id FROM submissions WHERE application_id=?", (app_id,)).fetchone()
    assert submission is not None


def test_csv_export(v1_repo: Path, tmp_path: Path) -> None:
    from cv_engine.cli import export_csv

    engine = Engine(v1_repo)
    app_id, _ = engine.ingest("Acme", "Developer", "Python developer role")
    output = export_csv(engine.repo, tmp_path / "applications.csv")
    text = output.read_text(encoding="utf-8")
    assert "current_status" in text
    assert app_id in text


def _working_claim(engine: Engine, application_id: str, fact_id: str):
    manifest = engine.root / "artifacts/working" / application_id / "resume.claims.json"
    draft = load_draft(manifest)
    return next(
        claim
        for section in draft.sections
        for claim in section.claims
        if fact_id in claim.fact_ids
    )


def test_validate_extracts_safe_manual_markdown_wording(v1_repo: Path) -> None:
    engine = Engine(v1_repo)
    app_id, _ = engine.ingest(
        "Manual Edit",
        "Account Manager",
        "Account Manager responsible for retention, portfolio growth, negotiation, and customer relationships.",
    )
    engine.analyze(app_id)
    markdown, _manifest, _report = engine.draft(app_id)
    claim = _working_claim(engine, app_id, "sales.metric.performance")
    markdown.write_text(
        markdown.read_text(encoding="utf-8").replace(claim.text, claim.text.rstrip("."), 1),
        encoding="utf-8",
    )

    report = engine.validate_working(app_id)

    assert report.passed, report.model_dump()
    assert _working_claim(engine, app_id, "sales.metric.performance").claim_type == "derived"


def test_validate_preserves_unsupported_manual_markdown_as_pending(v1_repo: Path) -> None:
    engine = Engine(v1_repo)
    app_id, _ = engine.ingest(
        "Pending Edit",
        "Account Manager",
        "Account Manager responsible for retention, portfolio growth, negotiation, and customer relationships.",
    )
    engine.analyze(app_id)
    markdown, _manifest, _report = engine.draft(app_id)
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


def test_cli_exposes_style_safe_composite_edit(v1_repo: Path) -> None:
    engine = Engine(v1_repo)
    app_id, _ = engine.ingest(
        "Composite CLI",
        "Account Manager",
        "Account Manager responsible for retention, portfolio growth, negotiation, and customer relationships.",
    )
    engine.analyze(app_id)
    engine.draft(app_id)
    claim = _working_claim(engine, app_id, "sales.metric.recurring_customers")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cv_engine.cli",
            "--repo",
            str(v1_repo),
            "edit-claim",
            app_id,
            claim.claim_id,
            "--template",
            "canonical-renderings",
            "--fact-id",
            "sales.metric.recurring_customers",
            "--fact-id",
            "sales.metric.performance",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert _working_claim(engine, app_id, "sales.metric.recurring_customers").claim_type == "composite"


def test_render_revalidates_approved_markdown_before_browser(v1_repo: Path) -> None:
    from cv_engine.workflow import WorkflowError

    engine = Engine(v1_repo)
    app_id, _ = engine.ingest("Acme", "Developer", "Python backend developer API React")
    engine.analyze(app_id)
    engine.draft(app_id)
    approved = engine.approve(app_id)
    markdown = approved["directory"] / "resume.md"
    markdown.write_text(markdown.read_text(encoding="utf-8") + "\nUnsupported claim.\n", encoding="utf-8")
    try:
        engine.render(app_id)
    except WorkflowError as exc:
        assert "approved Markdown" in str(exc)
    else:
        raise AssertionError("modified approved source reached rendering")


def test_cli_fast_mode_completes_definition_of_done(v1_repo: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cv_engine.cli",
            "--repo",
            str(v1_repo),
            "fast",
            "--company",
            "CLI Example",
            "--role",
            "Account Manager",
            "--job-text",
            "Account Manager responsible for retention, portfolio growth, negotiation, and customer relationships.",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ready"] is True
    assert Path(payload["pdf"]).is_file()
