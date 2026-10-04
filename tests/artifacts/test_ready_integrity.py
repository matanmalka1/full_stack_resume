"""Derived Ready and immutable Submission evidence (§16, §18)."""

from __future__ import annotations

import pytest
from helpers import stored_document, stored_submissions
from sqlalchemy import delete, update
from sqlalchemy.exc import ProgrammingError

from cv_engine.application.commands import (
    ClaimAddition,
    ExternalSubmissionCommand,
    RecruitmentCorrectionCommand,
    RecruitmentStatusCommand,
    RenderCommand,
    SubmissionCommand,
    UpdateDocumentCommand,
)
from cv_engine.application.errors import (
    DOCUMENT_NOT_APPROVED,
    DOCUMENT_NOT_READY,
    PreconditionFailed,
    WorkflowError,
)
from cv_engine.domain.document import PreparationState
from cv_engine.infrastructure.document_files import DocumentFiles
from cv_engine.infrastructure.persistence.application_projections import (
    SqlAlchemyApplicationProjectionReader,
)
from cv_engine.infrastructure.persistence.application_store import SqlAlchemyApplicationStore
from cv_engine.infrastructure.persistence.tables import cv_documents, submissions
from cv_engine.util import utc_now


def test_render_and_submission_refuse_unapproved_content_before_copy(
    drafted_application, monkeypatch
):
    setup = drafted_application("Not Ready")
    services, app_id = setup

    def forbidden(*args, **kwargs):
        raise AssertionError("copy must not start before Ready")

    monkeypatch.setattr(DocumentFiles, "copy_for_submission", forbidden)
    with pytest.raises(PreconditionFailed) as error:
        services.rendering.render(
            RenderCommand(application_id=app_id, expected_document_hash=setup.document_hash)
        )
    assert error.value.code == DOCUMENT_NOT_APPROVED
    with pytest.raises(PreconditionFailed) as error:
        services.submission.submit_application(
            SubmissionCommand(
                application_id=app_id,
                expected_document_hash=setup.document_hash,
                submitted_at=utc_now(),
                client="web",
            )
        )
    assert error.value.code == DOCUMENT_NOT_READY
    assert stored_submissions(services, app_id) == []


def test_submission_rechecks_ready_under_lock(ready_application, monkeypatch, database_engine):
    setup = ready_application("Copy Race")
    services, app_id = setup
    copy = DocumentFiles.copy_for_submission

    def move_after_copy(store, *args, **kwargs):
        result = copy(store, *args, **kwargs)
        with database_engine.begin() as connection:
            connection.execute(
                update(cv_documents)
                .where(cv_documents.c.application_id == app_id)
                .values(rendered_basis="0" * 64)
            )
        return result

    monkeypatch.setattr(DocumentFiles, "copy_for_submission", move_after_copy)
    with pytest.raises(PreconditionFailed) as error:
        services.submission.submit_application(
            SubmissionCommand(
                application_id=app_id,
                expected_document_hash=setup.document_hash,
                submitted_at=utc_now(),
                client="web",
            )
        )
    assert error.value.code == DOCUMENT_NOT_READY
    assert stored_submissions(services, app_id) == []
    assert services.queries.application_detail(app_id).application.current_status == "saved"


def test_submission_copies_survive_edits_and_database_triggers_refuse_mutation(
    submitted_application, database_engine
):
    setup = submitted_application("Immutable Copies")
    services, app_id = setup
    (sent,) = stored_submissions(services, app_id)
    document = stored_document(services, app_id)
    assert document.content is not None
    assert sent.pdf_path != document.pdf_path and sent.html_path != document.html_path
    before = {
        path: (services.paths.root / path).read_bytes()
        for path in (sent.html_path, sent.pdf_path)
        if path
    }
    services.draft_editing.update_document(
        UpdateDocumentCommand(
            application_id=app_id,
            expected_document_hash=document.document_hash,
            claim_additions=[
                ClaimAddition(section=document.content.sections[0].name, text="unsupported")
            ],
        )
    )
    assert services.queries.application_detail(app_id).preparation_state is PreparationState.DRAFT_IN_PROGRESS
    with pytest.raises(PreconditionFailed) as error:
        services.rendering.export_recruiter_pdf(app_id)
    assert error.value.code == DOCUMENT_NOT_READY
    assert stored_submissions(services, app_id) == [sent]
    assert all(
        (services.paths.root / path).read_bytes() == payload for path, payload in before.items()
    )
    for statement in (
        update(submissions).values(document_hash=submissions.c.document_hash),
        delete(submissions),
    ):
        with pytest.raises(ProgrammingError, match="immutable record"):
            with database_engine.begin() as connection:
                connection.execute(statement)


def test_generic_status_transition_to_applied_is_always_blocked(
    ready_application, transaction_manager
) -> None:
    """The generic transition rejects applied unconditionally -- even supplying
    a real, currently-valid rendered PDF artifact version id must not work,
    because the generic transition has no way to perform the fresh integrity
    verification that SubmissionService performs. There is no parameter that can
    talk it into treating a caller-supplied id as trustworthy."""
    services, app_id = ready_application("Direct Applied With PDF")
    with pytest.raises(WorkflowError, match="submission-owned"):
        services.recruitment.transition_status(
            RecruitmentStatusCommand(
                application_id=app_id,
                target_status="applied",
                reason="direct bypass attempt",
                client="web",
            )
        )
    with transaction_manager.read() as tx:
        assert (
            SqlAlchemyApplicationStore(transaction_manager).get_application(tx, app_id)[
                "current_status"
            ]
            == "saved"
        )


def test_external_submission_never_fabricates_document_or_files(
    analyzed_application, transaction_manager
) -> None:
    services, app_id = analyzed_application("External Submission")
    first = services.submission.record_external_submission(
        ExternalSubmissionCommand(
            application_id=app_id,
            submitted_at="2026-08-19T10:00:00+00:00",
            metadata={"source": "email confirmation"},
            client="web",
        )
    )
    second = services.submission.record_external_submission(
        ExternalSubmissionCommand(
            application_id=app_id,
            submitted_at="2026-08-19T11:00:00+00:00",
            client="web",
        )
    )
    assert first.current_status == second.current_status == "applied"
    with transaction_manager.read() as tx:
        submissions = SqlAlchemyApplicationProjectionReader(transaction_manager).submissions(
            tx, app_id
        )
    assert len(submissions) == 2
    assert all(row["submission_type"] == "external" for row in submissions)
    assert all(row["content"] is None for row in submissions)
    assert all(row["document_hash"] is None for row in submissions)
    with transaction_manager.read() as tx:
        applied_events = [
            row
            for row in SqlAlchemyApplicationProjectionReader(
                transaction_manager
            ).recruitment_events(tx, app_id)
            if row["to_status"] == "applied"
        ]
    assert len(applied_events) == 1


def test_correction_is_append_only_and_terminal_outcome_survives_closed(
    analyzed_application, transaction_manager
) -> None:
    services, app_id = analyzed_application("Correction History")
    withdrawn = services.recruitment.transition_status(
        RecruitmentStatusCommand(
            application_id=app_id,
            target_status="withdrawn",
            reason="mistaken entry",
            occurred_at="2026-08-19T10:00:00+00:00",
            client="web",
        )
    )
    assert withdrawn.terminal_outcome == "withdrawn"
    with pytest.raises(WorkflowError, match="reason is required"):
        services.recruitment.correct_recruitment_status(
            RecruitmentCorrectionCommand(
                application_id=app_id,
                target_status="interview",
                corrects_event_id=withdrawn.event_id or "",
                reason=" ",
                client="web",
            )
        )
    corrected = services.recruitment.correct_recruitment_status(
        RecruitmentCorrectionCommand(
            application_id=app_id,
            target_status="interview",
            corrects_event_id=withdrawn.event_id or "",
            reason="status was entered on the wrong application",
            occurred_at="2026-08-19T10:05:00+00:00",
            client="web",
        )
    )
    assert corrected.current_status == "interview"
    assert corrected.terminal_outcome is None
    with transaction_manager.read() as tx:
        events = SqlAlchemyApplicationProjectionReader(transaction_manager).recruitment_events(
            tx, app_id
        )
    original = next(row for row in events if row["id"] == withdrawn.event_id)
    correction = next(row for row in events if row["id"] == corrected.event_id)
    assert original["to_status"] == "withdrawn"
    assert correction["corrects_event_id"] == original["id"]
    assert correction["reason"] == "status was entered on the wrong application"

    for target in ("offer", "accepted", "closed"):
        closed = services.recruitment.transition_status(
            RecruitmentStatusCommand(application_id=app_id, target_status=target, client="web")
        )
    assert closed.current_status == "closed"
    assert closed.terminal_outcome == "accepted"
