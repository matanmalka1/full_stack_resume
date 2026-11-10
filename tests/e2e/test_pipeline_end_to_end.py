"""§14 acceptance: the service pipeline reaches Ready with no AI key.

The two AI steps run without one too: the analysis is seeded as existing, and
`create_draft` answers through the fake transport, so every line of the
application layer between them is production code.
"""

from __future__ import annotations

import os

from foreground import foreground_executor
from helpers import (
    actor_of,
    persisted_counts,
    seed_document,
    stored_document,
)
from sqlalchemy import text

from cv_engine.application.commands import (
    ApproveDocumentCommand,
    CheckDocumentCommand,
    DraftCommand,
    RenderCommand,
    UpdateDocumentCommand,
)
from cv_engine.domain.document import PreparationState
from cv_engine.util import new_id


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
        actor_of(services),
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
        actor_of(services),
        UpdateDocumentCommand(
            application_id=app_id,
            expected_document_hash=document.document_hash,
            claim_orders={section.name: [c.claim_id for c in reversed(section.claims)]},
        ),
    )
    token = edited.document_hash
    checked = services.draft_review.check_document(
        actor_of(services),
        CheckDocumentCommand(application_id=app_id, expected_document_hash=token),
    )
    assert checked.passed, checked.report
    approved = services.draft_review.approve_document(
        actor_of(services),
        ApproveDocumentCommand(application_id=app_id, expected_document_hash=token, client="web"),
    )
    assert approved.passed, approved.report
    rendered = services.rendering.render(
        actor_of(services), RenderCommand(application_id=app_id, expected_document_hash=token)
    )
    assert rendered.validation.passed, rendered.validation
    assert (
        services.queries.application_detail(actor_of(services), app_id).preparation_state
        is PreparationState.READY
    )
    report = services.maintenance.reconcile()
    assert report.passed, report.problems
    counts = persisted_counts(database_engine)
    assert report.ai_calls_checked == counts["ai_calls"]

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
