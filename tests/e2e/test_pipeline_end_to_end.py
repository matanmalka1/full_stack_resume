"""§14 acceptance: the service pipeline reaches Ready with no AI key."""

from __future__ import annotations

import os

from helpers import persisted_counts, seed_document, stored_document, stored_submissions

from cv_engine.application.commands import (
    ApproveDocumentCommand,
    CheckDocumentCommand,
    DraftCommand,
    RenderCommand,
    SubmissionCommand,
    UpdateDocumentCommand,
)
from cv_engine.domain.document import DocumentState
from cv_engine.util import utc_now


def test_deterministic_pipeline_reaches_ready_and_reconciles(
    services, deterministic_renderer, database_engine
):
    assert os.environ.get("OPENAI_API_KEY") is None
    ingested, analysis = seed_document(services, "Pipeline Co")
    app_id = ingested.application_id
    assert analysis.created_document
    document = stored_document(services, app_id)
    services.drafts.draft(
        DraftCommand(application_id=app_id, expected_document_hash=document.document_hash)
    )
    document = stored_document(services, app_id)
    assert document.content is not None
    section = next(
        s
        for s in document.content.sections
        if len(s.claims) > 1 and all(c.style not in {"heading", "date"} for c in s.claims)
    )
    edited = services.drafts.update_document(
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
    assert services.queries.application_detail(app_id).document_state is DocumentState.READY
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
    assert report.artifact_versions_checked == (
        counts["job_snapshots"] + counts["artifact_versions"] + submission_files
    )
    assert services.maintenance.inspect_orphans().candidates == []
    assert services.queries.application_detail(app_id).application.current_status == "applied"


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
