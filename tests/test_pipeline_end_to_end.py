"""The deterministic pipeline, driven through the application layer.

`ingest -> analyze -> draft -> validate -> approve -> render -> ready ->
reconcile`, with no AI key, no HTTP, and no CLI. This is the check CLAUDE.md
names as the one that has caught real defects here - approval silently
destroying unimported manual edits - and it belongs to the engine rather than
to any one client. Driving it through `application/` is what makes it prove
the engine works, instead of proving that a particular client knows how to
call it.

Every step names the exact source record it consumes, the way the use-cases
require: no step resolves "the latest" for itself.
"""

from __future__ import annotations

import os

import pytest
from helpers import ACCOUNT_MANAGER_JOB

import cv_engine.application.services.drafts.generation as draft_generation_module
import cv_engine.application.services.drafts.validation as draft_validation_module
from cv_engine.application.commands import (
    AnalyzeCommand,
    ApproveDraftCommand,
    DraftCommand,
    IngestCommand,
    ValidateDraftCommand,
)
from cv_engine.application.errors import ValidationBlocked
from cv_engine.application.maintenance import (
    build_application_export,
    reconcile_artifacts,
)
from cv_engine.domain.models import ValidationIssue, ValidationReport
from cv_engine.runtime.composition import Services


@pytest.fixture
def no_ai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The deterministic workflow reaches Ready with nothing configured.

    Asserted rather than assumed: a key leaking in from the developer's own
    environment would let this test pass while the offline path was broken.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_deterministic_pipeline_reaches_ready_and_reconciles(
    services: Services,
    deterministic_renderer: None,
    no_ai_key: None,
) -> None:
    assert os.environ.get("OPENAI_API_KEY") is None

    # ingest
    ingested = services.applications.ingest(
        IngestCommand(
            company="Pipeline Co",
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
            acknowledged_duplicates=True,
        )
    )
    application_id = ingested.application_id
    assert ingested.job_snapshot_id

    # analyze, against that exact snapshot
    analysed = services.analysis.analyze(
        AnalyzeCommand(
            application_id=application_id,
            job_snapshot_id=ingested.job_snapshot_id,
        )
    )

    # draft, from that exact analysis and plan
    drafted = services.drafts.draft(
        DraftCommand(
            application_id=application_id,
            job_analysis_id=analysed.analysis_id,
            selection_plan_id=analysed.selection_plan_id,
        )
    )

    # validate the exact draft version in front of us
    working = services.repository.active_working_draft(application_id)
    assert working.id == drafted.working_draft_id
    validated = services.drafts.validate_draft(
        ValidateDraftCommand(
            working_draft_id=working.id,
            expected_edit_version=working.edit_version,
        )
    )
    assert validated.passed, validated.report.model_dump(mode="json")

    # approve exactly what that run passed
    approved = services.drafts.approve_draft(
        ApproveDraftCommand(
            working_draft_id=validated.working_draft_id,
            expected_edit_version=validated.edit_version,
            validation_run_id=validated.validation_run_id,
        )
    )
    assert approved.revision_id
    assert approved.decision_record_id

    # render, then read Ready back from stored evidence
    rendered = services.rendering.render(application_id)
    assert rendered.validation.passed, rendered.validation.model_dump(mode="json")
    assert services.rendering.ready_report(application_id).passed
    assert services.rendering.ready_qualification(application_id).ready_qualified

    # reconcile: every registered artifact verifies through the payload store
    report = reconcile_artifacts(services.payloads, services.repository)
    assert report["passed"], report["problems"]
    assert report["artifact_versions_checked"] > 0
    assert services.knowledge_lifecycle.reconcile_facts().passed

    # the export projection sees the application the pipeline just produced
    export = build_application_export(services.queries.list_applications())
    assert export.metadata["row_count"] == 1
    assert export.rows[0]["id"] == application_id
    assert export.rows[0]["current_status"] == "saved"


def test_reconcile_reports_a_tampered_artifact(
    services: Services,
    deterministic_renderer: None,
    no_ai_key: None,
    ready_application,
) -> None:
    """Reconcile fails when stored evidence stops matching its recorded hash.

    Verification goes through the payload store rather than a resolved local
    path, so this asserts the check reports a hash mismatch rather than that a
    particular file on disk changed.
    """
    setup = ready_application("Tamper Co")
    assert reconcile_artifacts(services.payloads, services.repository)["passed"]

    pdf_record = services.repository.latest_artifact_version(setup.application_id, "resume_pdf")
    services.artifacts.resolve(pdf_record["path"]).write_bytes(
        b"%PDF-1.4\n% not the approved bytes\n"
    )

    report = reconcile_artifacts(services.payloads, services.repository)
    assert not report["passed"]
    assert any("hash mismatch" in problem for problem in report["problems"]), report["problems"]


def test_failed_pre_render_validation_blocks_approval(
    services: Services,
    no_ai_key: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A draft that fails pre-render validation cannot be approved.

    The guarantee belongs to the pipeline, not to any client: validation is
    mandatory, and a failing run must leave the application with no approved
    revision rather than one nothing vouched for.
    """
    real_validate = draft_generation_module.run_draft_validation

    def fail_validation(*args, **kwargs) -> ValidationReport:
        report = real_validate(*args, **kwargs)
        return ValidationReport.from_findings(
            groups={**report.groups, "content": False},
            issues=[
                *report.issues,
                ValidationIssue(
                    group="content",
                    code="injected-validation-failure",
                    message="controlled pre-render validation failure",
                ),
            ],
            evidence=report.evidence,
        )

    # Each draft module imports the domain validator under its own name, so a
    # patch reaches only the module it names. `generation` records the draft
    # Operation's own pre-render run; `validation` is the §15 command this test
    # calls. Both are patched so the assertion does not depend on which one the
    # pipeline happens to route through.
    monkeypatch.setattr(draft_generation_module, "run_draft_validation", fail_validation)
    monkeypatch.setattr(draft_validation_module, "run_draft_validation", fail_validation)

    ingested = services.applications.ingest(
        IngestCommand(
            company="Blocked Co",
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
            acknowledged_duplicates=True,
        )
    )
    analysed = services.analysis.analyze(
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_snapshot_id=ingested.job_snapshot_id,
        )
    )
    services.drafts.draft(
        DraftCommand(
            application_id=ingested.application_id,
            job_analysis_id=analysed.analysis_id,
            selection_plan_id=analysed.selection_plan_id,
        )
    )

    working = services.repository.active_working_draft(ingested.application_id)
    validated = services.drafts.validate_draft(
        ValidateDraftCommand(
            working_draft_id=working.id,
            expected_edit_version=working.edit_version,
        )
    )

    assert not validated.passed
    with pytest.raises(ValidationBlocked):
        services.drafts.approve_draft(
            ApproveDraftCommand(
                working_draft_id=validated.working_draft_id,
                expected_edit_version=validated.edit_version,
                validation_run_id=validated.validation_run_id,
            )
        )
    assert services.repository.approved_revisions(ingested.application_id) == []
