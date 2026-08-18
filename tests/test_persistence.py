from __future__ import annotations

import inspect
import sqlite3
import threading
import time
import uuid
from pathlib import Path

import pytest

from cv_engine.application.ports import ArtifactRegistry
from cv_engine.domain.analysis.classification import classify_job
from cv_engine.infrastructure.persistence.applications import SqliteApplicationRepository
from cv_engine.infrastructure.persistence import (
    MigrationChecksumError,
    Repository,
    SchemaFingerprintError,
    SchemaVersionError,
    apply_migrations,
    connect,
    current_schema_version,
)
from cv_engine.infrastructure.persistence.primitives import new_id
from cv_engine.infrastructure.persistence.schema import (
    MIGRATIONS_DIR,
    baseline_fingerprint,
    sqlite_master_fingerprint,
)
from cv_engine.infrastructure.persistence.serialization import serialization_version


IMMUTABLE_TABLES = (
    "fact_events",
    "job_snapshots",
    "job_analyses",
    "status_history",
    "application_events",
    "artifact_versions",
    "decision_records",
    "generation_runs",
    "validation_runs",
    "migration_runs",
    "submissions",
)


def test_numbered_migration_application_reapplication_and_version_gates(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state.sqlite3"
    repository = Repository(path)
    assert current_schema_version(path) == "0001"
    with connect(path) as connection:
        assert connection.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()[0] == "2"
        first = connection.execute(
            "SELECT version, name, checksum FROM schema_migrations"
        ).fetchall()
    apply_migrations(path)
    with connect(path) as connection:
        assert connection.execute(
            "SELECT version, name, checksum FROM schema_migrations"
        ).fetchall() == first

        connection.execute("UPDATE schema_migrations SET checksum='changed'")
        connection.commit()
    with pytest.raises(MigrationChecksumError, match="checksum changed"):
        Repository(path)

    path = tmp_path / "lower.sqlite3"
    Repository(path)
    with connect(path) as connection:
        connection.execute("DELETE FROM schema_migrations")
        connection.commit()
    with pytest.raises(SchemaVersionError, match="cv workspace upgrade"):
        Repository(path)
    assert apply_migrations(path) == "0001"

    with connect(path) as connection:
        connection.execute(
            "INSERT INTO schema_migrations(version, name, checksum, applied_at) "
            "VALUES('9999', '9999_future.sql', 'x', '2026-01-01')"
        )
        connection.commit()
    with pytest.raises(SchemaVersionError, match="unknown or newer"):
        Repository(path)
    assert repository.path.name == "state.sqlite3"

    empty = tmp_path / "empty.sqlite3"
    empty.touch()
    Repository(empty)
    assert current_schema_version(empty) == "0001"


def test_verified_baseline_adoption_and_difference_reporting(tmp_path: Path) -> None:
    sql = (MIGRATIONS_DIR / "0001_baseline.sql").read_text(encoding="utf-8")
    adoptable = tmp_path / "adoptable.sqlite3"
    with connect(adoptable) as connection:
        connection.executescript(sql)
    before = None
    with connect(adoptable) as connection:
        before = sqlite_master_fingerprint(connection)
    Repository(adoptable)
    with connect(adoptable) as connection:
        assert sqlite_master_fingerprint(connection) == before == baseline_fingerprint()
        assert connection.execute(
            "SELECT version FROM schema_migrations"
        ).fetchone()[0] == "0001"

    mismatch = tmp_path / "mismatch.sqlite3"
    with connect(mismatch) as connection:
        connection.executescript(sql)
        connection.execute("CREATE TABLE unexpected(id TEXT PRIMARY KEY)")
    with pytest.raises(SchemaFingerprintError, match="extra=.*unexpected"):
        Repository(mismatch)


def test_connection_policy_unit_of_work_bind_and_foreign_keys(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "state.sqlite3")
    with connect(repository.path) as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            connection.execute(
                "INSERT INTO job_snapshots(id, application_id, version_number, original_text, "
                "captured_at, source_metadata_json, content_hash) "
                "VALUES('missing-snapshot', 'missing-app', 1, 'x', '2026', '{}', 'x')"
            )

    with repository.unit_of_work() as uow:
        bound = repository.bind(uow)
        app_id, _ = bound.create_application(
            company="Committed", target_role="Developer", original_job_text="Python"
        )
        uow.commit()
    assert repository.get_application(app_id)["company"] == "Committed"

    with repository.unit_of_work() as uow:
        bound = repository.bind(uow)
        rolled_back_id, _ = bound.create_application(
            company="Rolled Back", target_role="Developer", original_job_text="Python"
        )
    with pytest.raises(KeyError):
        repository.get_application(rolled_back_id)


def test_two_writers_honor_busy_wait_and_commit_serially(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "state.sqlite3")
    repository.create_application(
        company="Writer", target_role="Developer", original_job_text="Python"
    )
    started = threading.Event()
    release = threading.Event()
    results: list[str] = []

    def first_writer() -> None:
        with repository.unit_of_work() as uow:
            uow.connection.execute(
                "UPDATE applications SET notes='first' WHERE company='Writer'"
            )
            started.set()
            release.wait(timeout=2)
            uow.commit()

    def second_writer() -> None:
        started.wait(timeout=2)
        with repository.unit_of_work() as uow:
            uow.connection.execute(
                "UPDATE applications SET notes='second' WHERE company='Writer'"
            )
            uow.commit()
            results.append("committed")

    first = threading.Thread(target=first_writer)
    second = threading.Thread(target=second_writer)
    first.start()
    second.start()
    time.sleep(0.05)
    release.set()
    first.join(timeout=2)
    second.join(timeout=2)
    assert results == ["committed"]
    assert repository.list_applications()[0]["notes"] == "second"


def _seed_immutable_tables(repository: Repository) -> None:
    with repository.transaction() as connection:
        connection.execute(
            "INSERT INTO applications(id, company, target_role, current_status, created_at, updated_at) "
            "VALUES('app', 'Co', 'Role', 'saved', '2026', '2026')"
        )
        connection.execute(
            "INSERT INTO job_snapshots(id, application_id, version_number, original_text, "
            "captured_at, source_metadata_json, content_hash) "
            "VALUES('snapshot', 'app', 1, 'text', '2026', '{}', 'hash')"
        )
        connection.execute(
            "INSERT INTO job_analyses(id, application_id, job_snapshot_id, version_number, "
            "structured_json, provider, model, created_at) "
            "VALUES('analysis', 'app', 'snapshot', 1, '{}', 'deterministic', 'rules-v1', '2026')"
        )
        connection.execute(
            "INSERT INTO status_history(application_id, from_status, to_status, changed_at) "
            "VALUES('app', NULL, 'saved', '2026')"
        )
        connection.execute(
            "INSERT INTO application_events(id, application_id, event_type, payload_json, created_at) "
            "VALUES('event', 'app', 'created', '{}', '2026')"
        )
        connection.execute(
            "INSERT INTO artifacts(id, application_id, artifact_type, logical_name, created_at) "
            "VALUES('artifact', 'app', 'resume_pdf', 'resume', '2026')"
        )
        connection.execute(
            "INSERT INTO artifact_versions(id, artifact_id, version_number, lifecycle_status, "
            "path, content_hash, created_at) "
            "VALUES('version', 'artifact', 1, 'rendered', 'output.pdf', 'hash', '2026')"
        )
        connection.execute(
            "INSERT INTO decision_records(id, application_id, artifact_version_id, job_snapshot_id, "
            "job_analysis_id, structured_json, summary, created_at) "
            "VALUES('decision', 'app', 'version', 'snapshot', 'analysis', '{}', 'summary', '2026')"
        )
        connection.execute(
            "INSERT INTO generation_runs(id, application_id, created_at, engine_version, profile_version, "
            "rendering_rules_version, facts_version, ai_provider, ai_model, task_contract_version, "
            "prompt_version, job_analysis_version, instruction_overrides_json, status) "
            "VALUES('generation', 'app', '2026', '1', '1', '1', '1', 'none', 'none', '1', '1', '1', '{}', 'completed')"
        )
        connection.execute(
            "INSERT INTO validation_runs(id, application_id, artifact_version_id, phase, report_json, created_at) "
            "VALUES('validation', 'app', 'version', 'post-render', '{}', '2026')"
        )
        connection.execute(
            "INSERT INTO migration_runs(id, snapshot_id, manifest_hash, dry_run_report_hash, row_count, "
            "artifact_count, report_json, created_at) "
            "VALUES('migration', 'backup', 'hash', 'hash', 1, 1, '{}', '2026')"
        )
        connection.execute(
            "INSERT INTO submissions(id, application_id, artifact_version_id, submitted_at) "
            "VALUES('submission', 'app', 'version', '2026')"
        )
        connection.execute(
            "INSERT INTO fact_events(id, fact_id, source_file, event_type, to_status, fact_json, "
            "fact_hash, facts_version, lifecycle_version, created_at) "
            "VALUES('fact-event', 'fact', 'base/common.md', 'fact_created', 'pending', '{}', 'hash', '1', '1', '2026')"
        )


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_all_immutable_tables_reject_sql_bypass(
    tmp_path: Path, operation: str
) -> None:
    repository = Repository(tmp_path / f"{operation}.sqlite3")
    _seed_immutable_tables(repository)
    for table in IMMUTABLE_TABLES:
        statement = (
            f"UPDATE {table} SET rowid=rowid"
            if operation == "update"
            else f"DELETE FROM {table}"
        )
        with pytest.raises(sqlite3.IntegrityError, match="immutable record"):
            with repository.transaction() as connection:
                connection.execute(statement)


def test_identity_serialization_registry_and_typed_artifact_ports() -> None:
    values = [new_id() for _ in range(20)]
    assert len(set(values)) == len(values)
    assert all(uuid.UUID(value).version == 4 for value in values)
    assert serialization_version("payload_manifest") == "1"
    with pytest.raises(ValueError, match="unregistered"):
        serialization_version("historical_report")

    for member in (
        "register_artifact_version",
        "record_decision",
        "record_validation",
        "latest_artifact_version",
    ):
        parameters = inspect.signature(getattr(ArtifactRegistry, member)).parameters.values()
        assert all(
            parameter.kind
            not in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD)
            for parameter in parameters
        )


def test_analysis_and_ready_demotion_commit_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = Repository(tmp_path / "atomic-analysis.sqlite3")
    app_id, snapshot_id = repository.create_application(
        company="Atomic", target_role="Developer", original_job_text="Python developer"
    )
    with repository.transaction() as connection:
        connection.execute(
            "UPDATE applications SET current_status='ready' WHERE id=?", (app_id,)
        )

    def fail_demotion(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("injected demotion failure")

    monkeypatch.setattr(SqliteApplicationRepository, "_set_status", fail_demotion)
    with pytest.raises(RuntimeError, match="injected demotion failure"):
        repository.save_analysis(
            app_id, snapshot_id, classify_job("Python backend developer role")
        )

    with connect(repository.path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM job_analyses WHERE application_id=?", (app_id,)
        ).fetchone()[0] == 0
        application = connection.execute(
            "SELECT current_status, language, track, profile, emphasis, fit_level "
            "FROM applications WHERE id=?", (app_id,)
        ).fetchone()
    assert tuple(application) == ("ready", None, None, None, None, None)
