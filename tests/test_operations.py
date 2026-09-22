from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock, Thread

import pytest
from foreground import ForegroundOperationExecutor, foreground_executor
from helpers import (
    ACCOUNT_MANAGER_JOB,
    analysis_proposal,
    artifact_path,
    seed_analysis_for_command,
    validate_active_draft,
)
from pydantic import ValidationError
from sqlalchemy import delete, select, update
from sqlalchemy.exc import ProgrammingError

from cv_engine.application.commands import (
    AnalyzeCommand,
    ApproveDraftCommand,
    CreateSelectionPlanCommand,
    DraftCommand,
    IngestCommand,
    RenderCommand,
)
from cv_engine.application.errors import (
    IDEMPOTENCY_KEY_REUSED,
    InfrastructureFailure,
    MissingFactRendering,
    StateConflict,
    UnknownRecord,
)
from cv_engine.application.operation_runner import (
    OperationExecutionError,
    OperationRunner,
    PreparedOperation,
    SourceChanged,
)
from cv_engine.application.operations import (
    CreateOperation,
    OperationAction,
    OperationContractError,
    OperationFailureCode,
    OperationOutputReference,
    OperationPhase,
    OperationSources,
    OperationStatus,
    OperationType,
    allows_automatic_retry,
    as_operation_view,
    available_operation_actions,
    is_terminal_operation,
    require_operation_transition,
)
from cv_engine.domain.contracts.validation import ValidationIssue, ValidationReport
from cv_engine.infrastructure.operation_logging import OperationFailureLogger
from cv_engine.infrastructure.payloads import PayloadStore
from cv_engine.infrastructure.persistence.application_projections import (
    SqlAlchemyApplicationProjectionReader,
)
from cv_engine.infrastructure.persistence.artifact_catalog import SqlAlchemyArtifactCatalog
from cv_engine.infrastructure.persistence.connection import SqlAlchemyTransactionManager
from cv_engine.infrastructure.persistence.draft_lifecycle import SqlAlchemyDraftLifecycleRepository
from cv_engine.infrastructure.persistence.operation_execution import (
    SqlAlchemyOperationExecutionStore,
)
from cv_engine.infrastructure.persistence.render_context import SqlAlchemyRenderContextReader
from cv_engine.infrastructure.persistence.tables import (
    OPERATION_FAILURE_CODES,
    operation_resource_leases,
    operations,
)
from cv_engine.infrastructure.persistence.validation_store import SqlAlchemyValidationRepository
from cv_engine.runtime.execution import OperationWorker
from cv_engine.util import new_id


def _active_operation(services, *args):
    transactions = services.operation_runner.transactions
    with transactions.read() as tx:
        return SqlAlchemyApplicationProjectionReader(transactions).active_operation(tx, *args)


def _active_working_draft(services, *args):
    transactions = services.operation_runner.transactions
    with transactions.read() as tx:
        return SqlAlchemyDraftLifecycleRepository(transactions).active_working_draft(tx, *args)


def _working_draft(services, *args):
    transactions = services.operation_runner.transactions
    with transactions.read() as tx:
        return SqlAlchemyDraftLifecycleRepository(transactions).working_draft(tx, *args)


def _approved_revision(services, *args):
    transactions = services.operation_runner.transactions
    with transactions.read() as tx:
        return SqlAlchemyDraftLifecycleRepository(transactions).approved_revision(tx, *args)


def _approved_revisions(services, *args):
    transactions = services.operation_runner.transactions
    with transactions.read() as tx:
        return SqlAlchemyDraftLifecycleRepository(transactions).approved_revisions(tx, *args)


def _latest_validation_for_working_draft(services, *args):
    transactions = services.operation_runner.transactions
    with transactions.read() as tx:
        return SqlAlchemyValidationRepository(transactions).latest_validation_for_working_draft(
            tx, *args
        )


def _artifact_version(services, *args):
    transactions = services.operation_runner.transactions
    with transactions.read() as tx:
        return SqlAlchemyArtifactCatalog(transactions).artifact_version(tx, *args)


def _artifact_versions(services, *args):
    transactions = services.operation_runner.transactions
    with transactions.read() as tx:
        return SqlAlchemyArtifactCatalog(transactions).artifact_versions(tx, *args)


def _artifact_version_for_revision(services, *args):
    transactions = services.operation_runner.transactions
    with transactions.read() as tx:
        return SqlAlchemyArtifactCatalog(transactions).artifact_version_for_revision(tx, *args)


def _latest_artifact_version(services, *args):
    transactions = services.operation_runner.transactions
    with transactions.read() as tx:
        return SqlAlchemyArtifactCatalog(transactions).latest_artifact_version(tx, *args)


def _runner(services, handlers, **options) -> OperationRunner:
    return OperationRunner(
        handlers,
        transactions=services.operation_runner.transactions,
        execution_store=services.operation_runner.execution_store,
        **options,
    )


def _enqueue_operation(services, request, *, operation_id=None, created_at=None):
    with services.operation_runner.transactions.write() as tx:
        return services.operation_submissions.operations.enqueue(
            tx,
            request,
            operation_id=operation_id or new_id(),
            created_at=created_at,
        )


def _operation(services, operation_id):
    return services.operation_runner.operation(operation_id)


def _claim_operation(services, operation_id, **options):
    with services.operation_runner.transactions.write() as tx:
        return services.operation_runner.execution_store.claim_operation(
            tx, operation_id, **options
        )


def _claim_next_operation(services, **options):
    with services.operation_runner.transactions.write() as tx:
        return services.operation_runner.execution_store.claim_next_operation(tx, **options)


def _execution_write(services, method, *args, **options):
    with services.operation_runner.transactions.write() as tx:
        return getattr(services.operation_runner.execution_store, method)(tx, *args, **options)


def _claim_receipt(services, *args, **options):
    with services.draft_approval.transactions.write() as tx:
        return services.draft_approval.receipts.claim_idempotency_receipt(tx, *args, **options)


def _read_receipt(services, command_type, idempotency_key):
    with services.draft_approval.transactions.read() as tx:
        return services.draft_approval.receipts.idempotency_receipt(
            tx, command_type, idempotency_key
        )


def _complete_receipt(services, receipt_id, result):
    with services.draft_approval.transactions.write() as tx:
        return services.draft_approval.receipts.complete_idempotency_receipt(tx, receipt_id, result)


def test_operation_lifecycle_accepts_only_forward_transitions() -> None:
    transitions = [
        (OperationStatus.QUEUED, OperationStatus.RUNNING),
        (OperationStatus.QUEUED, OperationStatus.CANCELLED),
        (OperationStatus.QUEUED, OperationStatus.INTERRUPTED),
        (OperationStatus.RUNNING, OperationStatus.SUCCEEDED),
        (OperationStatus.RUNNING, OperationStatus.FAILED),
        (OperationStatus.RUNNING, OperationStatus.CANCELLED),
        (OperationStatus.RUNNING, OperationStatus.INTERRUPTED),
    ]
    for current, target in transitions:
        require_operation_transition(current, target)


def test_terminal_operations_are_immutable() -> None:
    for terminal in list(OperationStatus)[2:]:
        assert is_terminal_operation(terminal)
        for target in OperationStatus:
            with pytest.raises(OperationContractError):
                require_operation_transition(terminal, target)


_OPERATION_ACTION_CASES = [
    (OperationStatus.QUEUED, None, None, (OperationAction.CANCEL,)),
    (OperationStatus.RUNNING, None, None, (OperationAction.CANCEL,)),
    (OperationStatus.RUNNING, "2026-08-24T07:01:00Z", None, ()),
    (OperationStatus.FAILED, None, None, (OperationAction.RETRY,)),
    (OperationStatus.SUCCEEDED, None, None, (OperationAction.RETRY,)),
    (OperationStatus.CANCELLED, None, None, (OperationAction.RETRY,)),
    (OperationStatus.INTERRUPTED, None, None, (OperationAction.RETRY,)),
]


def test_operation_actions_are_derived_by_the_lifecycle() -> None:
    assert {case[0] for case in _OPERATION_ACTION_CASES} == set(OperationStatus)
    for status, cancellation_requested_at, failure_code, expected in _OPERATION_ACTION_CASES:
        assert (
            available_operation_actions(status, cancellation_requested_at, failure_code) == expected
        ), status
    assert (
        available_operation_actions(
            OperationStatus.FAILED,
            None,
            OperationFailureCode.MISSING_FACT_RENDERING,
        )
        == ()
    )
    assert (
        available_operation_actions(
            OperationStatus.FAILED,
            None,
            OperationFailureCode.SOURCE_CHANGED,
        )
        == ()
    )


def test_operation_payload_hash_is_canonical_and_secret_fields_are_refused() -> None:
    common = {
        "application_id": "application-id",
        "operation_type": OperationType.ANALYZE_JOB,
        "idempotency_key": "request-1",
        "sources": OperationSources(
            job_snapshot_id="snapshot-id",
            job_snapshot_hash="a" * 64,
        ),
    }
    first = CreateOperation(payload={"mode": "ai", "options": {"b": 2, "a": 1}}, **common)
    second = CreateOperation(payload={"options": {"a": 1, "b": 2}, "mode": "ai"}, **common)
    assert first.payload_hash == second.payload_hash

    with pytest.raises(ValidationError, match=r"payload\.provider\.api-key"):
        CreateOperation(payload={"provider": {"api-key": "must-not-persist"}}, **common)


def test_only_one_automatic_retry_is_allowed_for_transient_failures() -> None:
    assert tuple(code.value for code in OperationFailureCode) == OPERATION_FAILURE_CODES
    transient_codes = [
        OperationFailureCode.PROVIDER_TIMEOUT,
        OperationFailureCode.PROVIDER_RATE_LIMITED,
        OperationFailureCode.PROVIDER_UNAVAILABLE,
        OperationFailureCode.BROWSER_START_FAILED,
    ]
    for code in transient_codes:
        assert allows_automatic_retry(code, attempts_completed=1), code
        assert not allows_automatic_retry(code, attempts_completed=2), code
        assert not allows_automatic_retry(OperationFailureCode.INVALID_OUTPUT, 1)

        with pytest.raises(OperationContractError):
            allows_automatic_retry(code, attempts_completed=0)


def _stored_request(application_id: str, key: str = "request-1") -> CreateOperation:
    return CreateOperation(
        application_id=application_id,
        operation_type=OperationType.ANALYZE_JOB,
        payload={"job_snapshot_id": "snapshot-id", "provider": "openai"},
        idempotency_key=key,
        sources=OperationSources(
            job_snapshot_id="snapshot-id",
            job_snapshot_hash="a" * 64,
        ),
        provider="openai",
        model="gpt-5.6-terra",
    )


def test_operation_creation_is_idempotent_and_projects_active_work(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="Operation Co", target_role="Developer", job_text="Python role", client="web"
        )
    )
    request = _stored_request(ingested.application_id)

    created = _enqueue_operation(
        services,
        request,
        operation_id="operation-id",
        created_at="2026-08-19T08:00:00+00:00",
    )
    repeated = _enqueue_operation(
        services,
        request,
        operation_id="ignored-id",
    )

    assert repeated == created
    assert created.payload_hash == request.payload_hash
    assert created.status is OperationStatus.QUEUED
    assert _operation(services, created.id) == created
    assert _active_operation(services, ingested.application_id).id == created.id
    detail = services.queries.application_detail(ingested.application_id)
    assert detail.active_operation == as_operation_view(created)
    assert detail.latest_operation == as_operation_view(created)
    assert detail.active_operation.status is OperationStatus.QUEUED

    _claim_operation(
        services,
        created.id,
        runner_id="runner",
        now="2026-08-19T08:01:00+00:00",
    )
    failed = _execution_write(
        services,
        "fail_operation",
        created.id,
        OperationFailureCode.PROVIDER_UNAVAILABLE,
        "provider unavailable",
        runner_id="runner",
        now="2026-08-19T08:02:00+00:00",
    )
    after_failure = services.queries.application_detail(ingested.application_id)
    assert after_failure.active_operation is None
    assert after_failure.latest_operation == as_operation_view(failed)


def test_operation_rejects_idempotency_key_with_another_payload(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="Conflict Co", target_role="Developer", job_text="Python role", client="web"
        )
    )
    request = _stored_request(ingested.application_id)
    _enqueue_operation(
        services,
        request,
    )
    conflicting = request.model_copy(update={"payload": {"mode": "ai"}})

    # Assert the contracted code rather than the prose: the code is what a client
    # switches on, and the message is free to be rewritten for a human.
    with pytest.raises(StateConflict) as raised:
        _enqueue_operation(
            services,
            conflicting,
        )
    assert raised.value.code == IDEMPOTENCY_KEY_REUSED


def test_terminal_operation_rows_cannot_be_rewritten_or_deleted(services, database_engine) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="Immutable Op Co", target_role="Developer", job_text="Python role", client="web"
        )
    )
    created = _enqueue_operation(
        services,
        _stored_request(ingested.application_id),
    )
    with database_engine.begin() as connection:
        connection.execute(
            update(operations)
            .where(operations.c.id == created.id)
            .values(
                status="cancelled",
                phase="completed",
                finished_at="2026-08-19T08:01:00+00:00",
            )
        )

    with pytest.raises(ProgrammingError, match="immutable terminal operation"):
        with database_engine.begin() as connection:
            connection.execute(
                update(operations).where(operations.c.id == created.id).values(message="rewritten")
            )
    with pytest.raises(ProgrammingError, match="immutable record"):
        with database_engine.begin() as connection:
            connection.execute(delete(operations).where(operations.c.id == created.id))


def test_two_runners_racing_one_operation_produce_one_claim(services, database_engine) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="Claim Race Co", target_role="Developer", job_text="Python role", client="web"
        )
    )
    created = _enqueue_operation(
        services,
        _stored_request(ingested.application_id),
    )
    barrier = Barrier(2)

    def claim(runner_id: str):
        transactions = SqlAlchemyTransactionManager(database_engine)
        execution = SqlAlchemyOperationExecutionStore(transactions)
        barrier.wait(timeout=2)
        with transactions.write() as tx:
            return execution.claim_operation(
                tx,
                created.id,
                runner_id=runner_id,
                now="2026-08-19T08:00:00+00:00",
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ("runner-a", "runner-b")))

    claimed = [result for result in results if result is not None]
    assert len(claimed) == 1
    winner = claimed[0]
    assert winner.lease_owner in {"runner-a", "runner-b"}
    # The loser must release only what it took. Releasing by operation_id
    # deleted the winner's leases, and the winner then failed at its first
    # heartbeat mid-execution with "operation resource leases are missing".
    with services.operation_runner.transactions.read() as tx:
        connection = services.operation_runner.transactions.connection_for(tx)
        held = connection.execute(
            select(operation_resource_leases.c.resource_kind).where(
                operation_resource_leases.c.operation_id == created.id,
                operation_resource_leases.c.lease_owner == winner.lease_owner,
            )
        ).scalars()
        assert sorted(held) == sorted(resource.kind.value for resource in winner.resources)
    _execution_write(services, "heartbeat_operation", created.id, runner_id=str(winner.lease_owner))


def test_foreground_executor_and_worker_race_one_operation_without_duplicate_execution(
    services,
) -> None:
    """The two concrete hosts contend through the same durable claim contract."""
    operation = _operation_for_runner(services, "Foreground Worker Race Co")
    barrier = Barrier(2)
    execution_lock = Lock()
    executions = 0

    def execute(_operation, _cancelled):
        nonlocal executions
        with execution_lock:
            executions += 1
        return PreparedOperation()

    handler = _Handler(execute=execute)
    foreground = ForegroundOperationExecutor(
        _runner(
            services,
            {OperationType.ANALYZE_JOB: handler},
            runner_id="foreground-racer",
        ),
        poll_interval_seconds=0,
        sleeper=lambda _seconds: None,
    )
    worker = OperationWorker(
        _runner(
            services,
            {OperationType.ANALYZE_JOB: handler},
            runner_id="worker-racer",
        ),
        request_cancellation=services.operation_lifecycle.cancel,
        concurrency=1,
        poll_interval_seconds=0,
    )

    def run_foreground():
        barrier.wait(timeout=2)
        return foreground.execute(operation.id)

    def run_worker():
        barrier.wait(timeout=2)
        return worker.run_once()

    with ThreadPoolExecutor(max_workers=2) as pool:
        foreground_result, worker_result = [
            future.result(timeout=5)
            for future in (pool.submit(run_foreground), pool.submit(run_worker))
        ]

    assert executions == 1
    assert foreground_result is not None
    assert foreground_result.status is OperationStatus.SUCCEEDED
    assert _operation(services, operation.id).status is OperationStatus.SUCCEEDED
    assert worker_result is None or worker_result.id == operation.id


def test_worker_logs_claim_and_terminal_result_but_not_an_empty_poll(
    services, caplog, tmp_path
) -> None:
    operation = _operation_for_runner(services, "Worker Logging Co")
    event_logger = OperationFailureLogger(tmp_path, tmp_path / "logs")
    worker = OperationWorker(
        _runner(
            services,
            {OperationType.ANALYZE_JOB: _Handler()},
            runner_id="logging-worker",
            technical_logger=event_logger.record,
            operation_failure_logger=event_logger.record_operation_failure,
            operation_event_logger=event_logger.record_event,
        ),
        request_cancellation=services.operation_lifecycle.cancel,
        concurrency=1,
    )
    caplog.set_level("INFO", logger="cv_engine.worker")

    result = worker.run_once()
    message_count = len(caplog.messages)
    empty_result = worker.run_once()

    assert result is not None
    assert result.status is OperationStatus.SUCCEEDED
    assert empty_result is None
    assert len(caplog.messages) == message_count
    assert any(f"operation claimed id={operation.id}" in message for message in caplog.messages)
    assert any(f"operation completed id={operation.id}" in message for message in caplog.messages)
    entries = [
        json.loads(line)
        for line in (tmp_path / "logs" / "operations.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [entry["event"] for entry in entries] == [
        "operation.claimed",
        "operation.phase_changed",
        "operation.phase_changed",
        "operation.phase_changed",
        "operation.phase_changed",
        "operation.succeeded",
    ]
    assert [entry["phase"] for entry in entries if entry["event"] == "operation.phase_changed"] == [
        OperationPhase.PRE_EXECUTION_CHECK.value,
        OperationPhase.EXECUTING.value,
        OperationPhase.PRE_ACTIVATION_CHECK.value,
        OperationPhase.ACTIVATING.value,
    ]
    assert all(entry["operation_id"] == operation.id for entry in entries)
    assert entries[-1]["duration_ms"] >= 0


def test_application_and_global_render_leases_queue_contending_work(services) -> None:
    first = services.applications.ingest(
        IngestCommand(
            company="Lease A", target_role="Developer", job_text="Python role", client="web"
        )
    )
    second = services.applications.ingest(
        IngestCommand(
            company="Lease B",
            target_role="Developer",
            job_text="Python role",
            acknowledged_duplicates=True,
            client="web",
        )
    )
    app_one = _enqueue_operation(services, _stored_request(first.application_id, "app-1"))
    same_app = _enqueue_operation(services, _stored_request(first.application_id, "app-2"))
    render_request = CreateOperation(
        application_id=second.application_id,
        operation_type=OperationType.RENDER_REVISION,
        payload={"approved_revision_id": "revision-1"},
        idempotency_key="render-1",
        sources=OperationSources(approved_revision_id="revision-1"),
    )
    render_one = _enqueue_operation(services, render_request)
    third = services.applications.ingest(
        IngestCommand(
            company="Lease C",
            target_role="Developer",
            job_text="Python role",
            acknowledged_duplicates=True,
            client="web",
        )
    )
    render_two = _enqueue_operation(
        services,
        render_request.model_copy(
            update={
                "application_id": third.application_id,
                "idempotency_key": "render-2",
            }
        ),
    )

    assert _claim_operation(services, app_one.id, runner_id="runner-a") is not None
    assert _claim_operation(services, same_app.id, runner_id="runner-b") is None
    assert _operation(services, same_app.id).phase.value == "waiting_for_application"
    assert _claim_operation(services, render_one.id, runner_id="runner-b") is not None
    assert _claim_operation(services, render_two.id, runner_id="runner-c") is None
    assert _operation(services, render_two.id).phase.value == "waiting_for_render_slot"


def test_ai_resource_allows_two_operations_and_queues_the_third(services) -> None:
    operations = []
    for number in range(3):
        ingested = services.applications.ingest(
            IngestCommand(
                company=f"AI Lease {number}",
                target_role="Developer",
                job_text="Python role",
                acknowledged_duplicates=True,
                client="web",
            )
        )
        request = _stored_request(ingested.application_id, f"ai-{number}").model_copy(
            update={"provider": "openai", "model": "test-model"}
        )
        operations.append(_enqueue_operation(services, request))

    assert _claim_operation(services, operations[0].id, runner_id="ai-a")
    assert _claim_operation(services, operations[1].id, runner_id="ai-b")
    assert _claim_operation(services, operations[2].id, runner_id="ai-c") is None
    assert _operation(services, operations[2].id).phase.value == "waiting_for_ai_slot"


def test_heartbeat_prevents_interruption_until_extended_lease_expires(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="Heartbeat Co", target_role="Developer", job_text="Python role", client="web"
        )
    )
    created = _enqueue_operation(
        services,
        _stored_request(ingested.application_id),
    )
    claimed = _claim_operation(
        services,
        created.id,
        runner_id="runner-a",
        lease_seconds=30,
        now="2026-08-19T08:00:00+00:00",
    )
    assert claimed is not None
    assert (
        _execution_write(services, "interrupt_expired_operations", now="2026-08-19T08:00:20+00:00")
        == []
    )

    _execution_write(
        services,
        "heartbeat_operation",
        created.id,
        runner_id="runner-a",
        lease_seconds=30,
        now="2026-08-19T08:00:20+00:00",
    )
    assert (
        _execution_write(services, "interrupt_expired_operations", now="2026-08-19T08:00:49+00:00")
        == []
    )
    assert _execution_write(
        services, "interrupt_expired_operations", now="2026-08-19T08:00:51+00:00"
    ) == [created.id]
    assert _operation(services, created.id).status is OperationStatus.INTERRUPTED


def test_startup_interrupts_a_queued_operation_with_an_expired_runner_lease(
    services, database_engine
) -> None:
    operation = _operation_for_runner(services, "Expired Queued Co")
    with database_engine.begin() as connection:
        connection.execute(
            update(operations)
            .where(operations.c.id == operation.id)
            .values(
                lease_owner="dead-runner",
                heartbeat_at="2026-08-19T07:59:00+00:00",
                lease_expires_at="2026-08-19T07:59:30+00:00",
            )
        )

    interrupted = _execution_write(
        services, "interrupt_expired_operations", now="2026-08-19T08:00:00+00:00"
    )

    assert interrupted == [operation.id]
    assert _operation(services, operation.id).status is OperationStatus.INTERRUPTED


def test_startup_reclaims_a_previous_runners_claim_before_its_lease_expires(
    services, database_engine
) -> None:
    """A fast restart must not leave a dead predecessor's claim stuck.

    `interrupt_expired_operations` deliberately waits out the TTL, which is
    right for a periodic sweep that must not disturb another live claimant.
    A process's one-time startup sweep has no such claimant to protect - it
    hasn't claimed anything yet - so it must reclaim unconditionally instead
    of leaving the row stuck until some later restart happens to land after
    the original lease's TTL.
    """
    operation = _operation_for_runner(services, "Fast Restart Co")
    with database_engine.begin() as connection:
        connection.execute(
            update(operations)
            .where(operations.c.id == operation.id)
            .values(
                status="running",
                lease_owner="dead-runner",
                heartbeat_at="2026-08-19T08:00:00+00:00",
                lease_expires_at="2026-08-19T08:00:30+00:00",
            )
        )

    # The lease has not expired yet; a TTL-respecting sweep would skip it.
    assert (
        _execution_write(services, "interrupt_expired_operations", now="2026-08-19T08:00:05+00:00")
        == []
    )

    interrupted = _execution_write(
        services,
        "interrupt_claims_from_previous_runners",
        now="2026-08-19T08:00:05+00:00",
    )

    assert interrupted == [operation.id]
    assert _operation(services, operation.id).status is OperationStatus.INTERRUPTED


class _Handler:
    def __init__(self, *, execute=None, check=None, activate=None):
        self._execute = execute or (lambda _operation, _cancelled: PreparedOperation())
        self._check = check or (lambda _operation, _tx: None)
        self._activate = activate or (lambda _operation, _prepared, _tx: ())

    def verify_external_sources(self, operation):
        del operation

    def verify_sources(self, tx, operation):
        return self._check(operation, tx)

    def execute(self, operation, cancellation_requested):
        return self._execute(operation, cancellation_requested)

    def activate(self, tx, operation, prepared):
        return self._activate(operation, prepared, tx)

    def after_activation(self, operation, prepared):
        del operation, prepared


def _ingest_for_operation(services, company: str):
    """An Application to hang an Operation on, and nothing more.

    Acknowledged, because every caller ingests the same job text under a
    different company and Stage B made an unacknowledged duplicate a refusal. A
    test that builds two Operations in one project is exercising the runner,
    not duplicate detection.
    """
    return services.applications.ingest(
        IngestCommand(
            company=company,
            target_role="Developer",
            job_text="Python role",
            acknowledged_duplicates=True,
            client="web",
        )
    )


def _operation_for_runner(services, company: str = "Runner Co"):
    ingested = _ingest_for_operation(services, company)
    operation = _enqueue_operation(
        services,
        _stored_request(ingested.application_id, company.casefold().replace(" ", "-")),
    )
    return operation


def test_runner_activates_outputs_and_completes_in_one_activation_transaction(services) -> None:
    operation = _operation_for_runner(services)
    prepared = PreparedOperation(
        value={"proposal": "validated"},
        outputs=(
            OperationOutputReference(
                output_type="provider_response",
                output_id="provider-artifact-id",
                active=False,
            ),
        ),
    )
    runner = _runner(
        services,
        {OperationType.ANALYZE_JOB: _Handler(execute=lambda *_args: prepared)},
        runner_id="foreground-test",
    )

    result = runner.run(operation.id)

    assert result.status is OperationStatus.SUCCEEDED
    assert result.attempts_completed == 1
    assert [(item.output_id, item.active) for item in result.outputs] == [
        ("provider-artifact-id", True)
    ]


def test_source_changed_is_checked_before_execution_and_again_before_activation(services) -> None:
    for fail_on_check in (1, 2):
        operation = _operation_for_runner(services, f"Source Check {fail_on_check}")
        checks = 0

        def check(_operation, _repository, target=fail_on_check):
            nonlocal checks
            checks += 1
            if checks == target:
                raise SourceChanged()

        result = _runner(
            services,
            {OperationType.ANALYZE_JOB: _Handler(check=check)},
            runner_id=f"runner-{fail_on_check}",
        ).run(operation.id)

        assert result.status is OperationStatus.FAILED
        assert result.failure_code is OperationFailureCode.SOURCE_CHANGED
        assert checks == fail_on_check


def test_cancellation_after_output_creation_keeps_output_inactive(services) -> None:
    operation = _operation_for_runner(services, "Cancel Output Co")

    def execute(_operation, _cancelled):
        services.operation_lifecycle.cancel(operation.id)
        return PreparedOperation(
            outputs=(
                OperationOutputReference(
                    output_type="provider_response", output_id="inactive-output", active=False
                ),
            )
        )

    result = _runner(
        services,
        {OperationType.ANALYZE_JOB: _Handler(execute=execute)},
        runner_id="runner-cancel",
    ).run(operation.id)

    assert result.status is OperationStatus.CANCELLED
    assert result.failure_code is OperationFailureCode.CANCELLED_BEFORE_ACTIVATION
    assert result.outputs[0].active is False


def test_runner_retries_one_transient_failure(services) -> None:
    operation = _operation_for_runner(services, "Retry Co")
    attempts = 0
    delays = []

    def execute(_operation, _cancelled):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OperationExecutionError(
                OperationFailureCode.PROVIDER_TIMEOUT, "Provider timed out."
            )
        return PreparedOperation()

    result = _runner(
        services,
        {OperationType.ANALYZE_JOB: _Handler(execute=execute)},
        runner_id="runner-retry",
        sleeper=delays.append,
    ).run(operation.id)
    assert result.status is OperationStatus.SUCCEEDED
    assert result.attempts_completed == 2
    assert attempts == 2
    assert delays == [0.25]


def test_runner_keeps_unclassified_exception_detail_out_of_result(services) -> None:
    failed_operation = _operation_for_runner(services, "Technical Failure Co")
    failed = _runner(
        services,
        {
            OperationType.ANALYZE_JOB: _Handler(
                execute=lambda *_args: (_ for _ in ()).throw(RuntimeError("secret traceback"))
            )
        },
        runner_id="runner-failure",
        technical_logger=lambda _error: "logs/operation-failure.jsonl",
    ).run(failed_operation.id)
    assert failed.status is OperationStatus.FAILED
    assert failed.safe_failure_detail == "Operation execution failed."
    assert "secret traceback" not in failed.safe_failure_detail
    assert failed.technical_log_reference == "logs/operation-failure.jsonl"


def test_an_unclassified_infrastructure_failure_is_terminal_and_not_retried(
    services, monkeypatch
) -> None:
    """The default arm of the classification, pinned rather than assumed.

    Only the four transient codes get their one retry. A failure that names
    nothing more specific is `VALIDATION_EXECUTION_FAILED` and stops on the
    first attempt - which is what stops a message that merely *reads* like a
    timeout from buying a second provider call.
    """
    ingested = services.applications.ingest(
        IngestCommand(
            company="Unclassified Co",
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
            client="web",
        )
    )
    attempts = 0

    def prepare_that_fails(_command, *, operation_id=None):
        nonlocal attempts
        attempts += 1
        raise InfrastructureFailure("provider request timed out")

    monkeypatch.setattr(services.analysis, "prepare", prepare_that_fails)
    operation = services.operation_submissions.submit_analysis(
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_snapshot_id=ingested.job_snapshot_id,
            provider="openai",
            model="gpt-5.6-luna",
        ),
        idempotency_key="unclassified-failure",
        analysis_service=services.analysis,
    )

    completed = foreground_executor(services).execute(operation.id)

    assert completed.status is OperationStatus.FAILED
    assert completed.failure_code is OperationFailureCode.VALIDATION_EXECUTION_FAILED
    assert attempts == 1


def test_missing_fact_rendering_is_specific_terminal_failure_with_domain_context(
    services, monkeypatch
) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="Missing Rendering Co",
            target_role="Developer",
            job_text="Python developer role",
            client="web",
        )
    )
    attempts = 0

    def prepare_that_fails(_command, *, operation_id=None):
        nonlocal attempts
        attempts += 1
        raise MissingFactRendering("situational.agentic_multi_agent", "he")

    monkeypatch.setattr(services.analysis, "prepare", prepare_that_fails)
    operation = services.operation_submissions.submit_analysis(
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_snapshot_id=ingested.job_snapshot_id,
            language_override="he",
        ),
        idempotency_key="missing-rendering-failure",
        analysis_service=services.analysis,
    )

    completed = foreground_executor(services).execute(operation.id)

    assert completed.status is OperationStatus.FAILED
    assert completed.failure_code is OperationFailureCode.MISSING_FACT_RENDERING
    assert completed.safe_failure_detail == (
        "Fact situational.agentic_multi_agent has no 'he' rendering."
    )
    assert completed.outputs == []
    with pytest.raises(StateConflict, match="cannot be retried"):
        services.operation_lifecycle.retry(completed.id, idempotency_key="meaningless-retry")
    assert completed.attempts_completed == 1
    assert attempts == 1


def test_foreground_analysis_reuses_an_explicit_idempotency_key(
    ai_services, fake_openai, requirement_concepts
) -> None:
    ingested = ai_services.applications.ingest(
        IngestCommand(
            company="Foreground Operation Co",
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
            client="web",
        )
    )
    command = AnalyzeCommand(
        application_id=ingested.application_id,
        job_snapshot_id=ingested.job_snapshot_id,
    )

    def submit_and_run() -> str:
        fake_openai.script("propose_analysis", analysis_proposal())
        operation = ai_services.operation_submissions.submit_analysis(
            command,
            idempotency_key="analysis-idempotency-key",
            analysis_service=ai_services.analysis,
        )
        return foreground_executor(ai_services).execute(operation.id).id

    first = submit_and_run()
    second = submit_and_run()

    assert first == second
    assert _operation(ai_services, first).status is OperationStatus.SUCCEEDED


def test_draft_operation_activates_one_validated_working_draft(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="Draft Operation Co",
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
            client="web",
        )
    )
    analysis = seed_analysis_for_command(
        services,
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_snapshot_id=ingested.job_snapshot_id,
        ),
    )
    operation = services.operation_submissions.submit_draft(
        DraftCommand(
            application_id=ingested.application_id,
            job_analysis_id=analysis.analysis_id,
            selection_plan_id=analysis.selection_plan_id,
        ),
        idempotency_key="draft-operation",
        draft_service=services.drafts,
    )

    completed = foreground_executor(services).execute(operation.id)

    assert completed.status is OperationStatus.SUCCEEDED
    outputs = {output.output_type: output.output_id for output in completed.outputs}
    working_id = outputs["working_draft"]
    assert _active_working_draft(services, ingested.application_id).id == working_id
    validation = _latest_validation_for_working_draft(services, working_id)
    assert validation is not None and validation["report"].passed


def test_draft_operation_refuses_a_replaced_selection_plan(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="Draft Plan Race Co",
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
            client="web",
        )
    )
    analysis = seed_analysis_for_command(
        services,
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_snapshot_id=ingested.job_snapshot_id,
        ),
    )
    command = DraftCommand(
        application_id=ingested.application_id,
        job_analysis_id=analysis.analysis_id,
        selection_plan_id=analysis.selection_plan_id,
    )
    operation = services.operation_submissions.submit_draft(
        command,
        idempotency_key="draft-plan-race",
        draft_service=services.drafts,
    )
    services.analysis.create_selection_plan(
        CreateSelectionPlanCommand(
            application_id=ingested.application_id,
            job_analysis_id=analysis.analysis_id,
        )
    )

    failed = foreground_executor(services).execute(operation.id)

    assert failed.status is OperationStatus.FAILED
    assert failed.failure_code is OperationFailureCode.SOURCE_CHANGED
    with pytest.raises(UnknownRecord):
        _active_working_draft(services, ingested.application_id)


def test_failed_render_operation_preserves_registered_outputs_as_inactive(
    ready_application,
    monkeypatch,
) -> None:
    setup = ready_application("Invalid Render Operation Co")
    failed_report = ValidationReport.from_findings(
        groups={"render": False},
        issues=[
            ValidationIssue(
                group="render",
                code="injected-render-failure",
                message="injected failure",
            )
        ],
    )
    monkeypatch.setattr(
        setup.services.rendering.renderer,
        "validate_rendered",
        lambda *_args, **_kwargs: failed_report,
    )
    operation = setup.services.operation_submissions.submit_render(
        RenderCommand(
            application_id=setup.application_id,
            approved_revision_id=setup.approved.revision_id,
        ),
        idempotency_key="invalid-render-operation",
        rendering_service=setup.services.rendering,
    )

    failed = foreground_executor(setup.services).execute(operation.id)

    assert failed.status is OperationStatus.FAILED
    assert failed.failure_code is OperationFailureCode.RENDER_FAILED
    assert failed.technical_log_reference == "logs/operations.jsonl"
    log_path = setup.services.paths.root / failed.technical_log_reference
    assert log_path.is_file()
    log_entry = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert {
        "occurred_at",
        "level",
        "operation_id",
        "application_id",
        "phase",
        "error_code",
        "log_reference",
    } <= log_entry.keys()
    assert log_entry["operation_id"] == failed.id
    assert log_entry["application_id"] == setup.application_id
    assert log_entry["error_code"] == OperationFailureCode.RENDER_FAILED.value
    assert log_entry["log_reference"] == failed.technical_log_reference
    assert len(failed.outputs) == 2
    assert all(not output.active for output in failed.outputs)
    for output in failed.outputs:
        assert (
            _artifact_version(setup.services, output.output_id)["lifecycle_status"]
            == "rendered-invalid"
        )

    retried = setup.services.operation_lifecycle.retry(
        failed.id, idempotency_key="invalid-render-operation-retry"
    )
    failed_again = foreground_executor(setup.services).execute(retried.id)
    assert failed_again.status is OperationStatus.FAILED
    assert {(output.output_type, output.output_id) for output in failed_again.outputs} == {
        (output.output_type, output.output_id) for output in failed.outputs
    }


def _render_operation(setup, key: str):
    return setup.services.operation_submissions.submit_render(
        RenderCommand(
            application_id=setup.application_id,
            approved_revision_id=setup.approved.revision_id,
        ),
        idempotency_key=key,
        rendering_service=setup.services.rendering,
    )


def _cancel_after_render(setup, operation_id: str):
    def interfere(_executed) -> None:
        setup.services.operation_lifecycle.cancel(operation_id)

    return interfere


def _move_the_source_after_render(setup, _operation_id: str):
    def interfere(_executed) -> None:
        manifest = _artifact_version_for_revision(
            setup.services, setup.approved.revision_id, "claim_manifest", "approved"
        )
        path = artifact_path(setup.services, manifest["path"])
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    return interfere


@pytest.mark.parametrize(
    "interference,expected_status,expected_code",
    [
        (
            _cancel_after_render,
            OperationStatus.CANCELLED,
            OperationFailureCode.CANCELLED_BEFORE_ACTIVATION,
        ),
        (
            _move_the_source_after_render,
            OperationStatus.FAILED,
            OperationFailureCode.SOURCE_CHANGED,
        ),
    ],
    ids=["cancelled", "source-changed"],
)
def test_a_render_stopped_between_the_phases_keeps_registered_inactive_outputs(
    ready_application, monkeypatch, interference, expected_status, expected_code
) -> None:
    """§18: "a completed output after cancellation is recorded as inactive evidence".

    Both parameters are the same window: the render finished and its three
    artifacts exist, and then the Operation stopped before activation - once
    because the user cancelled, once because the approved source moved under it.

    What has to hold in both is that every Operation output names a row that is
    really there. `operation_outputs.output_id` carries no foreign key, so
    nothing in the schema refuses a dangling reference and nothing reading the
    Operation can tell one from a real output. A reference to nothing is not
    evidence.

    Parameterized rather than written twice because the property is one
    property; the two interferences are only the two ways of reaching the
    window. `artifact_version` raises `UnknownRecord` for an ID registered
    nowhere, so resolving both *is* the assertion.
    """
    setup = ready_application(f"Stopped Render {expected_status.value}")
    existing_pdf = _latest_artifact_version(
        setup.services, setup.application_id, "resume_pdf", "rendered"
    )
    original_record_validation = SqlAlchemyValidationRepository.record_validation
    post_render_writes = 0

    def record_validation(
        self, tx, application_id, phase, report, artifact_version_id=None, **kwargs
    ):
        nonlocal post_render_writes
        if phase == "post-render":
            post_render_writes += 1
        return original_record_validation(
            self,
            tx,
            application_id,
            phase,
            report,
            artifact_version_id,
            **kwargs,
        )

    monkeypatch.setattr(SqlAlchemyValidationRepository, "record_validation", record_validation)
    operation = _render_operation(setup, f"stopped-render-{expected_status.value}")
    original = setup.services.rendering.execute
    interfere = interference(setup, operation.id)

    def execute_then_interfere(prepared):
        executed = original(prepared)
        interfere(executed)
        return executed

    monkeypatch.setattr(setup.services.rendering, "execute", execute_then_interfere)
    stopped = foreground_executor(setup.services).execute(operation.id)

    assert stopped.status is expected_status
    assert stopped.failure_code is expected_code
    outputs = [
        output for output in stopped.outputs if output.output_type in {"resume_html", "resume_pdf"}
    ]
    assert len(outputs) == 2
    assert all(not output.active for output in outputs)
    for output in outputs:
        registered = _artifact_version(setup.services, output.output_id)
        assert registered["revision_id"] == setup.approved.revision_id
        assert registered["lifecycle_status"] == "rendered"

    # An identical retry reuses the immutable artifacts and their existing
    # evidence. Stopping before activation must not add a fresh ValidationRun.
    pdf = next(output for output in outputs if output.output_type == "resume_pdf")
    assert pdf.output_id == existing_pdf["id"]
    assert post_render_writes == 0


def test_a_failure_partway_through_registration_leaves_no_artifact_at_all(
    ready_application, monkeypatch
) -> None:
    """Both artifacts are one render: both are registered, or neither is.

    The first repair moved registration into `execute` so the rows survive a
    cancellation. Left as independent writes that would have bought the
    opposite bug: a failure on the third leaves two rows committed while
    `execute` raises, so the runner records no Operation output at all and the
    Application carries registered artifacts belonging to a render that never
    reported. That is the mirror of the orphan being repaired, and it is not
    reachable through cancellation or `SOURCE_CHANGED`, which is why neither of
    those tests would have found it.

    The second registration is failed deliberately. What is asserted is that the
    first two did not survive it.
    """
    setup = ready_application("Partial Registration Co")
    before = {row["id"] for row in _artifact_versions(setup.services, setup.application_id)}
    operation = _render_operation(setup, "partial-registration")
    original = SqlAlchemyArtifactCatalog.register_artifact_version
    calls = 0

    def fail_on_the_second(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise InfrastructureFailure("injected registry failure")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(SqlAlchemyArtifactCatalog, "register_artifact_version", fail_on_the_second)
    monkeypatch.setattr(
        SqlAlchemyRenderContextReader,
        "matching_render_artifact",
        lambda *_args, **_kwargs: None,
    )
    failed = foreground_executor(setup.services).execute(operation.id)

    assert failed.status is OperationStatus.FAILED
    assert calls == 2, "the injected failure never reached the code under test"
    after = {row["id"] for row in _artifact_versions(setup.services, setup.application_id)}
    assert after == before, "a partial render registration survived"
    assert not [
        output for output in failed.outputs if output.output_type in {"resume_html", "resume_pdf"}
    ]


def test_a_failure_ingesting_the_second_render_payload_registers_neither(
    ready_application, monkeypatch
) -> None:
    setup = ready_application("Partial Render Ingest Co")
    before = {row["id"] for row in _artifact_versions(setup.services, setup.application_id)}
    original = PayloadStore.ingest_render_output
    calls = 0

    def fail_second(self, path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected second ingest failure")
        return original(self, path)

    monkeypatch.setattr(PayloadStore, "ingest_render_output", fail_second)
    failed = foreground_executor(setup.services).execute(
        _render_operation(setup, "partial-render-ingest").id
    )
    assert failed.status is OperationStatus.FAILED
    after = {row["id"] for row in _artifact_versions(setup.services, setup.application_id)}
    assert after == before


def _approve_command(services, application_id) -> ApproveDraftCommand:
    """Validate the active draft and name the run that approval must rely on."""
    validated = validate_active_draft(services, application_id)
    return ApproveDraftCommand(
        working_draft_id=validated.working_draft_id,
        expected_edit_version=validated.edit_version,
        validation_run_id=validated.validation_run_id,
        client="web",
    )


def test_pending_approval_receipt_recovers_a_committed_revision(drafted_application) -> None:
    setup = drafted_application("Approval Recovery Co")
    working = _active_working_draft(setup.services, setup.application_id)
    command = _approve_command(setup.services, setup.application_id)
    reserved_revision = new_id()
    receipt = _claim_receipt(
        setup.services,
        "approve_draft",
        "approval-recovery",
        {
            "working_draft_id": command.working_draft_id,
            "expected_edit_version": command.expected_edit_version,
            "validation_run_id": command.validation_run_id,
            "content_hash": working.content_hash,
        },
        reserved_entity_id=reserved_revision,
    )
    committed = setup.services.draft_approval.approve_draft(command, revision_id=reserved_revision)
    assert receipt["status"] == "pending"

    recovered = setup.services.draft_approval.approve_idempotent(
        command,
        idempotency_key="approval-recovery",
    )

    assert recovered == committed
    completed = _read_receipt(
        setup.services,
        "approve_draft",
        "approval-recovery",
    )
    assert completed["status"] == "completed"
    assert len(_approved_revisions(setup.services, setup.application_id)) == 1


@pytest.mark.parametrize("receipt_status", ["pending", "completed"])
@pytest.mark.parametrize(
    "changed_input", ["expected_edit_version", "validation_run_id", "actor_type", "client"]
)
def test_approval_recovery_refuses_changed_inputs(
    drafted_application, receipt_status, changed_input
) -> None:
    setup = drafted_application("Approval Frozen Inputs Co")
    command = _approve_command(setup.services, setup.application_id)
    working = _working_draft(setup.services, command.working_draft_id)
    receipt = _claim_receipt(
        setup.services,
        "approve_draft",
        "approval-frozen-inputs",
        {**command.model_dump(mode="json"), "content_hash": working.content_hash},
        reserved_entity_id=new_id(),
    )
    committed = setup.services.draft_approval.approve_draft(
        command, revision_id=receipt["reserved_entity_id"]
    )
    if receipt_status == "completed":
        _complete_receipt(setup.services, receipt["id"], committed.model_dump(mode="json"))
    changed_values = {
        "expected_edit_version": command.expected_edit_version + 1,
        "validation_run_id": new_id(),
        "actor_type": "system",
        "client": "worker",
    }
    changed = command.model_copy(update={changed_input: changed_values[changed_input]})
    with pytest.raises(StateConflict) as refused:
        setup.services.draft_approval.approve_idempotent(
            changed,
            idempotency_key="approval-frozen-inputs",
        )
    assert refused.value.code == IDEMPOTENCY_KEY_REUSED
    after = _read_receipt(setup.services, "approve_draft", "approval-frozen-inputs")
    assert after["status"] == receipt_status
    assert after["payload"] == receipt["payload"]
    assert _approved_revisions(setup.services, setup.application_id) == [
        _approved_revision(setup.services, committed.revision_id)
    ]
    replayed = setup.services.draft_approval.approve_idempotent(
        command,
        idempotency_key="approval-frozen-inputs",
    )
    assert replayed == committed


@pytest.mark.parametrize(
    "failure_stage", ["artifact_registration", "receipt_completion", "after_commit"]
)
def test_approval_identical_retry_reuses_reservation_after_failure(
    drafted_application, monkeypatch, failure_stage
) -> None:
    setup = drafted_application("Approval Retry Co")
    command = _approve_command(setup.services, setup.application_id)
    before_artifacts = _artifact_versions(setup.services, setup.application_id)
    calls = 0
    if failure_stage == "artifact_registration":
        original = SqlAlchemyArtifactCatalog.register_artifact_version

        def fail_registration(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise InfrastructureFailure("injected second approval artifact failure")
            return original(self, *args, **kwargs)

        monkeypatch.setattr(
            SqlAlchemyArtifactCatalog, "register_artifact_version", fail_registration
        )
    elif failure_stage == "receipt_completion":
        original = setup.services.draft_approval.receipts.complete_idempotency_receipt

        def fail_completion(*args, **kwargs):
            nonlocal calls
            calls += 1
            raise InfrastructureFailure("injected approval receipt completion failure")

        monkeypatch.setattr(
            setup.services.draft_approval.receipts,
            "complete_idempotency_receipt",
            fail_completion,
        )
    else:
        original = setup.services.draft_approval._approve

        def fail_after_commit(*args, **kwargs):
            nonlocal calls
            original(*args, **kwargs)
            calls += 1
            raise RuntimeError("injected lost response after approval commit")

        monkeypatch.setattr(setup.services.draft_approval, "_approve", fail_after_commit)

    expected_error = RuntimeError if failure_stage == "after_commit" else InfrastructureFailure
    with pytest.raises(expected_error):
        setup.services.draft_approval.approve_idempotent(
            command,
            idempotency_key="approval-retry",
        )
    assert calls == (2 if failure_stage == "artifact_registration" else 1)
    receipt = _read_receipt(setup.services, "approve_draft", "approval-retry")
    assert receipt["status"] == ("completed" if failure_stage == "after_commit" else "pending")
    references = [
        f"artifacts/revisions/{setup.application_id}/{receipt['reserved_entity_id']}/resume.json",
        f"artifacts/revisions/{setup.application_id}/{receipt['reserved_entity_id']}/resume.md",
    ]
    published = [setup.services.payloads.read_payload_text(reference) for reference in references]
    revisions = _approved_revisions(setup.services, setup.application_id)
    if failure_stage in {"artifact_registration", "receipt_completion"}:
        assert revisions == []
        assert _artifact_versions(setup.services, setup.application_id) == before_artifacts
        assert _working_draft(setup.services, command.working_draft_id).active
        if failure_stage == "artifact_registration":
            monkeypatch.setattr(SqlAlchemyArtifactCatalog, "register_artifact_version", original)
        else:
            monkeypatch.setattr(
                setup.services.draft_approval.receipts,
                "complete_idempotency_receipt",
                original,
            )
    else:
        assert len(revisions) == 1
        assert revisions[0].id == receipt["reserved_entity_id"]
        assert receipt["status"] == "completed"
        monkeypatch.setattr(setup.services.draft_approval, "_approve", original)

    recovered = setup.services.draft_approval.approve_idempotent(
        command,
        idempotency_key="approval-retry",
    )
    repeated = setup.services.draft_approval.approve_idempotent(
        command,
        idempotency_key="approval-retry",
    )
    assert recovered == repeated
    assert recovered.revision_id == receipt["reserved_entity_id"]
    assert len(_approved_revisions(setup.services, setup.application_id)) == 1
    completed = _read_receipt(setup.services, "approve_draft", "approval-retry")
    assert completed["id"] == receipt["id"]
    assert completed["payload"] == receipt["payload"]
    assert completed["status"] == "completed"
    assert [
        setup.services.payloads.read_payload_text(reference) for reference in references
    ] == published


def test_worker_shutdown_requests_cancellation_and_prevents_activation(
    services, monkeypatch
) -> None:
    operation = _operation_for_runner(services, "Worker Shutdown Co")
    started = Event()
    original_cancel = services.operation_lifecycle.operations.request_cancellation
    cancellation_attempts = []

    def cancel_after_heartbeat(tx, operation_id):
        cancellation_attempts.append(operation_id)
        if len(cancellation_attempts) == 1:
            # Establish the cancellation snapshot, then commit a heartbeat on
            # another connection. Its update must force cancellation to retry.
            services.operation_runner.execution_store.operation(tx, operation_id)
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(
                    _execution_write,
                    services,
                    "heartbeat_operation",
                    operation_id,
                    runner_id="shutdown-worker",
                ).result(timeout=2)
        return original_cancel(tx, operation_id)

    monkeypatch.setattr(
        services.operation_lifecycle.operations, "request_cancellation", cancel_after_heartbeat
    )

    def execute(_operation, cancellation_requested):
        started.set()
        while not cancellation_requested():
            Event().wait(0.01)
        return PreparedOperation()

    runner = _runner(
        services,
        {OperationType.ANALYZE_JOB: _Handler(execute=execute)},
        runner_id="shutdown-worker",
        heartbeat_interval_seconds=10,
    )
    worker = OperationWorker(
        runner,
        request_cancellation=services.operation_lifecycle.cancel,
        concurrency=1,
        poll_interval_seconds=0.01,
    )
    stop = Event()
    thread = Thread(target=worker.serve, args=(stop,))
    thread.start()
    assert started.wait(timeout=2)

    stop.set()
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert _operation(services, operation.id).status is OperationStatus.CANCELLED
    assert len(cancellation_attempts) == 2


def test_heartbeat_skips_inflight_cancellation_without_failing_operation(services) -> None:
    operation = _operation_for_runner(services, "Heartbeat Cancellation Co")
    claimed = _claim_operation(services, operation.id, runner_id="owner")
    assert claimed is not None
    transactions = services.operation_runner.transactions

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transactions.write() as tx:
            services.operation_lifecycle.operations.request_cancellation(tx, operation.id)
            # The cancellation update holds the row lock until this scope commits.
            # A heartbeat on another connection must skip it rather than wait and
            # raise a REPEATABLE READ serialization error after that commit.
            future = pool.submit(
                _execution_write,
                services,
                "heartbeat_operation",
                operation.id,
                runner_id="owner",
            )
            future.result(timeout=2)

    result = _execution_write(services, "complete_operation", operation.id, runner_id="owner")
    assert result.status is OperationStatus.CANCELLED
    assert result.failure_code is OperationFailureCode.CANCELLED_BEFORE_ACTIVATION


# --- execution-store methods against real PostgreSQL -------------------------
#
# The tests above drive Operations through the runner and the services, which is
# where the product's behaviour lives. These drive the token adapter methods
# directly, because their refusals are the branches a successful run never
# takes: a lease claimed by someone else, an output activated after
# cancellation, a receipt completed twice. Acceptance item 1 asks for the
# adapter under real PostgreSQL, and a method whose only coverage is the happy
# path is not covered.


def _queued(services, company: str, key: str = "request-1", created_at: str | None = None):
    ingested = _ingest_for_operation(services, company)
    return _enqueue_operation(
        services,
        _stored_request(ingested.application_id, key=key),
        created_at=created_at,
    )


def test_claim_next_operation_takes_the_oldest_ready_operation_or_nothing(services) -> None:
    """Ordering is by `created_at`, and only to the second.

    `utc_now()` has one-second resolution, so two operations created in the same
    second tie and the query falls through to `id`, which is a UUIDv4 — that is
    arbitrary, not creation order. Timestamps are passed explicitly here so the
    assertion tests the guarantee that exists rather than one that holds only
    when the clock happens to tick between two calls.
    """
    first = _queued(services, "Queue One", key="queue-1", created_at="2026-08-19T07:00:00+00:00")
    second = _queued(services, "Queue Two", key="queue-2", created_at="2026-08-19T07:00:01+00:00")

    claimed = _claim_next_operation(services, runner_id="runner-a", now="2026-08-19T08:00:00+00:00")
    assert claimed is not None
    assert claimed.id == first.id, "the older queued operation is taken first"

    # A retry that is not due yet is not ready, so the queue skips past it.
    _execution_write(
        services,
        "record_operation_attempt",
        first.id,
        runner_id="runner-a",
        retry_at="2026-08-19T09:00:00+00:00",
    )
    again = _claim_next_operation(services, runner_id="runner-b", now="2026-08-19T08:00:00+00:00")
    assert again is not None
    assert again.id == second.id

    assert (
        _claim_next_operation(services, runner_id="runner-c", now="2026-08-19T08:00:00+00:00")
        is None
    ), "an empty ready queue returns None rather than blocking or raising"


def test_lease_owning_methods_refuse_a_runner_that_does_not_hold_the_lease(services) -> None:
    """One contract, five entry points.

    Each of these updates `WHERE status='running' AND lease_owner=?` and raises
    when that matches nothing. Parameterised over the calls rather than written
    five times, so a sixth lease-owning method is one line.
    """
    operation = _queued(services, "Lease Co")
    _claim_operation(services, operation.id, runner_id="owner", now="2026-08-19T08:00:00+00:00")

    calls = {
        "set_operation_phase": lambda runner: _execution_write(
            services,
            "set_operation_phase",
            operation.id,
            OperationPhase.EXECUTING,
            runner_id=runner,
        ),
        "record_operation_attempt": lambda runner: _execution_write(
            services, "record_operation_attempt", operation.id, runner_id=runner
        ),
        "heartbeat_operation": lambda runner: _execution_write(
            services, "heartbeat_operation", operation.id, runner_id=runner
        ),
        "fail_operation": lambda runner: _execution_write(
            services,
            "fail_operation",
            operation.id,
            OperationFailureCode.PROVIDER_UNAVAILABLE,
            "provider down",
            runner_id=runner,
        ),
        "complete_operation": lambda runner: _execution_write(
            services, "complete_operation", operation.id, runner_id=runner
        ),
    }
    for name, call in calls.items():
        with pytest.raises(StateConflict, match="lease is not owned"):
            call("impostor")
        assert _operation(services, operation.id).status is OperationStatus.RUNNING, (
            f"{name} must not change the operation when it refuses"
        )

    assert (
        _execution_write(services, "record_operation_attempt", operation.id, runner_id="owner") == 1
    )
    assert _operation(services, operation.id).phase is OperationPhase.RETRY_WAIT


def test_completing_a_cancelled_operation_records_cancellation_not_success(services) -> None:
    operation = _queued(services, "Cancel Co")
    _claim_operation(services, operation.id, runner_id="owner", now="2026-08-19T08:00:00+00:00")
    services.operation_lifecycle.cancel(operation.id)

    completed = _execution_write(services, "complete_operation", operation.id, runner_id="owner")
    assert completed.status is OperationStatus.CANCELLED
    assert completed.failure_code is OperationFailureCode.CANCELLED_BEFORE_ACTIVATION
    assert completed.finished_at


def test_outputs_cannot_be_reactivated_or_activated_after_cancellation(
    services,
) -> None:
    operation = _queued(services, "Output Co")
    _claim_operation(services, operation.id, runner_id="owner", now="2026-08-19T08:00:00+00:00")

    _execution_write(services, "record_operation_output", operation.id, "analysis", "analysis-1")
    _execution_write(services, "activate_operation_output", operation.id, "analysis", "analysis-1")
    with pytest.raises(StateConflict, match="cannot be activated"):
        _execution_write(
            services, "activate_operation_output", operation.id, "analysis", "analysis-1"
        )
    with pytest.raises(StateConflict, match="cannot be activated"):
        _execution_write(
            services, "activate_operation_output", operation.id, "analysis", "never-recorded"
        )

    with pytest.raises(UnknownRecord):
        _execution_write(
            services, "record_operation_output", "no-such-operation", "analysis", "analysis-2"
        )

    # Cancellation closes the window: an output may still be recorded, but it
    # cannot be activated either by the activation method or by active=True on
    # the recording method.
    services.operation_lifecycle.cancel(operation.id)
    _execution_write(services, "record_operation_output", operation.id, "analysis", "analysis-3")
    with pytest.raises(StateConflict, match="cannot be activated"):
        _execution_write(
            services, "activate_operation_output", operation.id, "analysis", "analysis-3"
        )
    with pytest.raises(StateConflict, match="cannot be activated"):
        _execution_write(
            services, "record_operation_output", operation.id, "analysis", "analysis-4", active=True
        )
