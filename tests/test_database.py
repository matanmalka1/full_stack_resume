from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cv_engine.application.commands import IngestCommand, NextActionCommand
from cv_engine.infrastructure.db import connect
from cv_engine.domain.models import ApplicationStatus, ValidationReport


SCHEMA_FIXTURE = Path(__file__).parent / "fixtures/m1_sqlite_master.tsv"


def _sqlite_master_fingerprint(path: Path) -> list[tuple[str, str, str, str]]:
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            # schema_migrations is runner bookkeeping, not part of the M1
            # product schema whose fixture bytes are intentionally frozen.
            "WHERE sql IS NOT NULL AND name != 'schema_migrations' "
            "ORDER BY type, name"
        ).fetchall()
    return [
        (kind, name, table, " ".join(ddl.split()))
        for kind, name, table, ddl in rows
    ]


def test_status_history_and_transition_contract(application_repo) -> None:
    repo = application_repo
    app_id, _ = repo.create_application(company="Acme", target_role="Developer", original_job_text="Python developer role")
    repo.transition_status(app_id, ApplicationStatus.PREPARING, "analysis")
    assert repo.get_application(app_id)["current_status"] == "preparing"
    with pytest.raises(ValueError, match="engine-owned"):
        repo.transition_status(app_id, ApplicationStatus.READY)
    with pytest.raises(ValueError) as applied_refusal:
        repo.transition_status(app_id, ApplicationStatus.APPLIED)
    assert str(applied_refusal.value) == (
        "applied is submission-owned; it can only be reached through "
        "Engine.submit(), which performs fresh ready integrity verification "
        "and binds the submission to the exact validated PDF artifact version. "
        "The generic status transition never accepts applied, even with a real "
        "rendered PDF artifact version id, because it cannot perform that "
        "verification itself."
    )
    with connect(repo.path) as connection:
        history = connection.execute("SELECT from_status, to_status FROM status_history WHERE application_id=? ORDER BY id", (app_id,)).fetchall()
    assert [tuple(row) for row in history] == [(None, "saved"), ("saved", "preparing")]


def test_immutable_job_snapshot_trigger(application_repo) -> None:
    repo = application_repo
    _, snapshot_id = repo.create_application(company="Acme", target_role="Developer", original_job_text="Original exact text")
    with pytest.raises(sqlite3.IntegrityError, match="immutable record"):
        with repo.transaction() as connection:
            connection.execute("UPDATE job_snapshots SET original_text='changed' WHERE id=?", (snapshot_id,))


def test_next_action_is_not_a_status(application_repo) -> None:
    repo = application_repo
    app_id, _ = repo.create_application(company="Acme", target_role="Sales", original_job_text="Sales role")
    repo.set_next_action(app_id, "Follow up", "2026-08-20")
    row = repo.get_application(app_id)
    assert row["current_status"] == "saved"
    assert row["next_action"] == "Follow up"


def test_m1_sqlite_master_fingerprint_is_frozen(application_repo) -> None:
    expected = [
        tuple(line.split("\t", 3))
        for line in SCHEMA_FIXTURE.read_text(encoding="utf-8").splitlines()
    ]
    assert _sqlite_master_fingerprint(application_repo.path) == expected


def test_ready_submission_and_artifact_registry_preconditions(application_repo) -> None:
    repo = application_repo
    refused_app, refused_snapshot = repo.create_application(
        company="Move Guard", target_role="Developer", original_job_text="Python role"
    )
    repo.transition_status(refused_app, ApplicationStatus.PREPARING, "analysis")
    with pytest.raises(ValueError, match="rendered resume PDF"):
        repo.set_ready(refused_app, "missing")
    refused_pdf = repo.register_artifact_version(
        refused_app, "resume_pdf", "resume", "artifacts/refused/v001/resume.pdf",
        "a" * 64, "rendered", job_snapshot_id=refused_snapshot,
    )
    with pytest.raises(ValueError, match="post-render validation"):
        repo.set_ready(refused_app, refused_pdf)
    repo.record_validation(
        refused_app, "post-render",
        ValidationReport.from_findings({"render": False}, []), refused_pdf,
    )
    with pytest.raises(ValueError, match="passing post-render validation"):
        repo.set_ready(refused_app, refused_pdf)

    app_id, snapshot_id = repo.create_application(
        company="Move Guard Success", target_role="Developer",
        original_job_text="Another Python role",
    )
    repo.transition_status(app_id, ApplicationStatus.PREPARING, "analysis")
    pdf_id = repo.register_artifact_version(
        app_id, "resume_pdf", "resume", "artifacts/success/v001/resume.pdf",
        "c" * 64, "rendered", job_snapshot_id=snapshot_id,
    )
    repo.record_validation(
        app_id, "post-render",
        ValidationReport.from_findings({"render": True}, []), pdf_id,
    )
    repo.set_ready(app_id, pdf_id)
    with pytest.raises(ValueError, match="rendered resume PDF"):
        repo.record_submission(app_id, "missing")
    assert repo.record_submission(app_id, pdf_id)
    assert repo.get_application(app_id)["current_status"] == "applied"

    second_id = repo.register_artifact_version(
        app_id, "resume_pdf", "resume", "artifacts/success/v002/resume.pdf",
        "b" * 64, "rendered", job_snapshot_id=snapshot_id,
    )
    versions = repo.artifact_versions(app_id)
    assert [(row["id"], row["version_number"]) for row in versions] == [
        (pdf_id, 1), (second_id, 2),
    ]
    inventory = repo.artifact_inventory()
    assert len(inventory) == 3
    assert {(row["path"], row["content_hash"]) for row in versions}.issubset(
        {(row["path"], row["content_hash"]) for row in inventory}
    )
    assert repo.integrity_check() == []


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
