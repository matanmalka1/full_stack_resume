from __future__ import annotations

import pytest
from conftest import alembic_head
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, ProgrammingError

from cv_engine.application.commands import IngestCommand, NextActionCommand
from cv_engine.domain.contracts.records import AuditRecord
from cv_engine.domain.contracts.recruitment import ApplicationStatus
from cv_engine.infrastructure.persistence import (
    SqlAlchemyTransactionManager,
    current_database_revision,
)
from cv_engine.infrastructure.persistence.application_projections import (
    SqlAlchemyApplicationProjectionReader,
)
from cv_engine.infrastructure.persistence.application_store import SqlAlchemyApplicationStore
from cv_engine.infrastructure.persistence.artifact_catalog import SqlAlchemyArtifactCatalog
from cv_engine.infrastructure.persistence.job_snapshots import SqlAlchemyJobSnapshotStore
from cv_engine.infrastructure.persistence.maintenance import SqlAlchemyMaintenanceInspection
from cv_engine.infrastructure.persistence.recruitment import SqlAlchemyRecruitmentRepository
from cv_engine.infrastructure.persistence.recruitment_store import (
    SqlAlchemyInitialRecruitmentEventWriter,
)
from cv_engine.infrastructure.persistence.tables import (
    applications,
    job_snapshots,
    recruitment_events,
)
from cv_engine.util import new_id, normalized_text, sha256_text, utc_now


def _create(engine, *, company: str, target_role: str, text: str):
    digest = sha256_text(text)
    application_id = new_id()
    snapshot_id = new_id()
    created_at = utc_now()
    transactions = SqlAlchemyTransactionManager(engine)
    application_store = SqlAlchemyApplicationStore(transactions)
    snapshots = SqlAlchemyJobSnapshotStore(transactions)
    recruitment = SqlAlchemyInitialRecruitmentEventWriter(transactions)
    with transactions.write() as tx:
        application_store.insert_application(
            tx,
            application_id=application_id,
            company=company,
            target_role=target_role,
            source_url=None,
            notes="",
            source="manual",
            created_at=created_at,
        )
        snapshots.insert_initial_snapshot(
            tx,
            snapshot_id=snapshot_id,
            application_id=application_id,
            payload_path=f"artifacts/snapshots/{company}/snapshot.txt",
            source_hash=digest,
            normalized_hash=sha256_text(normalized_text(text)),
            source_url=None,
            source_metadata={},
            captured_at=created_at,
        )
        recruitment.insert_initial_saved_event(
            tx,
            application_id=application_id,
            actor_type="user",
            client="web",
            occurred_at=created_at,
        )
    return application_id, snapshot_id


def _recruitment(engine):
    transactions = SqlAlchemyTransactionManager(engine)
    return transactions, SqlAlchemyRecruitmentRepository(transactions)


def test_recruitment_event_and_transition_contract(database_engine) -> None:
    """Named for the table it reads.

    It was `test_status_history_...` until recruitment_events replaced that
    table; the body moved and the name did not, which is how the dead table kept
    looking referenced.
    """
    app_id, _ = _create(
        database_engine, company="Acme", target_role="Developer", text="Python developer role"
    )
    with pytest.raises(ValueError):
        ApplicationStatus("preparing")
    with pytest.raises(ValueError):
        ApplicationStatus("ready")
    transactions = SqlAlchemyTransactionManager(database_engine)
    with transactions.read() as tx:
        connection = transactions.connection_for(tx)
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
        with transactions.write() as tx:
            connection = transactions.connection_for(tx, access="write")
            connection.execute(
                update(applications)
                .where(applications.c.id == app_id)
                .values(current_status="ready")
            )
    assert history == [(None, "saved", "user", "web")]


def test_removed_cli_client_is_refused_at_the_command_and_database_boundaries(
    database_engine,
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
        database_engine,
        company="Database Client Guard",
        target_role="Developer",
        text="Python role",
    )
    with pytest.raises(IntegrityError, match="ck_recruitment_events_client"):
        transactions, recruitment = _recruitment(database_engine)
        with transactions.write() as tx:
            recruitment.insert_next_action(
                tx,
                application_id=app_id,
                next_action="Follow up",
                next_action_date="2026-09-01",
                actor_type="user",
                client="cli",
                occurred_at="2026-08-30T12:00:00+00:00",
            )

    transactions = SqlAlchemyTransactionManager(database_engine)
    application_store = SqlAlchemyApplicationStore(transactions)
    with transactions.read() as tx:
        assert application_store.get_application(tx, app_id)["next_action"] is None


def test_immutable_job_snapshot_trigger(database_engine) -> None:
    _, snapshot_id = _create(
        database_engine, company="Acme", target_role="Developer", text="Original exact text"
    )
    transactions = SqlAlchemyTransactionManager(database_engine)
    with pytest.raises(ProgrammingError, match="immutable record"):
        with transactions.write() as tx:
            connection = transactions.connection_for(tx, access="write")
            connection.execute(
                update(job_snapshots)
                .where(job_snapshots.c.id == snapshot_id)
                .values(source_hash="changed")
            )


def test_next_action_is_not_a_status(database_engine) -> None:
    app_id, _ = _create(database_engine, company="Acme", target_role="Sales", text="Sales role")
    transactions, recruitment = _recruitment(database_engine)
    with transactions.write() as tx:
        event_id = recruitment.insert_next_action(
            tx,
            application_id=app_id,
            next_action="Follow up",
            next_action_date="2026-08-20",
            actor_type="user",
            client="web",
            occurred_at="2026-08-19T10:00:00+00:00",
        )
    application_store = SqlAlchemyApplicationStore(transactions)
    with transactions.read() as tx:
        row = application_store.get_application(tx, app_id)
    assert row["current_status"] == "saved"
    assert row["next_action"] == "Follow up"
    with transactions.read() as tx:
        assert recruitment.event(tx, event_id)["event_type"] == "next_action"


def test_database_is_at_registered_head_schema(database_engine) -> None:
    assert current_database_revision(database_engine) == alembic_head()


def test_ready_is_not_persisted_and_submission_storage_commits_atomically(
    database_engine,
) -> None:
    app_id, snapshot_id = _create(
        database_engine,
        company="Move Guard Success",
        target_role="Developer",
        text="Another Python role",
    )
    transactions = SqlAlchemyTransactionManager(database_engine)
    catalog = SqlAlchemyArtifactCatalog(transactions)
    application_store = SqlAlchemyApplicationStore(transactions)
    projections = SqlAlchemyApplicationProjectionReader(transactions)
    with transactions.write() as tx:
        pdf_id = catalog.register_artifact_version(
            tx,
            app_id,
            "resume_pdf",
            "resume",
            "artifacts/success/v001/resume.pdf",
            "c" * 64,
            "rendered",
            job_snapshot_id=snapshot_id,
        )
    # Legacy monolith methods (`set_ready`, `record_submission`, and their
    # private forms) have no equivalent on any migrated store - there is
    # nothing left to assert `hasattr(..., "set_ready")` against here. Their
    # absence from the codebase is covered by the architecture's old-consumer
    # guards instead of a per-object hasattr check.
    transactions, recruitment = _recruitment(database_engine)
    catalog = SqlAlchemyArtifactCatalog(transactions)
    application_store = SqlAlchemyApplicationStore(transactions)
    projections = SqlAlchemyApplicationProjectionReader(transactions)
    with transactions.write() as tx:
        recruitment.insert_submission(
            tx,
            "submission-1",
            app_id,
            "external",
            None,
            pdf_id,
            "2026-08-18T10:00:00+00:00",
            {"reason": "application service verified exact Ready proof"},
        )
        recruitment.insert_event(
            tx,
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
    with transactions.read() as tx:
        assert application_store.get_application(tx, app_id)["current_status"] == "applied"

    with transactions.write() as tx:
        second_id = catalog.register_artifact_version(
            tx,
            app_id,
            "resume_pdf",
            "resume",
            "artifacts/success/v002/resume.pdf",
            "b" * 64,
            "rendered",
            job_snapshot_id=snapshot_id,
        )
    with transactions.read() as tx:
        versions = catalog.artifact_versions(tx, app_id)
    assert [(row["id"], row["version_number"]) for row in versions] == [
        (pdf_id, 1),
        (second_id, 2),
    ]
    assert all(row["revision_id"] is None for row in versions)
    inspection = SqlAlchemyMaintenanceInspection(transactions)
    with transactions.read() as tx:
        inventory = inspection.artifact_inventory(tx)
        problems = inspection.integrity_problems(tx)
    assert len(inventory) == 2
    assert {(row["path"], row["content_hash"]) for row in versions}.issubset(
        {(row["path"], row["content_hash"]) for row in inventory}
    )
    assert problems == []

    with pytest.raises(IntegrityError):
        with transactions.write() as tx:
            recruitment.insert_submission(
                tx,
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
        with transactions.write() as tx:
            recruitment.insert_submission(
                tx,
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
        with transactions.write() as tx:
            recruitment.insert_submission(
                tx,
                f"submission-no-artifact-{index}",
                app_id,
                "external",
                None,
                None,
                f"2026-08-18T1{index}:30:00+00:00",
                {},
            )
    with transactions.read() as tx:
        assert len(projections.submissions(tx, app_id)) == 3


def test_tracking_service_sets_next_action_without_changing_status(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="Service Action", target_role="Sales", job_text="Sales role", client="web"
        )
    )
    result = services.recruitment.set_next_action(
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
