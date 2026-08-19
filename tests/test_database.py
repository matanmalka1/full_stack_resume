from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cv_engine.application.commands import IngestCommand, NextActionCommand
from cv_engine.domain.models import ApplicationStatus
from cv_engine.infrastructure.persistence import connect, current_schema_version
from cv_engine.infrastructure.persistence.schema import (
    MIGRATIONS_DIR,
    registered_migration_names,
)
from cv_engine.util import normalized_text, sha256_text

SCHEMA_FIXTURE = Path(__file__).parent / "fixtures/schema_sqlite_master.tsv"


def _create(repo, *, company: str, target_role: str, text: str):
    digest = sha256_text(text)
    return repo.create_application(
        company=company,
        target_role=target_role,
        payload_path=f"artifacts/snapshots/{company}/snapshot.txt",
        source_hash=digest,
        normalized_hash=sha256_text(normalized_text(text)),
    )


def _sqlite_master_fingerprint(path: Path) -> list[tuple[str, str, str, str]]:
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            # schema_migrations is runner bookkeeping, not part of the product
            # schema whose fixture bytes are intentionally frozen.
            "WHERE sql IS NOT NULL AND name != 'schema_migrations' "
            "ORDER BY type, name"
        ).fetchall()
    return [(kind, name, table, " ".join(ddl.split())) for kind, name, table, ddl in rows]


def test_status_history_and_transition_contract(application_repo) -> None:
    repo = application_repo
    app_id, _ = _create(repo, company="Acme", target_role="Developer", text="Python developer role")
    assert not hasattr(repo, "transition_status")
    with pytest.raises(ValueError):
        ApplicationStatus("preparing")
    with pytest.raises(ValueError):
        ApplicationStatus("ready")
    with connect(repo.path) as connection:
        history = connection.execute(
            "SELECT from_status, to_status, actor_type, client FROM recruitment_events "
            "WHERE application_id=? ORDER BY rowid",
            (app_id,),
        ).fetchall()
        with pytest.raises(sqlite3.IntegrityError, match="invalid recruitment status"):
            connection.execute(
                "UPDATE applications SET current_status='ready' WHERE id=?", (app_id,)
            )
    assert [tuple(row) for row in history] == [(None, "saved", "user", "cli")]


def test_immutable_job_snapshot_trigger(application_repo) -> None:
    repo = application_repo
    _, snapshot_id = _create(
        repo, company="Acme", target_role="Developer", text="Original exact text"
    )
    with pytest.raises(sqlite3.IntegrityError, match="immutable record"):
        with repo.transaction() as connection:
            connection.execute(
                "UPDATE job_snapshots SET source_hash='changed' WHERE id=?", (snapshot_id,)
            )


def test_next_action_is_not_a_status(application_repo) -> None:
    repo = application_repo
    app_id, _ = _create(repo, company="Acme", target_role="Sales", text="Sales role")
    event_id = repo.insert_next_action_event(
        application_id=app_id,
        next_action="Follow up",
        next_action_date="2026-08-20",
        actor_type="user",
        client="cli",
        installation_id="test-installation",
        occurred_at="2026-08-19T10:00:00+00:00",
    )
    row = repo.get_application(app_id)
    assert row["current_status"] == "saved"
    assert row["next_action"] == "Follow up"
    assert repo.recruitment_event(event_id)["event_type"] == "next_action"


def test_sqlite_master_fingerprint_matches_the_recorded_schema(tmp_path: Path) -> None:
    """Every table, index, and trigger the baseline creates, recorded verbatim.

    This froze the M1 baseline while later migrations added to it, so that a
    database created at M1 could still be upgraded. Squashing the chain retired
    that job: with one migration there is no earlier shape to stay compatible
    with. What it still catches is a schema change nobody meant to make —
    dropping a trigger while editing the table above it moves this fixture, and
    moving it has to be deliberate.
    """
    baseline_path = tmp_path / "baseline.sqlite3"
    with connect(baseline_path) as connection:
        connection.executescript((MIGRATIONS_DIR / "0001_baseline.sql").read_text(encoding="utf-8"))
    expected = [
        tuple(line.split("\t", 3))
        for line in SCHEMA_FIXTURE.read_text(encoding="utf-8").splitlines()
    ]
    assert _sqlite_master_fingerprint(baseline_path) == expected


def test_database_is_at_registered_head_schema(application_repo) -> None:
    # The fingerprint proves what the baseline creates; this proves the runner
    # actually recorded it, so a database that silently skipped the migration
    # fails here rather than at the first query that needs a missing table.
    registered_head = registered_migration_names()[-1].split("_", 1)[0]
    assert current_schema_version(application_repo.path) == registered_head


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
            client="cli",
            installation_id="test-installation",
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

    with pytest.raises(sqlite3.IntegrityError):
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
    with pytest.raises(sqlite3.IntegrityError):
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
        IngestCommand(company="Service Action", target_role="Sales", job_text="Sales role")
    )
    result = services.tracking.set_next_action(
        NextActionCommand(
            application_id=ingested.application_id,
            next_action="Follow up",
            next_action_date="2026-08-20",
        )
    )
    assert result.current_status == "saved"
    assert result.next_action == "Follow up"
    assert result.next_action_date == "2026-08-20"
