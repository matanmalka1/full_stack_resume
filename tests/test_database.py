from __future__ import annotations

import pytest
from conftest import alembic_head
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, ProgrammingError

from cv_engine.application.commands import IngestCommand, NextActionCommand
from cv_engine.domain.models import ApplicationStatus, AuditRecord
from cv_engine.infrastructure.persistence import current_database_revision
from cv_engine.infrastructure.persistence.tables import (
    applications,
    job_snapshots,
    recruitment_events,
)
from cv_engine.util import normalized_text, sha256_text


def _create(repo, *, company: str, target_role: str, text: str):
    digest = sha256_text(text)
    return repo.create_application(
        company=company,
        target_role=target_role,
        payload_path=f"artifacts/snapshots/{company}/snapshot.txt",
        source_hash=digest,
        normalized_hash=sha256_text(normalized_text(text)),
        client="web",
    )


def test_recruitment_event_and_transition_contract(application_repo) -> None:
    """Named for the table it reads.

    It was `test_status_history_...` until recruitment_events replaced that
    table; the body moved and the name did not, which is how the dead table kept
    looking referenced.
    """
    repo = application_repo
    app_id, _ = _create(repo, company="Acme", target_role="Developer", text="Python developer role")
    assert not hasattr(repo, "transition_status")
    with pytest.raises(ValueError):
        ApplicationStatus("preparing")
    with pytest.raises(ValueError):
        ApplicationStatus("ready")
    with repo.read_connection() as connection:
        history = connection.execute(
            select(
                recruitment_events.c.from_status,
                recruitment_events.c.to_status,
                recruitment_events.c.actor_type,
                recruitment_events.c.client,
            )
            .where(recruitment_events.c.application_id == app_id)
            .order_by(recruitment_events.c.occurred_at, recruitment_events.c.seq)
        ).all()
    with pytest.raises(IntegrityError, match="ck_applications_current_status"):
        with repo.transaction() as connection:
            connection.execute(
                update(applications)
                .where(applications.c.id == app_id)
                .values(current_status="ready")
            )
    assert history == [(None, "saved", "user", "web")]


def test_removed_cli_client_is_refused_at_the_command_and_database_boundaries(
    application_repo,
) -> None:
    with pytest.raises(ValidationError):
        IngestCommand(
            company="Removed Client",
            target_role="Developer",
            job_text="Python role",
            client="cli",  # type: ignore[arg-type]
        )
    with pytest.raises(ValidationError):
        AuditRecord(
            id="removed-client-audit",
            application_id="application",
            action="test",
            entity_type="application",
            entity_id="application",
            actor_type="user",
            client="cli",  # type: ignore[arg-type]
            occurred_at="2026-08-30T12:00:00+00:00",
        )

    app_id, _ = _create(
        application_repo,
        company="Database Client Guard",
        target_role="Developer",
        text="Python role",
    )
    with pytest.raises(IntegrityError, match="ck_recruitment_events_client"):
        application_repo.insert_next_action_event(
            application_id=app_id,
            next_action="Follow up",
            next_action_date="2026-09-01",
            actor_type="user",
            client="cli",
            occurred_at="2026-08-30T12:00:00+00:00",
        )

    assert application_repo.get_application(app_id)["next_action"] is None


def test_immutable_job_snapshot_trigger(application_repo) -> None:
    repo = application_repo
    _, snapshot_id = _create(
        repo, company="Acme", target_role="Developer", text="Original exact text"
    )
    with pytest.raises(ProgrammingError, match="immutable record"):
        with repo.transaction() as connection:
            connection.execute(
                update(job_snapshots)
                .where(job_snapshots.c.id == snapshot_id)
                .values(source_hash="changed")
            )


def test_next_action_is_not_a_status(application_repo) -> None:
    repo = application_repo
    app_id, _ = _create(repo, company="Acme", target_role="Sales", text="Sales role")
    event_id = repo.insert_next_action_event(
        application_id=app_id,
        next_action="Follow up",
        next_action_date="2026-08-20",
        actor_type="user",
        client="web",
        occurred_at="2026-08-19T10:00:00+00:00",
    )
    row = repo.get_application(app_id)
    assert row["current_status"] == "saved"
    assert row["next_action"] == "Follow up"
    assert repo.recruitment_event(event_id)["event_type"] == "next_action"


def test_database_is_at_registered_head_schema(application_repo) -> None:
    assert current_database_revision(application_repo.engine) == alembic_head()


def test_ready_is_not_persisted_and_submission_storage_commits_atomically(
    application_repo,
) -> None:
    repo = application_repo
    app_id, snapshot_id = _create(
        repo,
        company="Move Guard Success",
        target_role="Developer",
        text="Another Python role",
    )
    pdf_id = repo.register_artifact_version(
        app_id,
        "resume_pdf",
        "resume",
        "artifacts/success/v001/resume.pdf",
        "c" * 64,
        "rendered",
        job_snapshot_id=snapshot_id,
    )
    assert not hasattr(repo, "set_ready")
    assert not hasattr(repo, "_set_ready")
    assert not hasattr(repo, "record_submission")
    assert not hasattr(repo, "_record_submission")
    with repo.unit_of_work() as uow:
        transaction = repo.bind(uow)
        transaction.insert_submission(
            "submission-1",
            app_id,
            "external",
            None,
            pdf_id,
            "2026-08-18T10:00:00+00:00",
            {"reason": "application service verified exact Ready proof"},
        )
        transaction.insert_recruitment_event(
            application_id=app_id,
            expected_current_status="saved",
            target_status="applied",
            event_type="status_transition",
            reason="submitted",
            actor_type="user",
            client="web",
            occurred_at="2026-08-18T10:00:00+00:00",
            terminal_outcome=None,
        )
        uow.commit()
    assert repo.get_application(app_id)["current_status"] == "applied"

    second_id = repo.register_artifact_version(
        app_id,
        "resume_pdf",
        "resume",
        "artifacts/success/v002/resume.pdf",
        "b" * 64,
        "rendered",
        job_snapshot_id=snapshot_id,
    )
    versions = repo.artifact_versions(app_id)
    assert [(row["id"], row["version_number"]) for row in versions] == [
        (pdf_id, 1),
        (second_id, 2),
    ]
    assert all(row["revision_id"] is None for row in versions)
    inventory = repo.artifact_inventory()
    assert len(inventory) == 2
    assert {(row["path"], row["content_hash"]) for row in versions}.issubset(
        {(row["path"], row["content_hash"]) for row in inventory}
    )
    assert repo.integrity_check() == []

    with pytest.raises(IntegrityError):
        repo.insert_submission(
            "fake-internal",
            app_id,
            "internal",
            None,
            pdf_id,
            "2026-08-18T11:00:00+00:00",
            {},
        )

    # One artifact, one submission. The table is immutable, so a duplicate cannot
    # be corrected afterwards: the history would permanently say a CV was sent
    # twice when it was sent once.
    with pytest.raises(IntegrityError):
        repo.insert_submission(
            "submission-duplicate",
            app_id,
            "external",
            None,
            pdf_id,
            "2026-08-18T12:00:00+00:00",
            {},
        )

    # An external submission may carry no artifact at all — applied through the
    # company's own form. Repeated NULLs stay legal under the same constraint.
    for index in (1, 2):
        repo.insert_submission(
            f"submission-no-artifact-{index}",
            app_id,
            "external",
            None,
            None,
            f"2026-08-18T1{index}:30:00+00:00",
            {},
        )
    assert len(repo.submissions(app_id)) == 3


def test_tracking_service_sets_next_action_without_changing_status(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="Service Action", target_role="Sales", job_text="Sales role", client="web"
        )
    )
    result = services.tracking.set_next_action(
        NextActionCommand(
            application_id=ingested.application_id,
            next_action="Follow up",
            next_action_date="2026-08-20",
            client="web",
        )
    )
    assert result.current_status == "saved"
    assert result.next_action == "Follow up"
    assert result.next_action_date == "2026-08-20"
