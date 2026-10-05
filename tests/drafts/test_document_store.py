"""The document store's one check: `expected_document_hash` against the row it locked.

state-and-use-cases.md §3 and the port contract in `application/ports/documents.py`.
Every hash-guarded write refuses a moved hash before writing anything, except
`record_render_error`, whose mismatch is an expected outcome reported by its return
value (§16). Discovered from the port rather than listed, so a new guarded write is
covered the moment it exists.
"""

from __future__ import annotations

import inspect

import pytest
from helpers import seed_document, seed_draft, services_transactions, stored_document

from cv_engine.application.errors import DOCUMENT_CHANGED, StateConflict
from cv_engine.application.ports.documents import DocumentBody, DocumentStore, RenderedFiles
from cv_engine.domain.contracts.validation import ValidationReport
from cv_engine.domain.document import PreparationState
from cv_engine.runtime.composition import Services
from cv_engine.util import utc_now

MOVED = "0" * 64


def _guarded_writes() -> list[str]:
    return sorted(
        name
        for name, member in inspect.getmembers(DocumentStore, inspect.isfunction)
        if "expected_document_hash" in inspect.signature(member).parameters
    )


def test_every_hash_guarded_write_refuses_a_moved_document_and_writes_nothing(
    services: Services,
) -> None:
    ingested, analysis = seed_document(services, "Store Co")
    application_id = ingested.application_id
    document = stored_document(services, application_id)
    body = DocumentBody(analysis_id=document.analysis_id, content=None)
    now = utc_now()
    arguments = {
        "update_body": (body,),
        "repin": (body, document.built_with),
        "stamp_check": (ValidationReport.from_findings({"content": True}, []), MOVED),
        "stamp_approval": (MOVED,),
        "activate_render": (MOVED, RenderedFiles(html="h", pdf="p")),
        "record_render_error": ({"code": "render_failed"},),
    }
    timestamps = {"stamp_approval": "approved_at"}
    assert _guarded_writes() == sorted(arguments), "cover every guarded write"

    for name, extra in arguments.items():
        write = getattr(services.drafts.documents, name)
        stamp = {timestamps.get(name, "updated_at"): now}
        if name == "record_render_error":
            with services_transactions(services).write() as tx:
                assert write(tx, application_id, MOVED, *extra, **stamp) is False
        else:
            with (
                pytest.raises(StateConflict) as refused,
                services_transactions(services).write() as tx,
            ):
                write(tx, application_id, MOVED, *extra, **stamp)
            assert refused.value.code == DOCUMENT_CHANGED, name
        assert stored_document(services, application_id) == document, name

    with pytest.raises(StateConflict), services_transactions(services).write() as tx:
        services.drafts.documents.create_document(
            tx, application_id, body, document.built_with, created_at=now
        )
    assert stored_document(services, application_id) == document
    assert analysis.document_id == document.id


def test_first_analysis_and_document_commit_together_or_not_at_all(
    services, monkeypatch, database_engine
):
    """§13 atomicity moved from the obsolete analysis/selection-plan HTTP scenario."""
    from helpers import persisted_counts, seed_existing_analysis

    from cv_engine.application.commands import IngestCommand
    from cv_engine.infrastructure.persistence.documents import SqlAlchemyDocumentStore

    ingested = services.applications.ingest(
        IngestCommand(
            company="Atomic Analysis Co",
            target_role="Account Manager",
            job_text="Account management and portfolio growth",
            client="web",
        )
    )
    before = persisted_counts(database_engine)
    create_document = SqlAlchemyDocumentStore.create_document

    def fail_after_document(*args, **kwargs):
        create_document(*args, **kwargs)
        raise RuntimeError("document activation interrupted")

    with monkeypatch.context() as patch:
        patch.setattr(SqlAlchemyDocumentStore, "create_document", fail_after_document)
        with pytest.raises(RuntimeError, match="document activation interrupted"):
            seed_existing_analysis(services, ingested)
    assert persisted_counts(database_engine) == before
    with services_transactions(services).read() as tx:
        assert services.drafts.documents.document(tx, ingested.application_id) is None

    result = seed_existing_analysis(services, ingested)
    after = persisted_counts(database_engine)
    assert after["job_analyses"] == before["job_analyses"] + 1
    assert after["cv_documents"] == before["cv_documents"] + 1
    document = stored_document(services, ingested.application_id)
    assert result.created_document and document.id == result.document_id
    assert document.analysis_id == result.analysis_id
    assert document.application_id == ingested.application_id
    assert document.content is None
    assert services.queries.application_detail(ingested.application_id).preparation_state is (
        PreparationState.READY_TO_DRAFT
    )
    seed_draft(services, ingested.application_id)
    assert stored_document(services, ingested.application_id).content is not None


def test_application_commands_refuse_stale_hash_before_work(ready_application):
    """§14–§18: the client token is checked even when the current document is Ready."""
    from cv_engine.application.commands import (
        ApplyAnalysisDecisionsCommand,
        ApproveDocumentCommand,
        BuildFromAnalysisCommand,
        CheckDocumentCommand,
        DraftCommand,
        RegenerateClaimCommand,
        RegenerateSectionCommand,
        RenderCommand,
        SubmissionCommand,
        UpdateDocumentCommand,
    )

    setup = ready_application("Stale Commands")
    services, application_id = setup
    document = stored_document(services, application_id)
    assert document.content is not None
    section = next(s for s in document.content.sections if s.claims)
    claim = section.claims[0]
    commands = [
        lambda: services.drafts.prepare(
            DraftCommand(application_id=application_id, expected_document_hash=MOVED),
            operation_id="stale-draft",
        ),
        lambda: services.draft_editing.update_document(
            UpdateDocumentCommand(
                application_id=application_id,
                expected_document_hash=MOVED,
                claim_removals=[claim.claim_id],
            )
        ),
        lambda: services.draft_editing.build_from_analysis(
            BuildFromAnalysisCommand(
                application_id=application_id,
                expected_document_hash=MOVED,
                analysis_id=document.analysis_id,
            )
        ),
        lambda: services.analysis.apply_analysis_decisions(
            ApplyAnalysisDecisionsCommand(
                application_id=application_id,
                expected_document_hash=MOVED,
                job_analysis_id=document.analysis_id,
                expected_analysis_id=document.analysis_id,
            )
        ),
        lambda: services.draft_review.check_document(
            CheckDocumentCommand(application_id=application_id, expected_document_hash=MOVED)
        ),
        lambda: services.draft_review.approve_document(
            ApproveDocumentCommand(
                application_id=application_id, expected_document_hash=MOVED, client="web"
            )
        ),
        lambda: services.drafts.prepare_section_regeneration(
            RegenerateSectionCommand(
                application_id=application_id, expected_document_hash=MOVED, section=section.name
            ),
            operation_id="stale-section",
        ),
        lambda: services.drafts.prepare_claim_regeneration(
            RegenerateClaimCommand(
                application_id=application_id, expected_document_hash=MOVED, claim_id=claim.claim_id
            ),
            operation_id="stale-claim",
        ),
        lambda: services.rendering.render(
            RenderCommand(application_id=application_id, expected_document_hash=MOVED)
        ),
        lambda: services.submission.submit_application(
            SubmissionCommand(
                application_id=application_id,
                expected_document_hash=MOVED,
                submitted_at=utc_now(),
                client="web",
            )
        ),
    ]
    for command in commands:
        with pytest.raises(StateConflict) as refused:
            command()
        assert refused.value.code == DOCUMENT_CHANGED
        assert stored_document(services, application_id) == document
