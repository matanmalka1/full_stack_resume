from __future__ import annotations

import json
import re
from types import SimpleNamespace
from pathlib import Path

import pytest

import cv_engine.application.services.drafts as draft_service_module
from cv_engine.application.commands import AnalyzeCommand, DraftCommand, IngestCommand
from cv_engine.application.errors import WorkflowError
from cv_engine.domain.draft_markdown import parse_draft, serialize_markdown
from cv_engine.domain.models import ValidationIssue, ValidationReport
from cv_engine.infrastructure.artifacts import FilesystemArtifactStore
from cv_engine.infrastructure.persistence import connect
from cv_engine.runtime.workspace import Workspace
from helpers import ACCOUNT_MANAGER_JOB, working_claim as _working_claim


@pytest.mark.browser
def test_default_flow_stops_for_review_then_reaches_ready(services) -> None:
    ingested = services.applications.ingest(IngestCommand(
        company="Acme",
        target_role="Account Manager",
        job_text=ACCOUNT_MANAGER_JOB,
    ))
    analysed = services.analysis.analyze(AnalyzeCommand(
        application_id=ingested.application_id,
        job_snapshot_id=ingested.job_snapshot_id,
    ))
    drafted = services.drafts.draft(DraftCommand(
        application_id=ingested.application_id,
        job_analysis_id=analysed.analysis_id,
    ))
    app_id = ingested.application_id
    paths = services.artifacts.working_paths(app_id)
    assert drafted.validation.passed
    markdown, manifest = paths.markdown, paths.manifest
    assert markdown.is_file() and manifest.is_file()
    assert services.repository.get_application(app_id)["current_status"] == "preparing"
    assert services.repository.artifact_versions(app_id) == []
    approved = services.drafts.approve(app_id)
    assert approved.version == 1
    rendered = services.rendering.render(app_id)
    pdf_record = services.repository.latest_artifact_version(app_id, "resume_pdf")
    pdf = services.artifacts.resolve(pdf_record["path"])
    assert rendered.validation.passed, rendered.validation.model_dump()
    assert pdf.name == "Matan Malka - Account Manager - CV.pdf"
    assert services.repository.get_application(app_id)["current_status"] == "ready"
    assert services.rendering.ready_report(app_id).passed
    decision = services.repository.latest_decision(app_id)
    assert decision["job_snapshot_id"] == ingested.job_snapshot_id
    submission_result = services.tracking.submit(app_id, "submitted to employer")
    assert submission_result.current_status == "applied"
    with connect(services.repository.path) as connection:
        submission = connection.execute("SELECT artifact_version_id FROM submissions WHERE application_id=?", (app_id,)).fetchone()
    assert submission is not None
    assert submission["artifact_version_id"] == submission_result.pdf_artifact_version_id


def test_csv_export_declares_its_schema_version(services, tmp_path: Path) -> None:
    import json as _json

    from cv_engine.cli import EXPORT_SCHEMA_VERSION, export_csv

    ingested = services.applications.ingest(IngestCommand(
        company="Acme", target_role="Developer", job_text="Python developer role"
    ))
    app_id = ingested.application_id
    output = export_csv(services.queries.list_applications(), tmp_path / "applications.csv")
    text = output.read_text(encoding="utf-8")
    assert "current_status" in text
    assert app_id in text

    metadata = _json.loads(
        output.with_suffix(output.suffix + ".meta.json").read_text(encoding="utf-8")
    )
    assert metadata["export_schema_version"] == EXPORT_SCHEMA_VERSION
    assert metadata["row_count"] == 1
    assert metadata["columns"][0] == "id"
    assert "current_status" in metadata["columns"]


def test_filesystem_working_draft_unconditionally_overwrites_the_projection(
    workspace: Workspace,
    draft_factory,
) -> None:
    application_id = "overwrite-projection"
    first = draft_factory(
        ACCOUNT_MANAGER_JOB,
        application_id=application_id,
    ).draft
    replacement = draft_factory(
        "Python backend developer API React",
        application_id=application_id,
    ).draft
    store = FilesystemArtifactStore(workspace)

    first_stored = store.write_working_draft(first)
    first_markdown = first_stored.paths.markdown.read_text(encoding="utf-8")
    replacement_stored = store.write_working_draft(replacement)

    assert replacement_stored.paths == first_stored.paths
    assert replacement_stored.paths.markdown.read_text(encoding="utf-8") == (
        serialize_markdown(replacement)
    )
    assert parse_draft(
        replacement_stored.paths.manifest.read_text(encoding="utf-8")
    ).profile == replacement.profile
    assert first_markdown != replacement_stored.markdown


def test_validate_extracts_safe_manual_markdown_wording(drafted_application) -> None:
    setup = drafted_application("Manual Edit")
    services, app_id = setup
    markdown = setup.markdown
    claim = _working_claim(services, app_id, "sales.metric.performance")
    markdown.write_text(
        markdown.read_text(encoding="utf-8").replace(claim.text, claim.text.rstrip("."), 1),
        encoding="utf-8",
    )

    report = services.drafts.validate_working(app_id)

    assert report.passed, report.model_dump()
    assert _working_claim(services, app_id, "sales.metric.performance").claim_type == "derived"


def test_validate_preserves_unsupported_manual_markdown_as_pending(drafted_application) -> None:
    setup = drafted_application("Pending Edit")
    services, app_id = setup
    markdown = setup.markdown
    claim = _working_claim(services, app_id, "sales.metric.performance")
    markdown.write_text(
        markdown.read_text(encoding="utf-8").replace(
            claim.text,
            "Delivered 30% improvement in direct SaaS Sales.",
            1,
        ),
        encoding="utf-8",
    )

    report = services.drafts.validate_working(app_id)

    assert not report.passed
    assert any(issue.code == "pending-claim" for issue in report.issues)
    assert _working_claim(services, app_id, "sales.metric.performance").claim_type == "pending"


def test_cli_exposes_style_safe_composite_edit(drafted_application, cli_runner) -> None:
    services, app_id = drafted_application("Composite CLI")
    claim = _working_claim(services, app_id, "sales.metric.recurring_customers")

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
    assert _working_claim(services, app_id, "sales.metric.recurring_customers").claim_type == "composite"


def test_render_revalidates_approved_markdown_before_browser(approved_application) -> None:
    setup = approved_application("Acme", "Developer", "Python backend developer API React")
    services, app_id = setup
    approved = setup.approved
    markdown = services.artifacts.approved_version_dir(app_id, approved.version) / "resume.md"
    markdown.write_text(markdown.read_text(encoding="utf-8") + "\nUnsupported claim.\n", encoding="utf-8")
    try:
        services.rendering.render(app_id)
    except WorkflowError as exc:
        assert "approved Markdown" in str(exc)
    else:
        raise AssertionError("modified approved source reached rendering")


@pytest.mark.parametrize(
    "failed_phase, expected_calls, message",
    [
        (
            "pre-render",
            ["ingest", "analyze", "draft"],
            "fast mode blocked by pre-render validation",
        ),
        (
            "post-render",
            ["ingest", "analyze", "draft", "approve", "render"],
            "fast mode blocked by post-render validation",
        ),
    ],
)
def test_fast_orchestration_preserves_call_order_and_gate_messages(
    failed_phase: str, expected_calls: list[str], message: str
) -> None:
    from cv_engine.cli import _fast

    calls: list[str] = []

    def report(phase: str) -> ValidationReport:
        passed = failed_phase != phase
        issues = [] if passed else [
            ValidationIssue(group="content", code=f"injected-{phase}-failure", message="x")
        ]
        return ValidationReport.from_findings(groups={"content": passed}, issues=issues)

    fake_services = SimpleNamespace(
        applications=SimpleNamespace(ingest=lambda _command: (
            calls.append("ingest") or SimpleNamespace(
                application_id="application-1", job_snapshot_id="snapshot-1"
            )
        )),
        analysis=SimpleNamespace(analyze=lambda _command: (
            calls.append("analyze") or SimpleNamespace(analysis_id="analysis-1")
        )),
        drafts=SimpleNamespace(
            draft=lambda _command: (
                calls.append("draft") or SimpleNamespace(validation=report("pre-render"))
            ),
            approve=lambda _application_id: (
                calls.append("approve") or SimpleNamespace(
                    version=1, decision_record_id="decision-1"
                )
            ),
        ),
        rendering=SimpleNamespace(render=lambda _application_id: (
            calls.append("render") or SimpleNamespace(validation=report("post-render"))
        )),
    )

    with pytest.raises(WorkflowError, match=re.escape(message)):
        _fast(fake_services, "Co", "Role", ACCOUNT_MANAGER_JOB)

    assert calls == expected_calls


def test_cli_fast_mode_refuses_pre_render_validation_failure(
    v1_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from cv_engine.cli import main

    real_validate = draft_service_module.validate_draft

    def fail_validation(*args, **kwargs) -> ValidationReport:
        report = real_validate(*args, **kwargs)
        return ValidationReport.from_findings(
            groups={**report.groups, "content": False},
            issues=[
                *report.issues,
                ValidationIssue(
                    group="content",
                    code="injected-cli-fast-failure",
                    message="controlled CLI fast validation failure",
                ),
            ],
            evidence=report.evidence,
        )

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(draft_service_module, "validate_draft", fail_validation)

    result = main([
        "--workspace",
        str(v1_repo),
        "fast",
        "--company",
        "CLI Refusal",
        "--role",
        "Account Manager",
        "--job-text",
        ACCOUNT_MANAGER_JOB,
    ])
    captured = capsys.readouterr()

    assert result == 2
    assert captured.out == ""
    assert "ERROR: fast mode blocked by pre-render validation" in captured.err


@pytest.mark.browser
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
