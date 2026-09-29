from __future__ import annotations

import threading
import time

import pytest
from helpers import seed_document, stored_document
from pydantic import ValidationError
from sqlalchemy import create_engine, delete, func, insert, inspect, select, text, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.pool import NullPool

from cv_engine.application.commands import IngestCommand
from cv_engine.application.errors import PreconditionFailed, StateConflict, UnknownRecord
from cv_engine.application.knowledge_mutations import (
    KnowledgeMutationState,
    PrepareKnowledgeMutation,
)
from cv_engine.application.ports.documents import DocumentBody
from cv_engine.application.settings import UpdateSettings
from cv_engine.domain.contracts.document import DocumentSubmission
from cv_engine.domain.contracts.records import AuditRecord
from cv_engine.domain.contracts.recruitment import ApplicationStatus
from cv_engine.infrastructure.persistence import SqlAlchemyTransactionManager
from cv_engine.infrastructure.persistence.analysis_sql import _analysis_record
from cv_engine.infrastructure.persistence.application_projections import (
    SqlAlchemyApplicationProjectionReader,
)
from cv_engine.infrastructure.persistence.application_store import SqlAlchemyApplicationStore
from cv_engine.infrastructure.persistence.documents import (
    SqlAlchemyDocumentStore,
    SqlAlchemyDocumentSubmissionStore,
)
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
    cv_documents,
    job_snapshots,
    knowledge_mutation_journal,
    metadata,
    submissions,
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
        "cv_documents",  # the one mutable resume document (product invariant 3)
        "operations",  # mutable only until a terminal status; terminal rows have a trigger
        "operation_resource_leases",  # ephemeral claim coordination
        "operation_outputs",  # permits exactly one inactive-to-active transition
        "knowledge_mutation_journal",  # permits one prepared-to-terminal transition
        "app_settings",  # safe mutable Web preferences, guarded by edit_version
    }
)
DELETE_ONLY_TABLES = frozenset({"operations", "operation_outputs", "knowledge_mutation_journal"})

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
        analysis_plan_store.lock_application(tx, "application")
    foreign = SqlAlchemyTransactionManager(database_engine)
    with foreign.write() as tx:
        with pytest.raises(TypeError, match="another transaction manager"):
            analysis_plan_store.lock_application(tx, "application")


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
            notes="",
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
        "updated_at": "2026-01-01T00:00:00+00:00",
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


def test_constraint_matrix_refuses_what_the_schema_forbids(database_engine) -> None:
    """Every CHECK and uniqueness rule the recruitment trail depends on, over real rows.

    `ready` and `preparing` are workflow projections, never stored statuses; the
    removed `cli` client is refused by the command and record contracts and by the
    event CHECK; and an internal submission must carry the document and both
    immutable file copies. Repeated external submissions carry no invented
    document or artifact references.
    """
    for status in ("preparing", "ready"):
        with pytest.raises(ValueError):
            ApplicationStatus(status)
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

    transactions = SqlAlchemyTransactionManager(database_engine)
    app_id, snapshot_id = _create_application(
        transactions, company="Constraint Matrix", target_role="Developer", text="Python role"
    )
    recruitment = SqlAlchemyRecruitmentRepository(transactions)
    submission_store = SqlAlchemyDocumentSubmissionStore(transactions)

    def current_status_ready(tx) -> None:
        transactions.connection_for(tx, access="write").execute(
            update(applications).where(applications.c.id == app_id).values(current_status="ready")
        )

    def cli_client_event(tx) -> None:
        recruitment.insert_next_action(
            tx,
            application_id=app_id,
            next_action="Follow up",
            next_action_date="2026-09-01",
            actor_type="user",
            client="cli",
            occurred_at="2026-08-30T12:00:00+00:00",
        )

    def internal_without_content(tx):
        transactions.connection_for(tx, access="write").execute(
            insert(submissions).values(
                id=new_id(),
                application_id=app_id,
                submission_type="internal",
                submitted_at=utc_now(),
                metadata_json={},
            )
        )

    for write, constraint in (
        (current_status_ready, "ck_applications_current_status"),
        (cli_client_event, "ck_recruitment_events_client"),
        (internal_without_content, None),
    ):
        with pytest.raises(IntegrityError, match=constraint):
            with transactions.write() as tx:
                write(tx)
    for _ in range(2):
        with transactions.write() as tx:
            submission_store.insert_submission(
                tx,
                DocumentSubmission(
                    id=new_id(),
                    application_id=app_id,
                    submission_type="external",
                    submitted_at=utc_now(),
                ),
            )
    with transactions.read() as tx:
        assert len(submission_store.submissions(tx, app_id)) == 2
        assert (
            SqlAlchemyApplicationStore(transactions).get_application(tx, app_id)["current_status"]
            == "saved"
        )


def test_connection_policy_transaction_scope_and_foreign_keys(database_engine) -> None:
    transactions = SqlAlchemyTransactionManager(database_engine)
    application_store = SqlAlchemyApplicationStore(transactions)
    with pytest.raises(IntegrityError, match="ForeignKeyViolation"):
        with transactions.write() as tx:
            connection = transactions.connection_for(tx, access="write")
            connection.execute(
                insert(job_snapshots).values(
                    id=new_id(),
                    application_id=new_id(),
                    version_number=1,
                    payload_path="artifacts/snapshots/x.txt",
                    source_hash="hash",
                    normalized_hash="normalized",
                    captured_at="2026-01-01T00:00:00+00:00",
                    source_metadata_json={},
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
    mutation_id = new_id()
    request = PrepareKnowledgeMutation(
        mutation_id=mutation_id,
        mutation_type="fact_confirmed",
        source_reference="base/sales.json",
        staged_reference=f"temp/knowledge/{mutation_id}.json",
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
    mutation_id = new_id()
    request = PrepareKnowledgeMutation(
        mutation_id=mutation_id,
        mutation_type="attach_fact",
        source_reference="profiles/sales.json",
        staged_reference=f"temp/knowledge/{mutation_id}.json",
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
                        "mutation_id": new_id(),
                        "staged_reference": f"temp/knowledge/{new_id()}.json",
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
    external_submission_id = new_id()
    with transactions.write() as tx:
        SqlAlchemyDocumentSubmissionStore(transactions).insert_submission(
            tx,
            DocumentSubmission(
                id=external_submission_id,
                application_id=application_id,
                submission_type="external",
                submitted_at="2026-08-19T10:00:00+00:00",
            ),
        )
    with transaction_manager.write() as tx:
        audit_log.insert_audit(
            tx,
            AuditRecord(
                id=new_id(),
                application_id=application_id,
                action="record_external_submission",
                entity_type="submission",
                entity_id=external_submission_id,
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


def test_one_document_per_application_is_enforced_by_the_database(services, database_engine):
    ingested, _ = seed_document(services, "One Document")
    with database_engine.connect() as connection:
        row = dict(
            connection.execute(
                select(cv_documents).where(cv_documents.c.application_id == ingested.application_id)
            )
            .mappings()
            .one()
        )
    row["id"] = new_id()
    with pytest.raises(IntegrityError):
        with database_engine.begin() as connection:
            connection.execute(insert(cv_documents).values(row))


def test_document_write_blocks_on_its_row_lock(services, database_url):
    ingested, _ = seed_document(services, "Locked Document")
    document = stored_document(services, ingested.application_id)
    impatient = create_engine(
        database_url, connect_args={"options": "-c lock_timeout=250ms"}, poolclass=NullPool
    )
    holder = create_engine(database_url, poolclass=NullPool)
    transactions = SqlAlchemyTransactionManager(impatient)
    store = SqlAlchemyDocumentStore(transactions)
    body = DocumentBody(
        analysis_id=document.analysis_id, selection=document.selection, content=None
    )
    try:
        with holder.begin() as held:
            held.execute(
                select(cv_documents.c.id).where(cv_documents.c.id == document.id).with_for_update()
            ).one()
            with pytest.raises(OperationalError, match="lock timeout"):
                with transactions.write() as tx:
                    store.update_body(
                        tx,
                        ingested.application_id,
                        document.document_hash,
                        body,
                        updated_at=utc_now(),
                    )
        with transactions.write() as tx:
            assert (
                store.update_body(
                    tx, ingested.application_id, document.document_hash, body, updated_at=utc_now()
                ).document_hash
                == document.document_hash
            )
    finally:
        impatient.dispose()
        holder.dispose()


def test_nullable_document_json_columns_bind_none_as_sql_null():
    """JSON null is a value; optional document fields must satisfy SQL IS NULL guards."""
    columns = [
        column
        for table in (metadata.tables["cv_documents"], metadata.tables["submissions"])
        for column in table.columns
        if column.nullable and isinstance(column.type, JSONB)
    ]
    assert columns
    for column in columns:
        assert isinstance(column.type, JSONB)
        assert column.type.none_as_null, str(column)
