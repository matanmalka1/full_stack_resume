from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cv_engine.infrastructure.db import connect
from cv_engine.domain.models import ApplicationStatus


SCHEMA_FIXTURE = Path(__file__).parent / "fixtures/m1_sqlite_master.tsv"


def _sqlite_master_fingerprint(path: Path) -> list[tuple[str, str, str, str]]:
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE sql IS NOT NULL ORDER BY type, name"
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
    with pytest.raises(ValueError, match="submission-owned"):
        repo.transition_status(app_id, ApplicationStatus.APPLIED)
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

