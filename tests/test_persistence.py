from __future__ import annotations

import threading
import time

import pytest
from sqlalchemy import delete, func, insert, inspect, select, text, update
from sqlalchemy.exc import IntegrityError, ProgrammingError

from cv_engine.application.errors import PreconditionFailed, StateConflict, UnknownRecord
from cv_engine.application.knowledge_mutations import (
    KnowledgeMutationState,
    PrepareKnowledgeMutation,
)
from cv_engine.application.settings import UpdateSettings
from cv_engine.domain.analysis.classification import classify_job
from cv_engine.domain.models import (
    AuditRecord,
    SelectionManifest,
    SelectionPlan,
    ValidationReport,
    ValidationRunLineage,
    WorkingDraft,
)
from cv_engine.infrastructure.persistence import Repository
from cv_engine.infrastructure.persistence.tables import (
    app_settings,
    applications,
    job_snapshots,
    knowledge_mutation_journal,
    metadata,
    selection_plans,
    working_drafts,
)
from cv_engine.util import normalized_text, sha256_text

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
    }
)
DELETE_ONLY_TABLES = frozenset(
    {"operations", "operation_outputs", "idempotency_receipts", "knowledge_mutation_journal"}
)

IMMUTABLE_MESSAGE = "immutable record"


def _create_application(repository, *, company: str, target_role: str, text: str):
    digest = sha256_text(text)
    return repository.create_application(
        company=company,
        target_role=target_role,
        payload_path=f"artifacts/snapshots/{company}/snapshot.txt",
        source_hash=digest,
        normalized_hash=sha256_text(normalized_text(text)),
        client="web",
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


def test_app_settings_schema_rejects_non_singleton_and_invalid_values(
    application_repo,
) -> None:
    valid = {
        "singleton_id": 1,
        "edit_version": 1,
        "auto_generate_when_review_not_required": False,
        "ai_enabled_override": None,
        "default_execution_mode": "deterministic",
        "ui_density": "comfortable",
        "ui_text_size": "normal",
        "updated_at": "2026",
    }
    invalid_values = (
        {**valid, "singleton_id": 2},
        {**valid, "edit_version": 0},
        {**valid, "default_execution_mode": "automatic"},
        {**valid, "ui_density": "dense"},
        {**valid, "ui_text_size": "huge"},
    )
    for values in invalid_values:
        with pytest.raises(IntegrityError):
            with application_repo.transaction() as connection:
                connection.execute(insert(app_settings).values(**values))


def test_app_settings_default_read_is_pure(application_repo) -> None:
    assert application_repo.app_settings().model_dump(mode="python") == {
        "edit_version": 0,
        "auto_generate_when_review_not_required": False,
        "ai_enabled_override": None,
        "default_execution_mode": "deterministic",
        "ui_density": "comfortable",
        "ui_text_size": "normal",
        "updated_at": None,
    }
    with application_repo.read_connection() as connection:
        assert connection.execute(select(func.count()).select_from(app_settings)).scalar_one() == 0


def test_app_settings_updates_are_optimistic_and_atomic(application_repo, monkeypatch) -> None:
    first = application_repo.update_app_settings(
        0,
        UpdateSettings(
            auto_generate_when_review_not_required=True,
            ai_enabled_override=False,
            default_execution_mode="deterministic",
            ui_density="compact",
            ui_text_size="large",
        ),
    )
    assert first.edit_version == 1
    assert first.ui_density == "compact"

    with pytest.raises(StateConflict, match="changed from version 0 to 1"):
        application_repo.update_app_settings(
            0,
            UpdateSettings(
                auto_generate_when_review_not_required=False,
                ai_enabled_override=None,
                default_execution_mode="deterministic",
                ui_density="comfortable",
                ui_text_size="normal",
            ),
        )
    assert application_repo.app_settings() == first

    def refuse_post_commit_reread() -> None:
        raise AssertionError("an update response must describe its own committed write")

    monkeypatch.setattr(application_repo, "app_settings", refuse_post_commit_reread)
    second = application_repo.update_app_settings(
        1,
        UpdateSettings(
            auto_generate_when_review_not_required=False,
            ai_enabled_override=None,
            default_execution_mode="deterministic",
            ui_density="comfortable",
            ui_text_size="normal",
        ),
    )
    assert second.edit_version == 2
    assert Repository(application_repo.engine).app_settings() == second


def test_connection_policy_unit_of_work_bind_and_foreign_keys(application_repo) -> None:
    repository = application_repo
    with pytest.raises(IntegrityError, match="ForeignKeyViolation"):
        with repository.transaction() as connection:
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
    with pytest.raises(UnknownRecord):
        repository.get_application(rolled_back_id)


def test_concurrent_writers_do_not_silently_overwrite(application_repo) -> None:
    repository = application_repo
    _create_application(repository, company="Writer", target_role="Developer", text="Python")
    started = threading.Event()
    release = threading.Event()
    results: list[str] = []
    failures: list[Exception] = []

    def first_writer() -> None:
        with repository.unit_of_work() as uow:
            assert uow.connection is not None
            uow.connection.execute(
                update(applications).where(applications.c.company == "Writer").values(notes="first")
            )
            started.set()
            release.wait(timeout=2)
            uow.commit()

    def second_writer() -> None:
        started.wait(timeout=2)
        try:
            with repository.unit_of_work() as uow:
                assert uow.connection is not None
                uow.connection.execute(
                    update(applications)
                    .where(applications.c.company == "Writer")
                    .values(notes="second")
                )
                uow.commit()
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
    assert repository.list_applications()[0]["notes"] in {"first", "second"}


def test_knowledge_mutation_journal_has_one_guarded_terminal_transition(
    application_repo,
) -> None:
    repository = application_repo
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
    with pytest.raises(PreconditionFailed, match="not prepared"):
        repository.commit_knowledge_mutation(prepared.id)
    with pytest.raises(ProgrammingError, match="invalid knowledge mutation transition"):
        with repository.transaction() as connection:
            connection.execute(
                update(knowledge_mutation_journal)
                .where(knowledge_mutation_journal.c.id == prepared.id)
                .values(mutation_type="attach_fact")
            )
    with pytest.raises(ProgrammingError, match="immutable record"):
        with repository.transaction() as connection:
            connection.execute(
                delete(knowledge_mutation_journal).where(
                    knowledge_mutation_journal.c.id == prepared.id
                )
            )


def test_knowledge_mutation_quarantine_requires_reason_and_unique_db_identity(
    application_repo,
) -> None:
    repository = application_repo
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

    with pytest.raises(PreconditionFailed, match="requires a reason"):
        repository.quarantine_knowledge_mutation(request.mutation_id, " ")
    with pytest.raises(IntegrityError, match="uq_knowledge_mutation_journal"):
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


def test_every_product_table_is_immutable_unless_explicitly_exempt(application_repo) -> None:
    """Completeness, not a roll-call.

    The previous version listed the immutable tables by hand, so a new immutable
    table was protected only if someone remembered to add it — and a forgotten
    trigger pair was indistinguishable from a table that did not exist. Here the
    tables are discovered and immutability is assumed, so the only way to be
    exempt is to say so in MUTABLE_TABLES.
    """
    repository = application_repo
    tables = set(metadata.tables)
    with repository.read_connection() as connection:
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


def test_every_immutable_table_guard_calls_its_shared_reject_function(application_repo) -> None:
    """Derive both guard groups from the live catalog, including future tables."""
    with application_repo.read_connection() as connection:
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


def test_immutability_triggers_refuse_real_repository_writes(application_repo) -> None:
    """Behavioural evidence over records the repository actually wrote.

    The derived test above covers every immutable table, but with foreign keys
    and CHECK constraints suspended. This one keeps them on and uses rows the
    repository created, so the four tables it can reach cheaply are proven under
    the conditions production actually runs in.
    """
    repository = application_repo
    repository.create_application(
        company="Immutable Co",
        target_role="Account Manager",
        payload_path="artifacts/snapshots/app/snapshot.txt",
        source_hash="s" * 64,
        normalized_hash="n" * 64,
        client="web",
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
            client="web",
            occurred_at="2026-08-19T10:00:00+00:00",
        )
    )

    for table_name in ("job_snapshots", "recruitment_events", "submissions", "audit_records"):
        table = metadata.tables[table_name]
        for statement in (update(table).values(id=table.c.id), delete(table)):
            with pytest.raises(ProgrammingError, match="immutable record"):
                with repository.transaction() as connection:
                    connection.execute(statement)


def test_typed_preparation_records_round_trip_and_refuse_stale_edits(
    application_repo,
    draft_factory,
) -> None:
    repository = application_repo
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

    with pytest.raises(StateConflict, match="edit version mismatch"):
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
    application_repo,
    draft_factory,
) -> None:
    repository = application_repo
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

    with pytest.raises(ProgrammingError, match="immutable record"):
        with repository.transaction() as connection:
            connection.execute(
                update(selection_plans)
                .where(selection_plans.c.id == plan.id)
                .values(plan_json=selection_plans.c.plan_json)
            )
    with pytest.raises(ProgrammingError, match="immutable record"):
        with repository.transaction() as connection:
            connection.execute(delete(selection_plans).where(selection_plans.c.id == plan.id))
    with pytest.raises(IntegrityError, match="one_active_working_draft_per_application"):
        repository.create_working_draft(app_id, analysis_id, plan.id, document)


def test_only_one_working_draft_per_application_can_be_active(application_repo) -> None:
    """Product invariant 3, enforced by storage rather than by a filesystem path.

    Before this boundary "one active draft" was an accident of every draft living
    at `working/{application_id}/`, which a second writer would simply overwrite.
    The partial unique index is what makes the invariant real, so it is asserted
    through SQLAlchemy Core: a repository method could satisfy it by convention while the
    table underneath still allowed two.
    """
    repository = application_repo
    now = "2026-08-18T00:00:00+00:00"

    def insert_draft(connection, draft_id: str, *, active: bool) -> None:
        connection.execute(
            insert(working_drafts).values(
                id=draft_id,
                application_id="a",
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

    with repository.transaction() as connection:
        connection.execute(
            insert(applications).values(
                id="a",
                company="C",
                target_role="R",
                current_status="saved",
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(job_snapshots).values(
                id="s",
                application_id="a",
                version_number=1,
                payload_path="p",
                source_hash="h",
                normalized_hash="n",
                captured_at=now,
                source_metadata_json={},
                content_hash="h",
            )
        )
    analysis = classify_job("Python backend developer API React")
    analysis_id, plan = _save_analysis(repository, "a", "s", analysis)
    assert analysis_id == plan.job_analysis_id
    with repository.transaction() as connection:
        insert_draft(connection, "first", active=True)

    with pytest.raises(IntegrityError, match="one_active_working_draft_per_application"):
        with repository.transaction() as connection:
            insert_draft(connection, "second", active=True)

    with repository.transaction() as connection:
        connection.execute(
            update(working_drafts).where(working_drafts.c.id == "first").values(active=False)
        )
        insert_draft(connection, "third", active=True)
    with repository.read_connection() as connection:
        assert (
            connection.execute(
                select(func.count())
                .select_from(working_drafts)
                .where(working_drafts.c.application_id == "a")
            ).scalar_one()
            == 2
        )
