from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock, Thread

import pytest
from foreground import ForegroundOperationExecutor, foreground_executor
from helpers import ACCOUNT_MANAGER_JOB, validate_active_draft
from pydantic import ValidationError
from sqlalchemy import delete, update
from sqlalchemy.exc import ProgrammingError

from cv_engine.application.commands import (
    AnalyzeCommand,
    ApproveDraftCommand,
    DraftCommand,
    IngestCommand,
    RenderCommand,
)
from cv_engine.application.errors import (
    IDEMPOTENCY_KEY_REUSED,
    InfrastructureFailure,
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
from cv_engine.domain.models import ValidationIssue, ValidationReport
from cv_engine.infrastructure.operation_logging import OperationFailureLogger
from cv_engine.infrastructure.persistence import Repository
from cv_engine.infrastructure.persistence.tables import operations
from cv_engine.runtime.execution import OperationWorker
from cv_engine.util import new_id


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
    (OperationStatus.QUEUED, None, (OperationAction.CANCEL,)),
    (OperationStatus.RUNNING, None, (OperationAction.CANCEL,)),
    (OperationStatus.RUNNING, "2026-08-24T07:01:00Z", ()),
    (OperationStatus.FAILED, None, (OperationAction.RETRY,)),
    (OperationStatus.SUCCEEDED, None, (OperationAction.RETRY,)),
    (OperationStatus.CANCELLED, None, (OperationAction.RETRY,)),
    (OperationStatus.INTERRUPTED, None, (OperationAction.RETRY,)),
]


def test_operation_actions_are_derived_by_the_lifecycle() -> None:
    assert {case[0] for case in _OPERATION_ACTION_CASES} == set(OperationStatus)
    for status, cancellation_requested_at, expected in _OPERATION_ACTION_CASES:
        assert available_operation_actions(status, cancellation_requested_at) == expected, status


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
        payload={"job_snapshot_id": "snapshot-id", "mode": "deterministic"},
        idempotency_key=key,
        sources=OperationSources(
            job_snapshot_id="snapshot-id",
            job_snapshot_hash="a" * 64,
        ),
        provider="deterministic",
        model="rules-v1",
    )


def test_operation_creation_is_idempotent_and_projects_active_work(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="Operation Co", target_role="Developer", job_text="Python role", client="web"
        )
    )
    request = _stored_request(ingested.application_id)

    created = services.repository.create_operation(
        request,
        operation_id="operation-id",
        created_at="2026-08-19T08:00:00+00:00",
    )
    repeated = services.repository.create_operation(
        request,
        operation_id="ignored-id",
    )

    assert repeated == created
    assert created.payload_hash == request.payload_hash
    assert created.status is OperationStatus.QUEUED
    assert services.repository.operation(created.id) == created
    assert services.repository.active_operation(ingested.application_id).id == created.id
    detail = services.queries.application_detail(ingested.application_id)
    assert detail.active_operation == as_operation_view(created)
    assert detail.active_operation.status is OperationStatus.QUEUED


def test_operation_rejects_idempotency_key_with_another_payload(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="Conflict Co", target_role="Developer", job_text="Python role", client="web"
        )
    )
    request = _stored_request(ingested.application_id)
    services.repository.create_operation(
        request,
    )
    conflicting = request.model_copy(update={"payload": {"mode": "ai"}})

    # Assert the contracted code rather than the prose: the code is what a client
    # switches on, and the message is free to be rewritten for a human.
    with pytest.raises(StateConflict) as raised:
        services.repository.create_operation(
            conflicting,
        )
    assert raised.value.code == IDEMPOTENCY_KEY_REUSED


def test_terminal_operation_rows_cannot_be_rewritten_or_deleted(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="Immutable Op Co", target_role="Developer", job_text="Python role", client="web"
        )
    )
    created = services.repository.create_operation(
        _stored_request(ingested.application_id),
    )
    with services.repository.transaction() as connection:
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
        with services.repository.transaction() as connection:
            connection.execute(
                update(operations).where(operations.c.id == created.id).values(message="rewritten")
            )
    with pytest.raises(ProgrammingError, match="immutable record"):
        with services.repository.transaction() as connection:
            connection.execute(delete(operations).where(operations.c.id == created.id))


def test_two_runners_racing_one_operation_produce_one_claim(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="Claim Race Co", target_role="Developer", job_text="Python role", client="web"
        )
    )
    created = services.repository.create_operation(
        _stored_request(ingested.application_id),
    )
    barrier = Barrier(2)

    def claim(runner_id: str):
        repository = Repository(services.repository.engine)
        barrier.wait(timeout=2)
        return repository.claim_operation(
            created.id,
            runner_id=runner_id,
            now="2026-08-19T08:00:00+00:00",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ("runner-a", "runner-b")))

    claimed = [result for result in results if result is not None]
    assert len(claimed) == 1
    assert claimed[0].lease_owner in {"runner-a", "runner-b"}


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
        services.repository,
        OperationRunner(
            services.repository,
            {OperationType.ANALYZE_JOB: handler},
            runner_id="foreground-racer",
        ),
        poll_interval_seconds=0,
        sleeper=lambda _seconds: None,
    )
    worker = OperationWorker(
        services.repository,
        OperationRunner(
            services.repository,
            {OperationType.ANALYZE_JOB: handler},
            runner_id="worker-racer",
        ),
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
    assert services.repository.operation(operation.id).status is OperationStatus.SUCCEEDED
    assert worker_result is None or worker_result.id == operation.id


def test_worker_logs_claim_and_terminal_result_but_not_an_empty_poll(
    services, caplog, tmp_path
) -> None:
    operation = _operation_for_runner(services, "Worker Logging Co")
    event_logger = OperationFailureLogger(tmp_path, tmp_path / "logs")
    worker = OperationWorker(
        services.repository,
        OperationRunner(
            services.repository,
            {OperationType.ANALYZE_JOB: _Handler()},
            runner_id="logging-worker",
            technical_logger=event_logger.record,
            operation_failure_logger=event_logger.record_operation_failure,
            operation_event_logger=event_logger.record_event,
        ),
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
    app_one = services.repository.create_operation(_stored_request(first.application_id, "app-1"))
    same_app = services.repository.create_operation(_stored_request(first.application_id, "app-2"))
    render_request = CreateOperation(
        application_id=second.application_id,
        operation_type=OperationType.RENDER_REVISION,
        payload={"approved_revision_id": "revision-1"},
        idempotency_key="render-1",
        sources=OperationSources(approved_revision_id="revision-1"),
    )
    render_one = services.repository.create_operation(render_request)
    third = services.applications.ingest(
        IngestCommand(
            company="Lease C",
            target_role="Developer",
            job_text="Python role",
            acknowledged_duplicates=True,
            client="web",
        )
    )
    render_two = services.repository.create_operation(
        render_request.model_copy(
            update={
                "application_id": third.application_id,
                "idempotency_key": "render-2",
            }
        ),
    )

    assert services.repository.claim_operation(app_one.id, runner_id="runner-a") is not None
    assert services.repository.claim_operation(same_app.id, runner_id="runner-b") is None
    assert services.repository.operation(same_app.id).phase.value == "waiting_for_application"
    assert services.repository.claim_operation(render_one.id, runner_id="runner-b") is not None
    assert services.repository.claim_operation(render_two.id, runner_id="runner-c") is None
    assert services.repository.operation(render_two.id).phase.value == "waiting_for_render_slot"


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
        operations.append(services.repository.create_operation(request))

    assert services.repository.claim_operation(operations[0].id, runner_id="ai-a")
    assert services.repository.claim_operation(operations[1].id, runner_id="ai-b")
    assert services.repository.claim_operation(operations[2].id, runner_id="ai-c") is None
    assert services.repository.operation(operations[2].id).phase.value == "waiting_for_ai_slot"


def test_heartbeat_prevents_interruption_until_extended_lease_expires(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="Heartbeat Co", target_role="Developer", job_text="Python role", client="web"
        )
    )
    created = services.repository.create_operation(
        _stored_request(ingested.application_id),
    )
    claimed = services.repository.claim_operation(
        created.id,
        runner_id="runner-a",
        lease_seconds=30,
        now="2026-08-19T08:00:00+00:00",
    )
    assert claimed is not None
    assert services.repository.interrupt_expired_operations(now="2026-08-19T08:00:20+00:00") == []

    services.repository.heartbeat_operation(
        created.id,
        runner_id="runner-a",
        lease_seconds=30,
        now="2026-08-19T08:00:20+00:00",
    )
    assert services.repository.interrupt_expired_operations(now="2026-08-19T08:00:49+00:00") == []
    assert services.repository.interrupt_expired_operations(now="2026-08-19T08:00:51+00:00") == [
        created.id
    ]
    assert services.repository.operation(created.id).status is OperationStatus.INTERRUPTED


def test_startup_interrupts_a_queued_operation_with_an_expired_runner_lease(services) -> None:
    operation = _operation_for_runner(services, "Expired Queued Co")
    with services.repository.transaction() as connection:
        connection.execute(
            update(operations)
            .where(operations.c.id == operation.id)
            .values(
                lease_owner="dead-runner",
                heartbeat_at="2026-08-19T07:59:00+00:00",
                lease_expires_at="2026-08-19T07:59:30+00:00",
            )
        )

    interrupted = services.repository.interrupt_expired_operations(now="2026-08-19T08:00:00+00:00")

    assert interrupted == [operation.id]
    assert services.repository.operation(operation.id).status is OperationStatus.INTERRUPTED


class _Handler:
    def __init__(self, *, execute=None, check=None, activate=None):
        self._execute = execute or (lambda _operation, _cancelled: PreparedOperation())
        self._check = check or (lambda _operation, _repository: None)
        self._activate = activate or (lambda _operation, _prepared, _repository: ())

    def check_sources(self, operation, repository):
        return self._check(operation, repository)

    def execute(self, operation, cancellation_requested):
        return self._execute(operation, cancellation_requested)

    def activate(self, operation, prepared, repository):
        return self._activate(operation, prepared, repository)


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
    operation = services.repository.create_operation(
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
    runner = OperationRunner(
        services.repository,
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

        result = OperationRunner(
            services.repository,
            {OperationType.ANALYZE_JOB: _Handler(check=check)},
            runner_id=f"runner-{fail_on_check}",
        ).run(operation.id)

        assert result.status is OperationStatus.FAILED
        assert result.failure_code is OperationFailureCode.SOURCE_CHANGED
        assert checks == fail_on_check


def test_cancellation_after_output_creation_keeps_output_inactive(services) -> None:
    operation = _operation_for_runner(services, "Cancel Output Co")

    def execute(_operation, _cancelled):
        services.repository.request_operation_cancellation(operation.id)
        return PreparedOperation(
            outputs=(
                OperationOutputReference(
                    output_type="provider_response", output_id="inactive-output", active=False
                ),
            )
        )

    result = OperationRunner(
        services.repository,
        {OperationType.ANALYZE_JOB: _Handler(execute=execute)},
        runner_id="runner-cancel",
    ).run(operation.id)

    assert result.status is OperationStatus.CANCELLED
    assert result.failure_code is OperationFailureCode.CANCELLED_BEFORE_ACTIVATION
    assert result.outputs[0].active is False


def test_runner_retries_one_transient_failure_and_keeps_technical_detail_out_of_result(
    services,
) -> None:
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

    result = OperationRunner(
        services.repository,
        {OperationType.ANALYZE_JOB: _Handler(execute=execute)},
        runner_id="runner-retry",
        sleeper=delays.append,
    ).run(operation.id)
    assert result.status is OperationStatus.SUCCEEDED
    assert result.attempts_completed == 2
    assert attempts == 2
    assert delays == [0.25]

    failed_operation = _operation_for_runner(services, "Technical Failure Co")
    failed = OperationRunner(
        services.repository,
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
    operation = services.operations.submit_analysis(
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_snapshot_id=ingested.job_snapshot_id,
            provider="openai",
            model="test-model",
        ),
        idempotency_key="unclassified-failure",
        analysis_service=services.analysis,
    )

    completed = foreground_executor(services).execute(operation.id)

    assert completed.status is OperationStatus.FAILED
    assert completed.failure_code is OperationFailureCode.VALIDATION_EXECUTION_FAILED
    assert attempts == 1


def test_foreground_analysis_reuses_an_explicit_idempotency_key(services) -> None:
    ingested = services.applications.ingest(
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
        operation = services.operations.submit_analysis(
            command,
            idempotency_key="analysis-idempotency-key",
            analysis_service=services.analysis,
        )
        return foreground_executor(services).execute(operation.id).id

    first = submit_and_run()
    second = submit_and_run()

    assert first == second
    assert services.repository.operation(first).status is OperationStatus.SUCCEEDED


def test_draft_operation_activates_one_validated_working_draft(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="Draft Operation Co",
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
            client="web",
        )
    )
    analysis = services.analysis.analyze(
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_snapshot_id=ingested.job_snapshot_id,
        )
    )
    operation = services.operations.submit_draft(
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
    working_id = completed.outputs[0].output_id
    assert services.repository.active_working_draft(ingested.application_id).id == working_id
    validation = services.repository.latest_validation_for_working_draft(working_id)
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
    analysis = services.analysis.analyze(
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_snapshot_id=ingested.job_snapshot_id,
        )
    )
    command = DraftCommand(
        application_id=ingested.application_id,
        job_analysis_id=analysis.analysis_id,
        selection_plan_id=analysis.selection_plan_id,
    )
    operation = services.operations.submit_draft(
        command,
        idempotency_key="draft-plan-race",
        draft_service=services.drafts,
    )
    old_plan = services.repository.selection_plan(analysis.selection_plan_id)
    services.repository.create_selection_plan(
        ingested.application_id,
        analysis.analysis_id,
        old_plan.plan,
        candidate_context_version=old_plan.candidate_context_version,
        candidate_context_hash=old_plan.candidate_context_hash,
        profile_version=old_plan.profile_version,
        selection_policy_version=old_plan.selection_policy_version,
        track_emphasis_dependencies=old_plan.track_emphasis_dependencies,
    )

    failed = foreground_executor(services).execute(operation.id)

    assert failed.status is OperationStatus.FAILED
    assert failed.failure_code is OperationFailureCode.SOURCE_CHANGED
    with pytest.raises(UnknownRecord):
        services.repository.active_working_draft(ingested.application_id)


def test_foreground_draft_runs_through_one_operation(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="Foreground Draft Co",
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
            client="web",
        )
    )
    analysed = services.analysis.analyze(
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_snapshot_id=ingested.job_snapshot_id,
        )
    )

    operation = services.operations.submit_draft(
        DraftCommand(
            application_id=ingested.application_id,
            job_analysis_id=analysed.analysis_id,
            selection_plan_id=analysed.selection_plan_id,
        ),
        idempotency_key="foreground-draft-key",
        draft_service=services.drafts,
    )
    completed = foreground_executor(services).execute(operation.id)

    assert completed.status is OperationStatus.SUCCEEDED
    outputs = {output.output_type: output.output_id for output in completed.outputs}
    validation = services.repository.latest_validation_for_working_draft(outputs["working_draft"])
    assert validation is not None
    assert validation["report"].passed


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
    operation = setup.services.operations.submit_render(
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
    assert len(failed.outputs) == 3
    assert all(not output.active for output in failed.outputs)
    for output in failed.outputs:
        assert (
            setup.services.repository.artifact_version(output.output_id)["lifecycle_status"]
            == "rendered-invalid"
        )


def _render_operation(setup, key: str):
    return setup.services.operations.submit_render(
        RenderCommand(
            application_id=setup.application_id,
            approved_revision_id=setup.approved.revision_id,
        ),
        idempotency_key=key,
        rendering_service=setup.services.rendering,
    )


def _cancel_after_render(setup, operation_id: str):
    def interfere(_executed) -> None:
        setup.services.repository.request_operation_cancellation(operation_id)

    return interfere


def _move_the_source_after_render(setup, _operation_id: str):
    def interfere(_executed) -> None:
        manifest = setup.services.repository.artifact_version_for_revision(
            setup.approved.revision_id, "claim_manifest", "approved"
        )
        path = setup.services.artifacts.resolve(manifest["path"])
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
    nowhere, so resolving all three *is* the assertion.
    """
    setup = ready_application(f"Stopped Render {expected_status.value}")
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
        output
        for output in stopped.outputs
        if output.output_type in {"resume_html", "resume_pdf", "visual_evidence"}
    ]
    assert len(outputs) == 3
    assert all(not output.active for output in outputs)
    for output in outputs:
        registered = setup.services.repository.artifact_version(output.output_id)
        assert registered["revision_id"] == setup.approved.revision_id
        assert registered["lifecycle_status"] == "rendered"

    # The post-render ValidationRun belongs to activation and did not happen, so
    # nothing claims these artifacts were checked into Ready. Asserted on the
    # PDF, which is the one an approval or a download would reach for.
    pdf = next(output for output in outputs if output.output_type == "resume_pdf")
    with pytest.raises(UnknownRecord):
        setup.services.repository.validation_for_artifact(
            setup.application_id, "post-render", pdf.output_id
        )


def test_a_failure_partway_through_registration_leaves_no_artifact_at_all(
    ready_application, monkeypatch
) -> None:
    """Three artifacts are one render: all of them are registered, or none is.

    The first repair moved registration into `execute` so the rows survive a
    cancellation. Left as three independent writes that would have bought the
    opposite bug: a failure on the third leaves two rows committed while
    `execute` raises, so the runner records no Operation output at all and the
    Application carries registered artifacts belonging to a render that never
    reported. That is the mirror of the orphan being repaired, and it is not
    reachable through cancellation or `SOURCE_CHANGED`, which is why neither of
    those tests would have found it.

    The third registration is failed deliberately. What is asserted is that the
    first two did not survive it.
    """
    setup = ready_application("Partial Registration Co")
    repository = setup.services.repository
    before = {row["id"] for row in repository.artifact_versions(setup.application_id)}
    operation = _render_operation(setup, "partial-registration")
    # Patched on the class, not on this instance. `bind` returns a *new*
    # repository object wrapping the UnitOfWork's connection, so an
    # instance-level patch is invisible to exactly the code under test - the
    # registrations run on the bound copy.
    original = type(repository).register_artifact_version
    calls = 0

    def fail_on_the_third(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise InfrastructureFailure("injected registry failure")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(type(repository), "register_artifact_version", fail_on_the_third)
    failed = foreground_executor(setup.services).execute(operation.id)

    assert failed.status is OperationStatus.FAILED
    assert calls == 3, "the injected failure never reached the code under test"
    after = {row["id"] for row in repository.artifact_versions(setup.application_id)}
    assert after == before, "a partial render registration survived"
    assert not [
        output
        for output in failed.outputs
        if output.output_type in {"resume_html", "resume_pdf", "visual_evidence"}
    ]


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
    working = setup.services.repository.active_working_draft(setup.application_id)
    command = _approve_command(setup.services, setup.application_id)
    reserved_revision = new_id()
    receipt = setup.services.repository.claim_idempotency_receipt(
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
    committed = setup.services.drafts.approve_draft(command, revision_id=reserved_revision)
    assert receipt["status"] == "pending"

    recovered = setup.services.operations.approve_idempotent(
        command,
        idempotency_key="approval-recovery",
        draft_service=setup.services.drafts,
    )

    assert recovered == committed
    completed = setup.services.repository.idempotency_receipt(
        "approve_draft",
        "approval-recovery",
    )
    assert completed["status"] == "completed"


def test_worker_shutdown_requests_cancellation_and_prevents_activation(services) -> None:
    operation = _operation_for_runner(services, "Worker Shutdown Co")
    started = Event()

    def execute(_operation, cancellation_requested):
        started.set()
        while not cancellation_requested():
            Event().wait(0.01)
        return PreparedOperation()

    runner = OperationRunner(
        services.repository,
        {OperationType.ANALYZE_JOB: _Handler(execute=execute)},
        runner_id="shutdown-worker",
        heartbeat_interval_seconds=0.02,
    )
    worker = OperationWorker(services.repository, runner, concurrency=1, poll_interval_seconds=0.01)
    stop = Event()
    thread = Thread(target=worker.serve, args=(stop,))
    thread.start()
    assert started.wait(timeout=2)

    stop.set()
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert services.repository.operation(operation.id).status is OperationStatus.CANCELLED


# --- repository methods against real PostgreSQL ------------------------------
#
# The tests above drive Operations through the runner and the services, which is
# where the product's behaviour lives. These drive eight repository methods
# directly, because their refusals are the branches a successful run never
# takes: a lease claimed by someone else, an output activated after
# cancellation, a receipt completed twice. Acceptance item 1 asks for the
# repository under real PostgreSQL, and a method whose only coverage is the happy
# path is not covered.


def _queued(services, company: str, key: str = "request-1", created_at: str | None = None):
    ingested = _ingest_for_operation(services, company)
    return services.repository.create_operation(
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
    repository = services.repository
    first = _queued(services, "Queue One", key="queue-1", created_at="2026-08-19T07:00:00+00:00")
    second = _queued(services, "Queue Two", key="queue-2", created_at="2026-08-19T07:00:01+00:00")

    claimed = repository.claim_next_operation(runner_id="runner-a", now="2026-08-19T08:00:00+00:00")
    assert claimed is not None
    assert claimed.id == first.id, "the older queued operation is taken first"

    # A retry that is not due yet is not ready, so the queue skips past it.
    repository.record_operation_attempt(
        first.id, runner_id="runner-a", retry_at="2026-08-19T09:00:00+00:00"
    )
    again = repository.claim_next_operation(runner_id="runner-b", now="2026-08-19T08:00:00+00:00")
    assert again is not None
    assert again.id == second.id

    assert (
        repository.claim_next_operation(runner_id="runner-c", now="2026-08-19T08:00:00+00:00")
        is None
    ), "an empty ready queue returns None rather than blocking or raising"


def test_lease_owning_methods_refuse_a_runner_that_does_not_hold_the_lease(services) -> None:
    """One contract, five entry points.

    Each of these updates `WHERE status='running' AND lease_owner=?` and raises
    when that matches nothing. Parameterised over the calls rather than written
    five times, so a sixth lease-owning method is one line.
    """
    repository = services.repository
    operation = _queued(services, "Lease Co")
    repository.claim_operation(operation.id, runner_id="owner", now="2026-08-19T08:00:00+00:00")

    calls = {
        "set_operation_phase": lambda runner: repository.set_operation_phase(
            operation.id, OperationPhase.EXECUTING, runner_id=runner
        ),
        "record_operation_attempt": lambda runner: repository.record_operation_attempt(
            operation.id, runner_id=runner
        ),
        "heartbeat_operation": lambda runner: repository.heartbeat_operation(
            operation.id, runner_id=runner
        ),
        "fail_operation": lambda runner: repository.fail_operation(
            operation.id,
            OperationFailureCode.PROVIDER_UNAVAILABLE,
            "provider down",
            runner_id=runner,
        ),
        "complete_operation": lambda runner: repository.complete_operation(
            operation.id, runner_id=runner
        ),
    }
    for name, call in calls.items():
        with pytest.raises(StateConflict, match="lease is not owned"):
            call("impostor")
        assert repository.operation(operation.id).status is OperationStatus.RUNNING, (
            f"{name} must not change the operation when it refuses"
        )

    assert repository.record_operation_attempt(operation.id, runner_id="owner") == 1
    assert repository.operation(operation.id).phase is OperationPhase.RETRY_WAIT


def test_completing_a_cancelled_operation_records_cancellation_not_success(services) -> None:
    repository = services.repository
    operation = _queued(services, "Cancel Co")
    repository.claim_operation(operation.id, runner_id="owner", now="2026-08-19T08:00:00+00:00")
    repository.request_operation_cancellation(operation.id)

    completed = repository.complete_operation(operation.id, runner_id="owner")
    assert completed.status is OperationStatus.CANCELLED
    assert completed.failure_code is OperationFailureCode.CANCELLED_BEFORE_ACTIVATION
    assert completed.finished_at


def test_outputs_cannot_be_activated_once_the_operation_stops_running(services) -> None:
    repository = services.repository
    operation = _queued(services, "Output Co")
    repository.claim_operation(operation.id, runner_id="owner", now="2026-08-19T08:00:00+00:00")

    repository.record_operation_output(operation.id, "analysis", "analysis-1")
    repository.activate_operation_output(operation.id, "analysis", "analysis-1")
    with pytest.raises(StateConflict, match="cannot be activated"):
        repository.activate_operation_output(operation.id, "analysis", "analysis-1")
    with pytest.raises(StateConflict, match="cannot be activated"):
        repository.activate_operation_output(operation.id, "analysis", "never-recorded")

    with pytest.raises(UnknownRecord):
        repository.record_operation_output("no-such-operation", "analysis", "analysis-2")

    # Cancellation closes the window: an output may still be recorded, but not
    # activated, which is what keeps a cancelled run from taking effect.
    repository.request_operation_cancellation(operation.id)
    repository.record_operation_output(operation.id, "analysis", "analysis-3")
    with pytest.raises(StateConflict, match="cannot be activated"):
        repository.record_operation_output(operation.id, "analysis", "analysis-4", active=True)
