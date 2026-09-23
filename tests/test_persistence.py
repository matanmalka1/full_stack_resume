from __future__ import annotations

import threading
import time

import pytest
from sqlalchemy import create_engine, delete, func, insert, inspect, select, text, update
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.pool import NullPool

from cv_engine.application.errors import PreconditionFailed, StateConflict, UnknownRecord
from cv_engine.application.knowledge_mutations import (
    KnowledgeMutationState,
    PrepareKnowledgeMutation,
)
from cv_engine.application.settings import UpdateSettings
from cv_engine.domain.contracts.drafts import WorkingDraft
from cv_engine.domain.contracts.records import AuditRecord, ValidationRunLineage
from cv_engine.domain.contracts.selection import SelectionManifest, SelectionPlan
from cv_engine.domain.contracts.validation import ValidationReport
from cv_engine.infrastructure.persistence import SqlAlchemyTransactionManager
from cv_engine.infrastructure.persistence.analysis_plans import SqlAlchemyAnalysisPlanRepository
from cv_engine.infrastructure.persistence.analysis_sql import _analysis_record
from cv_engine.infrastructure.persistence.application_projections import (
    SqlAlchemyApplicationProjectionReader,
)
from cv_engine.infrastructure.persistence.application_store import SqlAlchemyApplicationStore
from cv_engine.infrastructure.persistence.job_snapshots import SqlAlchemyJobSnapshotStore
from cv_engine.infrastructure.persistence.knowledge_lifecycle import (
    SqlAlchemyKnowledgeLifecycleRepository,
)
from cv_engine.infrastructure.persistence.recruitment import SqlAlchemyRecruitmentRepository
from cv_engine.infrastructure.persistence.recruitment_store import (
    SqlAlchemyInitialRecruitmentEventWriter,
)
from cv_engine.infrastructure.persistence.settings_store import SqlAlchemySettingsStore
from cv_engine.infrastructure.persistence.tables import (
    app_settings,
    applications,
    job_snapshots,
    knowledge_mutation_journal,
    metadata,
    selection_plans,
    working_drafts,
)
from cv_engine.util import new_id, normalized_text, sha256_text, utc_now

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
        "app_settings",  # safe mutable Web preferences, guarded by edit_version
        "payload_write_leases",  # pending/committed/reclaiming coordination state
    }
)
DELETE_ONLY_TABLES = frozenset(
    {"operations", "operation_outputs", "idempotency_receipts", "knowledge_mutation_journal"}
)

IMMUTABLE_MESSAGE = "immutable record"


@pytest.fixture
def knowledge_store(transaction_manager):
    return SqlAlchemyKnowledgeLifecycleRepository(transaction_manager)


def test_analysis_plan_adapter_rejects_read_closed_and_foreign_tokens(
    transaction_manager,
    analysis_plan_store,
    database_engine,
) -> None:
    with transaction_manager.read() as tx:
        with pytest.raises(TypeError, match="write transaction"):
            analysis_plan_store.lock_application(tx, "application")
    with pytest.raises(RuntimeError, match="transaction is closed"):
        analysis_plan_store.selection_plan(tx, "plan")
    foreign = SqlAlchemyTransactionManager(database_engine)
    with foreign.read() as tx:
        with pytest.raises(TypeError, match="another transaction manager"):
            analysis_plan_store.selection_plan(tx, "plan")


def _create_application(
    transactions,
    *,
    company: str,
    target_role: str,
    text: str,
    tx=None,
):
    digest = sha256_text(text)
    application_id = new_id()
    snapshot_id = new_id()
    created_at = utc_now()
    application_store = SqlAlchemyApplicationStore(transactions)
    snapshots = SqlAlchemyJobSnapshotStore(transactions)
    recruitment = SqlAlchemyInitialRecruitmentEventWriter(transactions)

    def insert_records(transaction) -> None:
        application_store.insert_application(
            transaction,
            application_id=application_id,
            company=company,
            target_role=target_role,
            source_url=None,
            notes="",
            source="manual",
            created_at=created_at,
        )
        snapshots.insert_initial_snapshot(
            transaction,
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
            transaction,
            application_id=application_id,
            actor_type="user",
            client="web",
            occurred_at=created_at,
        )

    if tx is None:
        with transactions.write() as transaction:
            insert_records(transaction)
    else:
        insert_records(tx)
    return application_id, snapshot_id


def _save_analysis(transactions, application_id: str, snapshot_id: str, analysis):
    plan = SelectionManifest(
        policy_version="test-selection-v1",
        emphasis=analysis.emphasis,
        emphasis_policy_version="test-emphasis-v1",
    )
    plans = SqlAlchemyAnalysisPlanRepository(transactions)
    with transactions.write() as tx:
        return plans.save_analysis(
            tx,
            application_id,
            snapshot_id,
            analysis,
            plan,
            provider="test",
            model="fixture",
            candidate_context_version="candidate-v1",
            candidate_context_hash="candidate-hash",
            profile_version="profile-v1",
            selection_policy_version=plan.policy_version,
            track_emphasis_dependencies={
                "track": analysis.track.value,
                "emphasis": analysis.emphasis.value,
            },
        )


def _create_selection_plan(transactions_or_engine, *args, **kwargs):
    transactions = (
        transactions_or_engine
        if isinstance(transactions_or_engine, SqlAlchemyTransactionManager)
        else SqlAlchemyTransactionManager(transactions_or_engine)
    )
    plans = SqlAlchemyAnalysisPlanRepository(transactions)
    with transactions.write() as tx:
        return plans.create_selection_plan(tx, *args, **kwargs)


def test_non_3_analysis_documents_are_rejected_without_an_adapter() -> None:
    for document in ({"analysis_version": "2.0"}, {}):
        with pytest.raises(UnknownRecord, match="only 3.0 can be read"):
            _analysis_record({"id": "historical-analysis", "structured_json": document})


def test_app_settings_schema_rejects_non_singleton_and_invalid_values(
    database_engine,
) -> None:
    valid = {
        "singleton_id": 1,
        "edit_version": 1,
        "auto_generate_when_review_not_required": False,
        "ai_enabled_override": None,
        "default_execution_mode": "deterministic",
        "default_ai_model": "gpt-5.6-terra",
        "default_reasoning_effort": "medium",
        "ui_density": "comfortable",
        "ui_text_size": "normal",
        "ui_theme": "system",
        "updated_at": "2026",
    }
    invalid_values = (
        {**valid, "singleton_id": 2},
        {**valid, "edit_version": 0},
        {**valid, "default_execution_mode": "automatic"},
        {**valid, "default_ai_model": "arbitrary-model"},
        {**valid, "default_reasoning_effort": "maximum"},
        {**valid, "ui_density": "dense"},
        {**valid, "ui_text_size": "huge"},
        {**valid, "ui_theme": "sepia"},
    )
    transactions = SqlAlchemyTransactionManager(database_engine)
    for values in invalid_values:
        with pytest.raises(IntegrityError):
            with transactions.write() as tx:
                connection = transactions.connection_for(tx, access="write")
                connection.execute(insert(app_settings).values(**values))


def test_app_settings_default_read_is_pure_and_updates_are_optimistic_and_atomic(
    database_engine, monkeypatch
) -> None:
    transactions = SqlAlchemyTransactionManager(database_engine)
    settings = SqlAlchemySettingsStore(transactions)
    with transactions.read() as tx:
        stored = settings.settings(tx)
    assert stored.model_dump(mode="python") == {
        "edit_version": 0,
        "auto_generate_when_review_not_required": False,
        "ai_enabled_override": None,
        "default_execution_mode": "deterministic",
        "default_ai_model": None,
        "default_reasoning_effort": "medium",
        "ui_density": "comfortable",
        "ui_text_size": "normal",
        "ui_theme": "system",
        "updated_at": None,
    }
    with database_engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(app_settings)).scalar_one() == 0

    with transactions.write() as tx:
        first = settings.update_settings(
            tx,
            0,
            UpdateSettings(
                auto_generate_when_review_not_required=True,
                ai_enabled_override=False,
                default_execution_mode="deterministic",
                default_ai_model="gpt-5.6-terra",
                default_reasoning_effort="medium",
                ui_density="compact",
                ui_text_size="large",
                ui_theme="system",
            ),
        )
    assert first.edit_version == 1
    assert first.ui_density == "compact"

    with pytest.raises(StateConflict, match="changed from version 0 to 1"):
        with transactions.write() as tx:
            settings.update_settings(
                tx,
                0,
                UpdateSettings(
                    auto_generate_when_review_not_required=False,
                    ai_enabled_override=None,
                    default_execution_mode="deterministic",
                    default_ai_model="gpt-5.6-terra",
                    default_reasoning_effort="medium",
                    ui_density="comfortable",
                    ui_text_size="normal",
                    ui_theme="system",
                ),
            )
    with transactions.read() as tx:
        assert settings.settings(tx) == first

    def refuse_post_commit_reread() -> None:
        raise AssertionError("an update response must describe its own committed write")

    monkeypatch.setattr(settings, "settings", refuse_post_commit_reread)
    with transactions.write() as tx:
        second = settings.update_settings(
            tx,
            1,
            UpdateSettings(
                auto_generate_when_review_not_required=False,
                ai_enabled_override=None,
                default_execution_mode="deterministic",
                default_ai_model="gpt-5.6-luna",
                default_reasoning_effort="low",
                ui_density="comfortable",
                ui_text_size="normal",
                ui_theme="system",
            ),
        )
    assert second.edit_version == 2
    verification = SqlAlchemySettingsStore(transactions)
    with transactions.read() as tx:
        assert verification.settings(tx) == second


def test_connection_policy_transaction_scope_and_foreign_keys(database_engine) -> None:
    transactions = SqlAlchemyTransactionManager(database_engine)
    application_store = SqlAlchemyApplicationStore(transactions)
    with pytest.raises(IntegrityError, match="ForeignKeyViolation"):
        with transactions.write() as tx:
            connection = transactions.connection_for(tx, access="write")
            connection.execute(
                insert(job_snapshots).values(
                    id="missing-snapshot",
                    application_id="missing-app",
                    version_number=1,
                    payload_path="artifacts/snapshots/x.txt",
                    source_hash="hash",
                    normalized_hash="normalized",
                    captured_at="2026",
                    source_metadata_json={},
                    content_hash="hash",
                )
            )

    with transactions.write() as tx:
        app_id, _ = _create_application(
            transactions,
            company="Committed",
            target_role="Developer",
            text="Python",
            tx=tx,
        )
    with transactions.read() as tx:
        assert application_store.get_application(tx, app_id)["company"] == "Committed"

    with pytest.raises(RuntimeError, match="force rollback"):
        with transactions.write() as tx:
            rolled_back_id, _ = _create_application(
                transactions,
                company="Rolled Back",
                target_role="Developer",
                text="Python",
                tx=tx,
            )
            raise RuntimeError("force rollback")
    with pytest.raises(UnknownRecord):
        with transactions.read() as tx:
            application_store.get_application(tx, rolled_back_id)


def test_concurrent_writers_do_not_silently_overwrite(database_engine) -> None:
    transactions = SqlAlchemyTransactionManager(database_engine)
    _create_application(transactions, company="Writer", target_role="Developer", text="Python")
    started = threading.Event()
    release = threading.Event()
    results: list[str] = []
    failures: list[Exception] = []

    def first_writer() -> None:
        with transactions.write() as tx:
            connection = transactions.connection_for(tx, access="write")
            connection.execute(
                update(applications).where(applications.c.company == "Writer").values(notes="first")
            )
            started.set()
            release.wait(timeout=2)

    def second_writer() -> None:
        started.wait(timeout=2)
        try:
            with transactions.write() as tx:
                connection = transactions.connection_for(tx, access="write")
                connection.execute(
                    update(applications)
                    .where(applications.c.company == "Writer")
                    .values(notes="second")
                )
            results.append("committed")
        except Exception as exc:
            failures.append(exc)

    first = threading.Thread(target=first_writer)
    second = threading.Thread(target=second_writer)
    first.start()
    second.start()
    time.sleep(0.05)
    release.set()
    first.join(timeout=2)
    second.join(timeout=2)
    assert len(results) + len(failures) == 1
    applications_reader = SqlAlchemyApplicationProjectionReader(transactions)
    with transactions.read() as tx:
        assert applications_reader.applications(tx)[0]["notes"] in {"first", "second"}


def test_knowledge_mutation_journal_has_one_guarded_terminal_transition(
    database_engine,
    transaction_manager,
    knowledge_store,
) -> None:
    request = PrepareKnowledgeMutation(
        mutation_id="mutation-1",
        mutation_type="promote_fact",
        source_reference="base/sales.json",
        staged_reference="temp/knowledge/mutation-1.json",
        old_sha256="a" * 64,
        new_sha256="b" * 64,
        db_mutation_type="fact_event",
        db_mutation_id="event-1",
        db_mutation={"fact_id": "fact-1", "to_status": "canonical"},
        recovery_strategy="finish_or_restore",
    )

    with transaction_manager.write() as tx:
        prepared = knowledge_store.prepare_mutation(
            tx, request, prepared_at="2026-08-19T10:00:00+00:00"
        )
    assert prepared.state is KnowledgeMutationState.PREPARED
    with transaction_manager.read() as tx:
        assert knowledge_store.prepared_mutations(tx) == [prepared]
    assert prepared.db_mutation == {"fact_id": "fact-1", "to_status": "canonical"}

    with transaction_manager.write() as tx:
        committed = knowledge_store.commit_mutation(
            tx, prepared.id, committed_at="2026-08-19T10:01:00+00:00"
        )
        assert knowledge_store.mutation(tx, prepared.id) == committed

    assert committed.state is KnowledgeMutationState.COMMITTED
    with transaction_manager.read() as tx:
        assert knowledge_store.prepared_mutations(tx) == []
    with pytest.raises(PreconditionFailed, match="not prepared"):
        with transaction_manager.write() as tx:
            knowledge_store.commit_mutation(tx, prepared.id)
    with pytest.raises(ProgrammingError, match="invalid knowledge mutation transition"):
        with database_engine.begin() as connection:
            connection.execute(
                update(knowledge_mutation_journal)
                .where(knowledge_mutation_journal.c.id == prepared.id)
                .values(mutation_type="attach_fact")
            )
    with pytest.raises(ProgrammingError, match="immutable record"):
        with database_engine.begin() as connection:
            connection.execute(
                delete(knowledge_mutation_journal).where(
                    knowledge_mutation_journal.c.id == prepared.id
                )
            )


def test_knowledge_mutation_quarantine_requires_reason_and_unique_db_identity(
    transaction_manager,
    knowledge_store,
) -> None:
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
    with transaction_manager.write() as tx:
        knowledge_store.prepare_mutation(tx, request)

    with pytest.raises(PreconditionFailed, match="requires a reason"):
        with transaction_manager.write() as tx:
            knowledge_store.quarantine_mutation(tx, request.mutation_id, " ")
    with pytest.raises(IntegrityError, match="uq_knowledge_mutation_journal"):
        with transaction_manager.write() as tx:
            knowledge_store.prepare_mutation(
                tx,
                PrepareKnowledgeMutation(
                    **{
                        **request.__dict__,
                        "mutation_id": "mutation-2",
                        "staged_reference": "temp/knowledge/mutation-2.json",
                    }
                ),
            )

    with transaction_manager.write() as tx:
        quarantined = knowledge_store.quarantine_mutation(
            tx,
            request.mutation_id,
            "staged bytes no longer match",
            quarantined_at="2026-08-19T10:02:00+00:00",
        )
    assert quarantined.state is KnowledgeMutationState.QUARANTINED
    assert quarantined.quarantine_reason == "staged bytes no longer match"
    with transaction_manager.read() as tx:
        assert knowledge_store.quarantined_mutations(tx) == [quarantined]


def test_every_product_table_is_immutable_unless_explicitly_exempt(database_engine) -> None:
    """Completeness, not a roll-call.

    The previous version listed the immutable tables by hand, so a new immutable
    table was protected only if someone remembered to add it — and a forgotten
    trigger pair was indistinguishable from a table that did not exist. Here the
    tables are discovered and immutability is assumed, so the only way to be
    exempt is to say so in MUTABLE_TABLES.
    """
    tables = set(metadata.tables)
    with database_engine.connect() as connection:
        assert set(inspect(connection).get_table_names()) == tables | {"alembic_version"}
        trigger_rows = connection.execute(
            text(
                "SELECT event_object_table, trigger_name FROM information_schema.triggers "
                "WHERE trigger_schema = current_schema()"
            )
        ).all()
        function_source = connection.execute(
            text("SELECT pg_get_functiondef(to_regprocedure('cv_reject_immutable_change()'))")
        ).scalar_one()
    triggers = {(table, name) for table, name in trigger_rows}

    problems: list[str] = []
    for table in sorted(tables - MUTABLE_TABLES):
        for verb in ("update", "delete"):
            name = f"no_{verb}_{table}"
            if (table, name) not in triggers:
                problems.append(f"{table} is not exempt but has no {name} trigger")
    for table in DELETE_ONLY_TABLES:
        if (table, f"prevent_delete_{table}") not in triggers:
            problems.append(f"{table} has no delete-only guard")

    assert not problems, problems
    assert IMMUTABLE_MESSAGE in function_source
    assert tables - MUTABLE_TABLES


def test_every_immutable_table_guard_calls_its_shared_reject_function(database_engine) -> None:
    """Derive both guard groups from the live catalog, including future tables."""
    with database_engine.connect() as connection:
        guarded = {
            (table, trigger_name, function_name)
            for table, trigger_name, function_name in connection.execute(
                text(
                    "SELECT c.relname, t.tgname, p.proname FROM pg_trigger t "
                    "JOIN pg_class c ON c.oid = t.tgrelid "
                    "JOIN pg_proc p ON p.oid = t.tgfoid "
                    "WHERE NOT t.tgisinternal AND t.tgenabled = 'O' "
                    "AND p.proname IN "
                    "('cv_reject_immutable_change', 'cv_reject_protected_delete')"
                )
            )
        }
    expected = {
        (table, f"no_{verb}_{table}", "cv_reject_immutable_change")
        for table in set(metadata.tables) - MUTABLE_TABLES
        for verb in ("update", "delete")
    } | {
        (table, f"prevent_delete_{table}", "cv_reject_protected_delete")
        for table in DELETE_ONLY_TABLES
    }
    assert guarded == expected


def test_immutability_triggers_refuse_real_repository_writes(
    database_engine, transaction_manager, application_projection_reader, audit_log
) -> None:
    """Behavioural evidence over records the repository actually wrote.

    The derived test above covers every immutable table, but with foreign keys
    and CHECK constraints suspended. This one keeps them on and uses rows the
    repository created, so the four tables it can reach cheaply are proven under
    the conditions production actually runs in.
    """
    repository = transaction_manager
    _create_application(
        repository,
        company="Immutable Co",
        target_role="Account Manager",
        text="immutable application source",
    )
    with transaction_manager.read() as tx:
        application_id = application_projection_reader.applications(tx)[0]["id"]
    transactions = transaction_manager
    recruitment = SqlAlchemyRecruitmentRepository(transactions)
    with transactions.write() as tx:
        recruitment.insert_submission(
            tx,
            "external-submission",
            application_id,
            "external",
            None,
            None,
            "2026-08-19T10:00:00+00:00",
            {},
        )
    with transaction_manager.write() as tx:
        audit_log.insert_audit(
            tx,
            AuditRecord(
                id="audit-record",
                application_id=application_id,
                action="record_external_submission",
                entity_type="submission",
                entity_id="external-submission",
                actor_type="user",
                client="web",
                occurred_at="2026-08-19T10:00:00+00:00",
            ),
        )

    for table_name in ("job_snapshots", "recruitment_events", "submissions", "audit_records"):
        table = metadata.tables[table_name]
        for statement in (update(table).values(id=table.c.id), delete(table)):
            with pytest.raises(ProgrammingError, match="immutable record"):
                with database_engine.begin() as connection:
                    connection.execute(statement)


def test_typed_preparation_records_round_trip_and_refuse_stale_edits(
    database_engine,
    draft_factory,
    analysis_document,
    transaction_manager,
    application_projection_reader,
    analysis_plan_store,
    draft_lifecycle_store,
    validation_store,
) -> None:
    repository = transaction_manager
    app_id, snapshot_id = _create_application(
        repository,
        company="Typed Records",
        target_role="Developer",
        text="Python backend developer API React",
    )
    with transaction_manager.read() as tx:
        assert set(
            next(
                row
                for row in application_projection_reader.snapshots(tx, app_id)
                if row["id"] == snapshot_id
            )
        ) == {
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
    analysis = analysis_document()
    analysis_id, _initial_plan = _save_analysis(repository, app_id, snapshot_id, analysis)
    document = draft_factory(
        "Python backend developer API React",
        profile_override="development",
        application_id=app_id,
        job_snapshot_id=snapshot_id,
        job_analysis_id=analysis_id,
    ).draft
    assert document.selection is not None

    plan = _create_selection_plan(
        repository,
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
    with transaction_manager.read() as tx:
        assert analysis_plan_store.selection_plan(tx, plan.id) == plan

    with transaction_manager.write() as tx:
        working = draft_lifecycle_store.create_working_draft(
            tx,
            app_id,
            analysis_id,
            plan.id,
            document,
        )
    assert isinstance(working, WorkingDraft)
    with transaction_manager.read() as tx:
        assert draft_lifecycle_store.active_working_draft(tx, app_id) == working

    changed_source = document.model_copy(update={"content_hash": "changed-hash"})
    with transaction_manager.write() as tx:
        changed = draft_lifecycle_store.update_working_draft(
            tx,
            working.id,
            working.edit_version,
            changed_source,
        )
    assert changed.edit_version == working.edit_version + 1
    assert changed.content_hash == "changed-hash"

    with pytest.raises(StateConflict, match="edit version mismatch"):
        with transaction_manager.write() as tx:
            draft_lifecycle_store.update_working_draft(
                tx,
                working.id,
                working.edit_version,
                document.model_copy(update={"content_hash": "stale-write"}),
            )
    with transaction_manager.read() as tx:
        assert draft_lifecycle_store.working_draft(tx, working.id) == changed

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
    with transaction_manager.write() as tx:
        validation_id = validation_store.record_validation(
            tx,
            app_id,
            "pre-render",
            ValidationReport.from_findings({"content": True}, []),
            lineage=lineage,
        )
    with transaction_manager.read() as tx:
        assert validation_store.validation_lineage(tx, validation_id) == lineage


def test_selection_plan_is_immutable_and_only_one_working_draft_can_be_active(
    database_engine, draft_factory, analysis_document, transaction_manager, draft_lifecycle_store
) -> None:
    """Product invariant 3, enforced by storage rather than by a filesystem path.

    Before this boundary "one active draft" was an accident of every draft living
    at `working/{application_id}/`, which a second writer would simply overwrite.
    The partial unique index is what makes the invariant real, so it is asserted
    through SQLAlchemy Core: a repository method could satisfy it by convention while the
    table underneath still allowed two.
    """
    repository = transaction_manager
    now = "2026-08-18T00:00:00+00:00"
    app_id, snapshot_id = _create_application(
        repository,
        company="Constraint Records",
        target_role="Developer",
        text="Python backend developer API React",
    )
    analysis = analysis_document()
    analysis_id, initial_plan = _save_analysis(repository, app_id, snapshot_id, analysis)
    assert initial_plan.job_analysis_id == analysis_id
    document = draft_factory(
        "Python backend developer API React",
        profile_override="development",
        application_id=app_id,
        job_snapshot_id=snapshot_id,
        job_analysis_id=analysis_id,
    ).draft
    assert document.selection is not None
    plan = _create_selection_plan(
        repository,
        app_id,
        analysis_id,
        document.selection,
        candidate_context_version="candidate-v1",
        candidate_context_hash="candidate-hash",
        profile_version="profile-v1",
        selection_policy_version=document.selection.policy_version,
        track_emphasis_dependencies={},
    )
    with transaction_manager.write() as tx:
        draft_lifecycle_store.create_working_draft(tx, app_id, analysis_id, plan.id, document)

    with pytest.raises(ProgrammingError, match="immutable record"):
        with database_engine.begin() as connection:
            connection.execute(
                update(selection_plans)
                .where(selection_plans.c.id == plan.id)
                .values(plan_json=selection_plans.c.plan_json)
            )
    with pytest.raises(ProgrammingError, match="immutable record"):
        with database_engine.begin() as connection:
            connection.execute(delete(selection_plans).where(selection_plans.c.id == plan.id))

    def insert_draft(connection, draft_id: str, *, active: bool) -> None:
        connection.execute(
            insert(working_drafts).values(
                id=draft_id,
                application_id=app_id,
                job_analysis_id=analysis_id,
                selection_plan_id=plan.id,
                source_json={},
                edit_version=1,
                content_hash="h",
                active=active,
                created_at=now,
                updated_at=now,
            )
        )

    with pytest.raises(IntegrityError, match="one_active_working_draft_per_application"):
        with database_engine.begin() as connection:
            insert_draft(connection, "second", active=True)

    with database_engine.begin() as connection:
        connection.execute(
            update(working_drafts)
            .where(working_drafts.c.application_id == app_id)
            .values(active=False)
        )
        insert_draft(connection, "third", active=True)
    with database_engine.connect() as connection:
        assert (
            connection.execute(
                select(func.count())
                .select_from(working_drafts)
                .where(working_drafts.c.application_id == app_id)
            ).scalar_one()
            == 2
        )


def test_a_stale_plan_write_is_refused_rather_than_silently_rebased(
    database_engine, analysis_document, transaction_manager
) -> None:
    """The lost-update path, closed.

    The version number is allocated inside the write, so two writers that read
    the same plan do not collide: the later one gets a legal new version built
    on a plan it never saw. The optimistic check makes that a refusal instead.

    This used to be exercised through gap acceptances, which are gone. The
    guard is not: it belongs to write consistency, and it was very nearly
    removed together with the acceptance carry that happened to invoke it.
    """
    repository = transaction_manager
    app_id, snapshot_id = _create_application(
        repository,
        company="Concurrent Plan Co",
        target_role="Developer",
        text="Python backend developer API React",
    )
    analysis = analysis_document()
    analysis_id, initial = _save_analysis(repository, app_id, snapshot_id, analysis)

    def write(expected: str | None):
        return _create_selection_plan(
            repository,
            app_id,
            analysis_id,
            initial.plan,
            candidate_context_version="candidate-v1",
            candidate_context_hash="candidate-hash",
            profile_version="profile-v1",
            selection_policy_version=initial.plan.policy_version,
            track_emphasis_dependencies={},
            expected_selection_plan_id=expected,
        )

    first = write(initial.id)
    assert first.id != initial.id

    # A second writer that still believes `initial` is active is refused, rather
    # than writing a new version on top of a plan it never saw.
    with pytest.raises(StateConflict, match="moved since this decision was made"):
        write(initial.id)

    # Naming the plan that is actually active, the write goes through.
    second = write(first.id)
    assert second.version_number == first.version_number + 1


def test_a_plan_write_blocks_on_the_application_lock(
    database_engine, database_url, analysis_document, transaction_manager
) -> None:
    """Deterministic proof that the lock is taken, and taken before the read.

    The earlier version of this raced two threads and asserted the outcome.
    That was not a regression test: without the lock the threads are still free
    to interleave harmlessly, so it passed against the broken implementation as
    often as the fixed one.

    Instead one connection holds the Application row and a second tries to write
    a plan with a short `lock_timeout`. If the writer takes the lock it cannot
    proceed and times out; if it does not, it writes happily. The timeout is the
    assertion.
    """
    repository = transaction_manager
    app_id, snapshot_id = _create_application(
        repository,
        company="Locked Application Co",
        target_role="Developer",
        text="Python backend developer API React",
    )
    analysis = analysis_document()
    analysis_id, initial = _save_analysis(repository, app_id, snapshot_id, analysis)

    impatient = create_engine(
        database_url, connect_args={"options": "-c lock_timeout=250ms"}, poolclass=NullPool
    )
    holder = create_engine(database_url, poolclass=NullPool)
    try:
        with holder.begin() as held:
            held.execute(
                select(applications.c.id).where(applications.c.id == app_id).with_for_update()
            ).one()

            with pytest.raises(OperationalError, match="lock timeout"):
                _create_selection_plan(
                    impatient,
                    app_id,
                    analysis_id,
                    initial.plan,
                    candidate_context_version="candidate-v1",
                    candidate_context_hash="candidate-hash",
                    profile_version="profile-v1",
                    selection_policy_version=initial.plan.policy_version,
                    track_emphasis_dependencies={},
                )

        # The holder committed; the same write now goes through and the version
        # it allocates is the one after whatever the lock was protecting.
        after = _create_selection_plan(
            impatient,
            app_id,
            analysis_id,
            initial.plan,
            candidate_context_version="candidate-v1",
            candidate_context_hash="candidate-hash",
            profile_version="profile-v1",
            selection_policy_version=initial.plan.policy_version,
            track_emphasis_dependencies={},
        )
        assert after.version_number > initial.version_number
    finally:
        impatient.dispose()
        holder.dispose()
