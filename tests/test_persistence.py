from __future__ import annotations

import inspect
import sqlite3
import threading
import time
import uuid
from pathlib import Path

import pytest

from cv_engine.application.knowledge_mutations import (
    KnowledgeMutationState,
    PrepareKnowledgeMutation,
)
from cv_engine.application.ports import ArtifactRegistry
from cv_engine.domain.analysis.classification import classify_job
from cv_engine.domain.models import (
    AuditRecord,
    SelectionManifest,
    SelectionPlan,
    ValidationReport,
    ValidationRunLineage,
    WorkingDraft,
)
from cv_engine.infrastructure.persistence import (
    MigrationChecksumError,
    Repository,
    SchemaFingerprintError,
    SchemaVersionError,
    apply_migrations,
    connect,
    current_schema_version,
)
from cv_engine.infrastructure.persistence.schema import (
    MIGRATIONS_DIR,
    baseline_fingerprint,
    initialize,
    registered_migration_names,
    sqlite_master_fingerprint,
)
from cv_engine.util import new_id, normalized_text, sha256_text

# Immutability is the default, so nothing has to be registered when an immutable
# table is added. A table is exempt only by being named here, which means that
# forgetting a trigger pair fails this module instead of passing silently — the
# defect an inclusion list cannot detect, because a table nobody remembered to
# list looks exactly like a table that does not exist.
MUTABLE_TABLES = frozenset(
    {
        "applications",  # the current recruitment projection and tracking fields
        "working_drafts",  # the one mutable resume document (product invariant 3)
        "operations",  # mutable only until a terminal status; terminal rows have a trigger
        "operation_resource_leases",  # ephemeral claim/heartbeat coordination
        "operation_outputs",  # permits exactly one inactive-to-active transition
        "idempotency_receipts",  # permits exactly one pending-to-completed transition
        "knowledge_mutation_journal",  # permits one prepared-to-terminal transition
        "schema_meta",  # bookkeeping
        "schema_migrations",  # bookkeeping
        "sqlite_sequence",  # SQLite's own AUTOINCREMENT bookkeeping
    }
)

IMMUTABLE_ABORT = "RAISE(ABORT, 'immutable record')"

# Derived, never written down: a new migration must not require editing a test.
HEAD_VERSION = registered_migration_names()[-1].split("_", 1)[0]


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
    assert current_schema_version(path) == HEAD_VERSION
    with connect(path) as connection:
        assert (
            connection.execute(
                "SELECT value FROM schema_meta WHERE key='schema_version'"
            ).fetchone()[0]
            == "2"
        )
        first = connection.execute(
            "SELECT version, name, checksum FROM schema_migrations"
        ).fetchall()
    apply_migrations(path)
    with connect(path) as connection:
        assert (
            connection.execute("SELECT version, name, checksum FROM schema_migrations").fetchall()
            == first
        )

        connection.execute("UPDATE schema_migrations SET checksum='changed'")
        connection.commit()
    with pytest.raises(MigrationChecksumError, match="checksum changed"):
        Repository(path)

    path = tmp_path / "lower.sqlite3"
    with connect(path) as connection:
        connection.executescript((MIGRATIONS_DIR / "0001_baseline.sql").read_text(encoding="utf-8"))
    with pytest.raises(SchemaVersionError, match="cv workspace upgrade"):
        Repository(path)
    assert current_schema_version(path) == "0001"
    assert apply_migrations(path) == HEAD_VERSION

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
    assert current_schema_version(empty) == HEAD_VERSION


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
        assert connection.execute("SELECT version FROM schema_migrations").fetchone()[0] == "0001"
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

    assert apply_migrations(adoptable) == HEAD_VERSION
    with connect(adoptable) as connection:
        columns = {
            row["name"]: row["notnull"]
            for row in connection.execute("PRAGMA table_info(job_snapshots)")
        }
    assert "original_text" not in columns
    assert columns["payload_path"] == 1
    assert columns["source_hash"] == 1
    assert columns["normalized_hash"] == 1

    fresh = tmp_path / "fresh-head.sqlite3"
    Repository(fresh)
    with connect(adoptable) as upgraded_connection, connect(fresh) as fresh_connection:
        assert sqlite_master_fingerprint(upgraded_connection) == sqlite_master_fingerprint(
            fresh_connection
        )
        revision_columns = {
            row["name"]: row["notnull"]
            for row in upgraded_connection.execute("PRAGMA table_info(approved_revisions)")
        }
        artifact_columns = {
            row["name"]: row["notnull"]
            for row in upgraded_connection.execute("PRAGMA table_info(artifact_versions)")
        }
    assert revision_columns["validation_run_id"] == 1
    assert revision_columns["resume_json_path"] == 1
    assert artifact_columns["revision_id"] == 0

    mismatch = tmp_path / "mismatch.sqlite3"
    with connect(mismatch) as connection:
        connection.executescript(sql)
        connection.execute("CREATE TABLE unexpected(id TEXT PRIMARY KEY)")
    with pytest.raises(SchemaFingerprintError, match="extra=.*unexpected"):
        Repository(mismatch)


def test_tracking_migration_preserves_legacy_status_and_submission_evidence(
    tmp_path: Path,
) -> None:
    path = tmp_path / "pre-tracking.sqlite3"
    # Named, not positional: this test is about 0006, and a later migration
    # being added must not silently change which one it exercises.
    tracking_migration = "0006_tracking_and_audit.sql"
    preceding = registered_migration_names()[: registered_migration_names().index(tracking_migration)]
    with connect(path) as connection:
        for name in preceding:
            connection.executescript((MIGRATIONS_DIR / name).read_text(encoding="utf-8"))
        connection.execute(
            "INSERT INTO applications(id, company, target_role, current_status, created_at, "
            "updated_at) VALUES('app', 'Co', 'Role', 'ready', '2026-01-01', '2026-01-03')"
        )
        connection.execute(
            "INSERT INTO job_snapshots(id, application_id, version_number, payload_path, "
            "source_hash, normalized_hash, captured_at, source_metadata_json, content_hash) "
            "VALUES('snapshot', 'app', 1, 'artifacts/snapshots/app/snapshot.txt', 'source', "
            "'normalized', '2026-01-01', '{}', 'source')"
        )
        for from_status, to_status, changed_at in (
            (None, "saved", "2026-01-01"),
            ("saved", "preparing", "2026-01-02"),
            ("preparing", "ready", "2026-01-03"),
        ):
            connection.execute(
                "INSERT INTO status_history(application_id, from_status, to_status, changed_at) "
                "VALUES('app', ?, ?, ?)",
                (from_status, to_status, changed_at),
            )
        connection.execute(
            "INSERT INTO artifacts(id, application_id, artifact_type, logical_name, created_at) "
            "VALUES('artifact', 'app', 'resume_pdf', 'legacy-resume', '2026-01-03')"
        )
        connection.execute(
            "INSERT INTO artifact_versions(id, artifact_id, version_number, lifecycle_status, "
            "path, content_hash, created_at, job_snapshot_id) VALUES('pdf', 'artifact', 1, "
            "'migrated-historical', 'legacy/resume.pdf', 'hash', '2026-01-03', 'snapshot')"
        )
        connection.execute(
            "INSERT INTO submissions(id, application_id, artifact_version_id, submitted_at) "
            "VALUES('submission', 'app', 'pdf', '2026-01-03')"
        )
        connection.executescript(
            (MIGRATIONS_DIR / tracking_migration).read_text(encoding="utf-8")
        )

        application = connection.execute(
            "SELECT current_status, terminal_outcome FROM applications WHERE id='app'"
        ).fetchone()
        events = connection.execute(
            "SELECT id, event_type, from_status, to_status, legacy_from_status, "
            "legacy_to_status FROM recruitment_events ORDER BY CAST(id AS INTEGER)"
        ).fetchall()
        submission = connection.execute(
            "SELECT id, submission_type, approved_revision_id, artifact_version_id FROM submissions"
        ).fetchone()
    assert tuple(application) == ("saved", None)
    assert [tuple(row) for row in events] == [
        ("1", "status_transition", None, "saved", None, None),
        ("2", "migration", "saved", "saved", "saved", "preparing"),
        ("3", "migration", "saved", "saved", "preparing", "ready"),
    ]
    assert tuple(submission) == ("submission", "external", None, "pdf")


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
    _create_application(repository, company="Writer", target_role="Developer", text="Python")
    started = threading.Event()
    release = threading.Event()
    results: list[str] = []

    def first_writer() -> None:
        with repository.unit_of_work() as uow:
            uow.connection.execute("UPDATE applications SET notes='first' WHERE company='Writer'")
            started.set()
            release.wait(timeout=2)
            uow.commit()

    def second_writer() -> None:
        started.wait(timeout=2)
        with repository.unit_of_work() as uow:
            uow.connection.execute("UPDATE applications SET notes='second' WHERE company='Writer'")
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


def test_knowledge_mutation_journal_has_one_guarded_terminal_transition(
    tmp_path: Path,
) -> None:
    repository = Repository(tmp_path / "knowledge-journal.sqlite3")
    request = PrepareKnowledgeMutation(
        mutation_id="mutation-1",
        mutation_type="promote_fact",
        source_reference="base/sales.md",
        staged_reference="temp/knowledge/mutation-1.json",
        old_sha256="a" * 64,
        new_sha256="b" * 64,
        db_mutation_type="fact_event",
        db_mutation_id="event-1",
        db_mutation={"fact_id": "fact-1", "to_status": "canonical"},
        recovery_strategy="finish_or_restore",
    )

    prepared = repository.prepare_knowledge_mutation(
        request, prepared_at="2026-08-19T10:00:00+00:00"
    )
    assert prepared.state is KnowledgeMutationState.PREPARED
    assert repository.prepared_knowledge_mutations() == [prepared]
    assert prepared.db_mutation == {"fact_id": "fact-1", "to_status": "canonical"}

    with repository.unit_of_work() as uow:
        committed = repository.bind(uow).commit_knowledge_mutation(
            prepared.id, committed_at="2026-08-19T10:01:00+00:00"
        )
        assert repository.bind(uow).knowledge_mutation(prepared.id) == committed
        uow.commit()

    assert committed.state is KnowledgeMutationState.COMMITTED
    assert repository.prepared_knowledge_mutations() == []
    with pytest.raises(ValueError, match="not prepared"):
        repository.commit_knowledge_mutation(prepared.id)
    with connect(repository.path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="invalid knowledge mutation transition"):
            connection.execute(
                "UPDATE knowledge_mutation_journal SET mutation_type='attach_fact' WHERE id=?",
                (prepared.id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="immutable record"):
            connection.execute(
                "DELETE FROM knowledge_mutation_journal WHERE id=?", (prepared.id,)
            )


def test_knowledge_mutation_quarantine_requires_reason_and_unique_db_identity(
    tmp_path: Path,
) -> None:
    repository = Repository(tmp_path / "knowledge-quarantine.sqlite3")
    request = PrepareKnowledgeMutation(
        mutation_id="mutation-1",
        mutation_type="attach_fact",
        source_reference="profiles/sales.json",
        staged_reference="temp/knowledge/mutation-1.json",
        old_sha256="a" * 64,
        new_sha256="b" * 64,
        db_mutation_type="fact_attachment",
        db_mutation_id="attachment-1",
        db_mutation={"fact_id": "fact-1"},
        recovery_strategy="finish_or_restore",
    )
    repository.prepare_knowledge_mutation(request)

    with pytest.raises(ValueError, match="requires a reason"):
        repository.quarantine_knowledge_mutation(request.mutation_id, " ")
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        repository.prepare_knowledge_mutation(
            PrepareKnowledgeMutation(
                **{
                    **request.__dict__,
                    "mutation_id": "mutation-2",
                    "staged_reference": "temp/knowledge/mutation-2.json",
                }
            )
        )

    quarantined = repository.quarantine_knowledge_mutation(
        request.mutation_id,
        "staged bytes no longer match",
        quarantined_at="2026-08-19T10:02:00+00:00",
    )
    assert quarantined.state is KnowledgeMutationState.QUARANTINED
    assert quarantined.quarantine_reason == "staged bytes no longer match"
    assert repository.quarantined_knowledge_mutations() == [quarantined]


def test_every_product_table_is_immutable_unless_explicitly_exempt(tmp_path: Path) -> None:
    """Completeness, not a roll-call.

    The previous version listed the immutable tables by hand, so a new immutable
    table was protected only if someone remembered to add it — and a forgotten
    trigger pair was indistinguishable from a table that did not exist. Here the
    tables are discovered and immutability is assumed, so the only way to be
    exempt is to say so in MUTABLE_TABLES.
    """
    repository = Repository(tmp_path / "immutability.sqlite3")
    with connect(repository.path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        triggers = {
            row[0]: " ".join((row[1] or "").split())
            for row in connection.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='trigger'"
            )
        }

    problems: list[str] = []
    for table in sorted(tables - MUTABLE_TABLES):
        for verb in ("update", "delete"):
            name = f"no_{verb}_{table}"
            if name not in triggers:
                problems.append(f"{table} is not exempt but has no {name} trigger")
            elif IMMUTABLE_ABORT not in triggers[name]:
                problems.append(f"{name} does not raise the immutable-record abort")

    for name in sorted(triggers):
        for verb, partner_verb in (("update", "delete"), ("delete", "update")):
            prefix = f"no_{verb}_"
            if not name.startswith(prefix):
                continue
            table = name[len(prefix) :]
            if f"no_{partner_verb}_{table}" not in triggers:
                problems.append(f"{name} has no counterpart no_{partner_verb}_{table}")
            if table in MUTABLE_TABLES:
                problems.append(f"{name} guards {table}, which is declared mutable")

    assert not problems, problems
    # A guard that cannot be observed failing is not evidence.
    assert tables - MUTABLE_TABLES


def test_immutability_triggers_refuse_real_repository_writes(tmp_path: Path) -> None:
    """Behavioural evidence over records the repository actually wrote.

    The structural test above proves every immutable table is guarded; this proves
    the guards bite, using rows created through the repository rather than a
    hand-maintained seeder that duplicated the schema's NOT NULLs and foreign keys.
    """
    repository = Repository(tmp_path / "refusals.sqlite3")
    repository.create_application(
        company="Immutable Co",
        target_role="Account Manager",
        payload_path="artifacts/snapshots/app/snapshot.txt",
        source_hash="s" * 64,
        normalized_hash="n" * 64,
    )
    application_id = repository.list_applications()[0]["id"]
    repository.insert_submission(
        "external-submission",
        application_id,
        "external",
        None,
        None,
        "2026-08-19T10:00:00+00:00",
        {},
    )
    repository.insert_audit(
        AuditRecord(
            id="audit-record",
            application_id=application_id,
            action="record_external_submission",
            entity_type="submission",
            entity_id="external-submission",
            actor_type="user",
            client="cli",
            installation_id="test-installation",
            occurred_at="2026-08-19T10:00:00+00:00",
        )
    )

    for table in ("job_snapshots", "recruitment_events", "submissions", "audit_records"):
        for statement in (f"UPDATE {table} SET rowid=rowid", f"DELETE FROM {table}"):
            with pytest.raises(sqlite3.IntegrityError, match="immutable record"):
                with repository.transaction() as connection:
                    connection.execute(statement)


def test_identity_and_typed_artifact_ports() -> None:
    values = [new_id() for _ in range(20)]
    assert len(set(values)) == len(values)
    assert all(uuid.UUID(value).version == 4 for value in values)

    for member in (
        "register_artifact_version",
        "insert_decision",
        "record_validation",
        "latest_artifact_version",
    ):
        parameters = inspect.signature(getattr(ArtifactRegistry, member)).parameters.values()
        assert all(
            parameter.kind not in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD)
            for parameter in parameters
        )


def test_analysis_does_not_change_recruitment_status(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "atomic-analysis.sqlite3")
    app_id, snapshot_id = _create_application(
        repository, company="Atomic", target_role="Developer", text="Python developer"
    )
    _save_analysis(repository, app_id, snapshot_id, classify_job("Python backend developer role"))

    with connect(repository.path) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM job_analyses WHERE application_id=?", (app_id,)
            ).fetchone()[0]
            == 1
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM selection_plans WHERE application_id=?", (app_id,)
            ).fetchone()[0]
            == 1
        )
        application = connection.execute(
            "SELECT current_status, language, track, profile, emphasis, fit_level "
            "FROM applications WHERE id=?",
            (app_id,),
        ).fetchone()
    assert application["current_status"] == "saved"
    assert all(application[field] is not None for field in tuple(application.keys())[1:])


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
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM working_drafts WHERE application_id='a'"
            ).fetchone()[0]
            == 2
        )
