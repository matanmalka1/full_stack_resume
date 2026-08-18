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
from cv_engine.domain.models import (
    SelectionPlan,
    SelectionManifest,
    ValidationReport,
    ValidationRunLineage,
    WorkingDraft,
)
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
    initialize,
    sqlite_master_fingerprint,
)
from cv_engine.infrastructure.persistence.serialization import serialization_version
from cv_engine.util import normalized_text, sha256_text


IMMUTABLE_TABLES = (
    "fact_events",
    "job_snapshots",
    "job_analyses",
    "selection_plans",
    "status_history",
    "application_events",
    "artifact_versions",
    "decision_records",
    "generation_runs",
    "validation_runs",
    "migration_runs",
    "submissions",
)


def _create_application(repository, *, company: str, target_role: str, text: str):
    digest = sha256_text(text)
    return repository.create_application(
        company=company,
        target_role=target_role,
        payload_path=f"artifacts/snapshots/{company}/snapshot.txt",
        source_hash=digest,
        normalized_hash=sha256_text(normalized_text(text)),
    )


def _save_analysis(repository, application_id: str, snapshot_id: str, analysis):
    plan = SelectionManifest(
        policy_version="test-selection-v1",
        emphasis=analysis.emphasis,
        emphasis_policy_version="test-emphasis-v1",
    )
    return repository.save_analysis(
        application_id,
        snapshot_id,
        analysis,
        plan,
        provider="deterministic",
        model="rules-v1",
        candidate_context_version="candidate-v1",
        candidate_context_hash="candidate-hash",
        profile_version="profile-v1",
        selection_policy_version=plan.policy_version,
        track_emphasis_dependencies={
            "track": analysis.track.value,
            "emphasis": analysis.emphasis.value,
        },
    )


def test_numbered_migration_application_reapplication_and_version_gates(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state.sqlite3"
    repository = Repository(path)
    assert current_schema_version(path) == "0003"
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
    with connect(path) as connection:
        connection.executescript(
            (MIGRATIONS_DIR / "0001_baseline.sql").read_text(encoding="utf-8")
        )
    with pytest.raises(SchemaVersionError, match="cv workspace upgrade"):
        Repository(path)
    assert current_schema_version(path) == "0001"
    assert apply_migrations(path) == "0003"

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
    assert current_schema_version(empty) == "0003"


def test_verified_baseline_adoption_and_difference_reporting(tmp_path: Path) -> None:
    sql = (MIGRATIONS_DIR / "0001_baseline.sql").read_text(encoding="utf-8")
    adoptable = tmp_path / "adoptable.sqlite3"
    with connect(adoptable) as connection:
        connection.executescript(sql)
    before = None
    with connect(adoptable) as connection:
        before = sqlite_master_fingerprint(connection)
    with pytest.raises(SchemaVersionError, match="cv workspace upgrade"):
        Repository(adoptable)
    with connect(adoptable) as connection:
        assert sqlite_master_fingerprint(connection) == before == baseline_fingerprint()
        assert connection.execute(
            "SELECT version FROM schema_migrations"
        ).fetchone()[0] == "0001"
    additive = tmp_path / "additive-0002.sqlite3"
    with connect(additive) as connection:
        connection.executescript(sql)
        connection.executescript(
            (MIGRATIONS_DIR / "0002_preparation_records.sql").read_text(encoding="utf-8")
        )
        additive_columns = {
            row["name"]: row["notnull"]
            for row in connection.execute("PRAGMA table_info(job_snapshots)")
        }
    assert additive_columns["original_text"] == 1
    assert additive_columns["payload_path"] == 0
    assert additive_columns["source_hash"] == 0
    assert additive_columns["normalized_hash"] == 0

    assert apply_migrations(adoptable) == "0003"
    with connect(adoptable) as connection:
        columns = {
            row["name"]: row["notnull"]
            for row in connection.execute("PRAGMA table_info(job_snapshots)")
        }
    assert "original_text" not in columns
    assert columns["payload_path"] == 1
    assert columns["source_hash"] == 1
    assert columns["normalized_hash"] == 1

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
                "INSERT INTO job_snapshots(id, application_id, version_number, payload_path, "
                "source_hash, normalized_hash, captured_at, source_metadata_json, content_hash) "
                "VALUES('missing-snapshot', 'missing-app', 1, 'artifacts/snapshots/x.txt', "
                "'hash', 'normalized', '2026', '{}', 'hash')"
            )

    with repository.unit_of_work() as uow:
        bound = repository.bind(uow)
        app_id, _ = _create_application(
            bound, company="Committed", target_role="Developer", text="Python"
        )
        uow.commit()
    assert repository.get_application(app_id)["company"] == "Committed"

    with repository.unit_of_work() as uow:
        bound = repository.bind(uow)
        rolled_back_id, _ = _create_application(
            bound, company="Rolled Back", target_role="Developer", text="Python"
        )
    with pytest.raises(KeyError):
        repository.get_application(rolled_back_id)


def test_two_writers_honor_busy_wait_and_commit_serially(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "state.sqlite3")
    _create_application(
        repository, company="Writer", target_role="Developer", text="Python"
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
            "INSERT INTO job_snapshots(id, application_id, version_number, payload_path, "
            "source_hash, normalized_hash, captured_at, source_metadata_json, content_hash) "
            "VALUES('snapshot', 'app', 1, 'artifacts/snapshots/app/snapshot.txt', "
            "'hash', 'normalized', '2026', '{}', 'hash')"
        )
        connection.execute(
            "INSERT INTO job_analyses(id, application_id, job_snapshot_id, version_number, "
            "structured_json, provider, model, created_at) "
            "VALUES('analysis', 'app', 'snapshot', 1, '{}', 'deterministic', 'rules-v1', '2026')"
        )
        connection.execute(
            "INSERT INTO selection_plans(id, application_id, job_analysis_id, version_number, "
            "plan_json, candidate_context_version, candidate_context_hash, profile_version, "
            "selection_policy_version, track_emphasis_dependencies_json, created_at) "
            "VALUES('plan', 'app', 'analysis', 1, '{}', 'candidate-v1', 'candidate-hash', "
            "'profile-v1', 'selection-v1', '{}', '2026')"
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
    app_id, snapshot_id = _create_application(
        repository, company="Atomic", target_role="Developer", text="Python developer"
    )
    with repository.transaction() as connection:
        connection.execute(
            "UPDATE applications SET current_status='ready' WHERE id=?", (app_id,)
        )

    def fail_demotion(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("injected demotion failure")

    monkeypatch.setattr(SqliteApplicationRepository, "_set_status", fail_demotion)
    with pytest.raises(RuntimeError, match="injected demotion failure"):
        _save_analysis(
            repository, app_id, snapshot_id, classify_job("Python backend developer role")
        )

    with connect(repository.path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM job_analyses WHERE application_id=?", (app_id,)
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM selection_plans WHERE application_id=?", (app_id,)
        ).fetchone()[0] == 0
        application = connection.execute(
            "SELECT current_status, language, track, profile, emphasis, fit_level "
            "FROM applications WHERE id=?", (app_id,)
        ).fetchone()
    assert tuple(application) == ("ready", None, None, None, None, None)


def test_typed_preparation_records_round_trip_and_refuse_stale_edits(
    tmp_path: Path,
    draft_factory,
) -> None:
    repository = Repository(tmp_path / "preparation-records.sqlite3")
    app_id, snapshot_id = _create_application(
        repository,
        company="Typed Records",
        target_role="Developer",
        text="Python backend developer API React",
    )
    assert set(repository.get_snapshot(snapshot_id)) == {
        "id",
        "application_id",
        "version_number",
        "payload_path",
        "source_hash",
        "normalized_hash",
        "source_url",
        "captured_at",
        "source_metadata_json",
        "content_hash",
        "prior_snapshot_id",
    }
    analysis = classify_job("Python backend developer API React")
    analysis_id, _initial_plan = _save_analysis(repository, app_id, snapshot_id, analysis)
    document = draft_factory(
        "Python backend developer API React",
        application_id=app_id,
        job_snapshot_id=snapshot_id,
        job_analysis_id=analysis_id,
    ).draft
    assert document.selection is not None

    plan = repository.create_selection_plan(
        app_id,
        analysis_id,
        document.selection,
        candidate_context_version="candidate-v1",
        candidate_context_hash="candidate-hash",
        profile_version="profile-v1",
        selection_policy_version=document.selection.policy_version,
        track_emphasis_dependencies={
            "track": analysis.track.value,
            "emphasis": analysis.emphasis.value,
        },
    )
    assert isinstance(plan, SelectionPlan)
    assert repository.selection_plan(plan.id) == plan

    working = repository.create_working_draft(
        app_id,
        analysis_id,
        plan.id,
        document,
    )
    assert isinstance(working, WorkingDraft)
    assert repository.active_working_draft(app_id) == working

    changed_source = document.model_copy(update={"content_hash": "changed-hash"})
    changed = repository.update_working_draft(
        working.id,
        working.edit_version,
        changed_source,
    )
    assert changed.edit_version == working.edit_version + 1
    assert changed.content_hash == "changed-hash"

    with pytest.raises(ValueError, match="edit version mismatch"):
        repository.update_working_draft(
            working.id,
            working.edit_version,
            document.model_copy(update={"content_hash": "stale-write"}),
        )
    assert repository.working_draft(working.id) == changed

    lineage = ValidationRunLineage(
        working_draft_id=changed.id,
        edit_version=changed.edit_version,
        content_hash=changed.content_hash,
        job_snapshot_id=snapshot_id,
        job_analysis_id=analysis_id,
        selection_plan_id=plan.id,
        knowledge_context_hash="knowledge-hash",
        validator_versions={"draft": "2.0"},
    )
    validation_id = repository.record_validation(
        app_id,
        "pre-render",
        ValidationReport.from_findings({"content": True}, []),
        lineage=lineage,
    )
    assert repository.validation_lineage(validation_id) == lineage


def test_selection_plan_is_immutable_and_only_one_working_draft_can_be_active(
    tmp_path: Path,
    draft_factory,
) -> None:
    repository = Repository(tmp_path / "preparation-constraints.sqlite3")
    app_id, snapshot_id = _create_application(
        repository,
        company="Constraint Records",
        target_role="Developer",
        text="Python backend developer API React",
    )
    analysis = classify_job("Python backend developer API React")
    analysis_id, _initial_plan = _save_analysis(repository, app_id, snapshot_id, analysis)
    document = draft_factory(
        "Python backend developer API React",
        application_id=app_id,
        job_snapshot_id=snapshot_id,
        job_analysis_id=analysis_id,
    ).draft
    assert document.selection is not None
    plan = repository.create_selection_plan(
        app_id,
        analysis_id,
        document.selection,
        candidate_context_version="candidate-v1",
        candidate_context_hash="candidate-hash",
        profile_version="profile-v1",
        selection_policy_version=document.selection.policy_version,
        track_emphasis_dependencies={},
    )
    repository.create_working_draft(app_id, analysis_id, plan.id, document)

    with pytest.raises(sqlite3.IntegrityError, match="immutable record"):
        with repository.transaction() as connection:
            connection.execute(
                "UPDATE selection_plans SET plan_json=plan_json WHERE id=?",
                (plan.id,),
            )
    with pytest.raises(sqlite3.IntegrityError, match="immutable record"):
        with repository.transaction() as connection:
            connection.execute("DELETE FROM selection_plans WHERE id=?", (plan.id,))
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        repository.create_working_draft(app_id, analysis_id, plan.id, document)


def test_only_one_working_draft_per_application_can_be_active(tmp_path: Path) -> None:
    """Product invariant 3, enforced by storage rather than by a filesystem path.

    Before this boundary "one active draft" was an accident of every draft living
    at `working/{application_id}/`, which a second writer would simply overwrite.
    The partial unique index is what makes the invariant real, so it is asserted
    through raw SQL: a repository method could satisfy it by convention while the
    table underneath still allowed two.
    """
    database = tmp_path / "one-active.sqlite3"
    initialize(database)
    now = "2026-08-18T00:00:00+00:00"

    def insert_draft(connection: object, draft_id: str, *, active: int) -> None:
        connection.execute(
            "INSERT INTO working_drafts(id, application_id, job_analysis_id, selection_plan_id, "
            "source_json, edit_version, content_hash, active, created_at, updated_at) "
            "VALUES(?, 'a', 'an', 'pl', '{}', 1, 'h', ?, ?, ?)",
            (draft_id, active, now, now),
        )

    with connect(database) as connection:
        connection.execute(
            "INSERT INTO applications(id, company, target_role, current_status, created_at, "
            "updated_at) VALUES('a', 'C', 'R', 'saved', ?, ?)",
            (now, now),
        )
        connection.execute(
            "INSERT INTO job_snapshots(id, application_id, version_number, payload_path, "
            "source_hash, normalized_hash, captured_at, source_metadata_json, content_hash) "
            "VALUES('s', 'a', 1, 'p', 'h', 'n', ?, '{}', 'h')",
            (now,),
        )
        connection.execute(
            "INSERT INTO job_analyses(id, application_id, job_snapshot_id, version_number, "
            "structured_json, provider, model, created_at) "
            "VALUES('an', 'a', 's', 1, '{}', 'deterministic', 'rules-v1', ?)",
            (now,),
        )
        connection.execute(
            "INSERT INTO selection_plans(id, application_id, job_analysis_id, version_number, "
            "plan_json, candidate_context_version, candidate_context_hash, profile_version, "
            "selection_policy_version, track_emphasis_dependencies_json, created_at) "
            "VALUES('pl', 'a', 'an', 1, '{}', 'v', 'h', 'pv', '1.0.0', '{}', ?)",
            (now,),
        )
        insert_draft(connection, "first", active=1)

        with pytest.raises(sqlite3.IntegrityError, match="working_drafts.application_id"):
            insert_draft(connection, "second", active=1)

        # Deactivating releases the slot, and the superseded row survives as history.
        connection.execute("UPDATE working_drafts SET active=0 WHERE id='first'")
        insert_draft(connection, "third", active=1)
        assert connection.execute(
            "SELECT COUNT(*) FROM working_drafts WHERE application_id='a'"
        ).fetchone()[0] == 2

