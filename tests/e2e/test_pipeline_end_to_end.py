"""§14 acceptance: the service pipeline reaches Ready with no AI key.

The two AI steps run without one too: the analysis is seeded as existing, and
`create_draft` answers through the fake transport, so every line of the
application layer between them is production code.
"""

from __future__ import annotations

import os

from foreground import foreground_executor
from helpers import (
    persisted_counts,
    seed_document,
    stored_document,
    stored_submissions,
)
from sqlalchemy import text

from cv_engine.application.commands import (
    ApproveDocumentCommand,
    CheckDocumentCommand,
    DraftCommand,
    RenderCommand,
    SubmissionCommand,
    UpdateDocumentCommand,
)
from cv_engine.domain.document import PreparationState
from cv_engine.util import new_id, utc_now


def test_pipeline_reaches_ready_and_reconciles(
    ai_services, fake_openai, deterministic_renderer, database_engine
):
    assert os.environ.get("OPENAI_API_KEY") is None
    services = ai_services
    ingested, analysis = seed_document(services, "Pipeline Co")
    app_id = ingested.application_id
    assert analysis.created_document
    document = stored_document(services, app_id)
    fake_openai.script_draft()
    queued = services.operation_submissions.submit_draft(
        DraftCommand(application_id=app_id, expected_document_hash=document.document_hash),
        idempotency_key=new_id(),
        draft_service=services.drafts,
    )
    drafted = foreground_executor(services).execute(queued.id)
    assert drafted.status.value == "succeeded", drafted.safe_failure_detail
    document = stored_document(services, app_id)
    assert document.content is not None
    section = next(
        s
        for s in document.content.sections
        if len(s.claims) > 1 and all(c.style not in {"heading", "date"} for c in s.claims)
    )
    edited = services.draft_editing.update_document(
        UpdateDocumentCommand(
            application_id=app_id,
            expected_document_hash=document.document_hash,
            claim_orders={section.name: [c.claim_id for c in reversed(section.claims)]},
        )
    )
    token = edited.document_hash
    checked = services.draft_validation.check_document(
        CheckDocumentCommand(application_id=app_id, expected_document_hash=token)
    )
    assert checked.passed, checked.report
    approved = services.draft_approval.approve_document(
        ApproveDocumentCommand(application_id=app_id, expected_document_hash=token, client="web")
    )
    assert approved.passed, approved.report
    rendered = services.rendering.render(
        RenderCommand(application_id=app_id, expected_document_hash=token)
    )
    assert rendered.validation.passed, rendered.validation
    assert services.queries.application_detail(app_id).preparation_state is PreparationState.READY
    services.submission.submit_application(
        SubmissionCommand(
            application_id=app_id,
            expected_document_hash=token,
            submitted_at=utc_now(),
            client="web",
        )
    )
    (sent,) = stored_submissions(services, app_id)
    assert sent.content == stored_document(services, app_id).content
    assert sent.job_snapshot_id == ingested.job_snapshot_id
    report = services.maintenance.reconcile()
    assert report.passed, report.problems
    counts = persisted_counts(database_engine)
    submission_files = sum(path is not None for path in (sent.html_path, sent.pdf_path))
    assert report.payloads_checked == counts["job_snapshots"] + submission_files
    assert report.ai_calls_checked == counts["ai_calls"]
    assert services.maintenance.inspect_orphans().candidates == []
    assert services.queries.application_detail(app_id).application.current_status == "applied"

    # A logged call's response is checked against the hash it was logged under. The
    # log is append-only, so a tamper needs its trigger switched off - what a
    # hand-edited database would take - and reconciliation repairs nothing.
    assert report.ai_calls_checked > 0
    with database_engine.begin() as connection:
        connection.execute(text("ALTER TABLE ai_calls DISABLE TRIGGER no_update_ai_calls"))
        tampered = connection.execute(
            text(
                "UPDATE ai_calls SET sanitized_response = sanitized_response || "
                "'{\"edited\": true}'::jsonb WHERE id = "
                "(SELECT id FROM ai_calls WHERE sanitized_response IS NOT NULL LIMIT 1) "
                "RETURNING id"
            )
        ).scalar_one()
        connection.execute(text("ALTER TABLE ai_calls ENABLE TRIGGER no_update_ai_calls"))
    tampered_report = services.maintenance.reconcile()
    assert not tampered_report.passed
    assert f"AI call response hash mismatch: {tampered}" in tampered_report.problems


def test_reconcile_reports_tampered_submission_without_repair(submitted_application):
    setup = submitted_application("Tamper Co")
    services, app_id = setup
    (sent,) = stored_submissions(services, app_id)
    assert sent.pdf_path is not None
    path = services.paths.root / sent.pdf_path
    tampered = b"%PDF-1.4\n% not the submitted bytes\n"
    path.write_bytes(tampered)
    report = services.maintenance.reconcile()
    assert not report.passed
    assert any("hash mismatch" in problem for problem in report.problems)
    assert path.read_bytes() == tampered
    assert stored_submissions(services, app_id) == [sent]


def test_reconcile_verifies_job_snapshot_payloads(services):
    """§19b requires JobSnapshot verification, including without any Submission."""
    ingested, _ = seed_document(services, "Snapshot Integrity")
    reference = services.payloads.snapshot_path(ingested.application_id, ingested.job_snapshot_id)
    reference.write_bytes(b"posting changed after capture")
    report = services.maintenance.reconcile()
    assert not report.passed
    assert report.problems
    assert reference.read_bytes() == b"posting changed after capture"
