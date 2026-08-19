from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from pydantic import ValidationError

from cv_engine.application.commands import IngestCommand
from cv_engine.application.errors import StateConflict
from cv_engine.application.operations import (
    CreateOperation,
    OperationContractError,
    OperationFailureCode,
    OperationOutputReference,
    OperationSources,
    OperationStatus,
    OperationType,
    allows_automatic_retry,
    is_terminal_operation,
    require_operation_transition,
)
from cv_engine.application.operation_runner import (
    OperationExecutionError,
    OperationRunner,
    PreparedOperation,
    SourceChanged,
)
from cv_engine.infrastructure.persistence import Repository


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (OperationStatus.QUEUED, OperationStatus.RUNNING),
        (OperationStatus.QUEUED, OperationStatus.CANCELLED),
        (OperationStatus.QUEUED, OperationStatus.INTERRUPTED),
        (OperationStatus.RUNNING, OperationStatus.SUCCEEDED),
        (OperationStatus.RUNNING, OperationStatus.FAILED),
        (OperationStatus.RUNNING, OperationStatus.CANCELLED),
        (OperationStatus.RUNNING, OperationStatus.INTERRUPTED),
    ],
)
def test_operation_lifecycle_accepts_only_forward_transitions(current, target) -> None:
    require_operation_transition(current, target)


@pytest.mark.parametrize("terminal", list(OperationStatus)[2:])
def test_terminal_operations_are_immutable(terminal) -> None:
    assert is_terminal_operation(terminal)
    for target in OperationStatus:
        with pytest.raises(OperationContractError):
            require_operation_transition(terminal, target)


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


def test_working_draft_optimistic_identity_is_all_or_nothing() -> None:
    with pytest.raises(ValidationError, match="requires id, edit version, and content hash"):
        OperationSources(working_draft_id="draft-id", working_draft_edit_version=1)


@pytest.mark.parametrize(
    "code",
    [
        OperationFailureCode.PROVIDER_TIMEOUT,
        OperationFailureCode.PROVIDER_RATE_LIMITED,
        OperationFailureCode.PROVIDER_UNAVAILABLE,
        OperationFailureCode.BROWSER_START_FAILED,
    ],
)
def test_only_one_automatic_retry_is_allowed_for_transient_failures(code) -> None:
    assert allows_automatic_retry(code, attempts_completed=1)
    assert not allows_automatic_retry(code, attempts_completed=2)
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


def test_sqlite_operation_creation_is_idempotent_and_projects_active_work(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(company="Operation Co", target_role="Developer", job_text="Python role")
    )
    request = _stored_request(ingested.application_id)

    created = services.repository.create_operation(
        request,
        installation_id=services.workspace.installation_id(),
        operation_id="operation-id",
        created_at="2026-08-19T08:00:00+00:00",
    )
    repeated = services.repository.create_operation(
        request,
        installation_id=services.workspace.installation_id(),
        operation_id="ignored-id",
    )

    assert repeated == created
    assert created.payload_hash == request.payload_hash
    assert created.status is OperationStatus.QUEUED
    assert services.repository.operation(created.id) == created
    assert services.repository.active_operation(ingested.application_id).id == created.id
    detail = services.queries.application_detail(ingested.application_id)
    assert detail.active_operation["id"] == created.id
    assert detail.active_operation["status"] == "queued"


def test_sqlite_operation_rejects_idempotency_key_with_another_payload(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(company="Conflict Co", target_role="Developer", job_text="Python role")
    )
    request = _stored_request(ingested.application_id)
    services.repository.create_operation(
        request,
        installation_id=services.workspace.installation_id(),
    )
    conflicting = request.model_copy(update={"payload": {"mode": "ai"}})

    with pytest.raises(StateConflict, match="IDEMPOTENCY_KEY_REUSED"):
        services.repository.create_operation(
            conflicting,
            installation_id=services.workspace.installation_id(),
        )


def test_terminal_operation_rows_cannot_be_rewritten_or_deleted(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(company="Immutable Op Co", target_role="Developer", job_text="Python role")
    )
    created = services.repository.create_operation(
        _stored_request(ingested.application_id),
        installation_id=services.workspace.installation_id(),
    )
    with services.repository.transaction() as connection:
        connection.execute(
            "UPDATE operations SET status='cancelled', phase='completed', finished_at=? "
            "WHERE id=?",
            ("2026-08-19T08:01:00+00:00", created.id),
        )

    with pytest.raises(sqlite3.IntegrityError, match="immutable terminal operation"):
        with services.repository.transaction() as connection:
            connection.execute(
                "UPDATE operations SET message='rewritten' WHERE id=?", (created.id,)
            )
    with pytest.raises(sqlite3.IntegrityError, match="immutable record"):
        with services.repository.transaction() as connection:
            connection.execute("DELETE FROM operations WHERE id=?", (created.id,))


def test_two_runners_racing_one_operation_produce_one_claim(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(company="Claim Race Co", target_role="Developer", job_text="Python role")
    )
    created = services.repository.create_operation(
        _stored_request(ingested.application_id),
        installation_id=services.workspace.installation_id(),
    )
    barrier = Barrier(2)

    def claim(runner_id: str):
        repository = Repository(services.workspace.database_path)
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


def test_application_and_global_render_leases_queue_contending_work(services) -> None:
    first = services.applications.ingest(
        IngestCommand(company="Lease A", target_role="Developer", job_text="Python role")
    )
    second = services.applications.ingest(
        IngestCommand(company="Lease B", target_role="Developer", job_text="Python role")
    )
    installation = services.workspace.installation_id()
    app_one = services.repository.create_operation(
        _stored_request(first.application_id, "app-1"), installation_id=installation
    )
    same_app = services.repository.create_operation(
        _stored_request(first.application_id, "app-2"), installation_id=installation
    )
    render_request = CreateOperation(
        application_id=second.application_id,
        operation_type=OperationType.RENDER_REVISION,
        payload={"approved_revision_id": "revision-1"},
        idempotency_key="render-1",
        sources=OperationSources(approved_revision_id="revision-1"),
    )
    render_one = services.repository.create_operation(
        render_request, installation_id=installation
    )
    third = services.applications.ingest(
        IngestCommand(company="Lease C", target_role="Developer", job_text="Python role")
    )
    render_two = services.repository.create_operation(
        render_request.model_copy(
            update={
                "application_id": third.application_id,
                "idempotency_key": "render-2",
            }
        ),
        installation_id=installation,
    )

    assert services.repository.claim_operation(app_one.id, runner_id="runner-a") is not None
    assert services.repository.claim_operation(same_app.id, runner_id="runner-b") is None
    assert services.repository.operation(same_app.id).phase.value == "waiting_for_application"
    assert services.repository.claim_operation(render_one.id, runner_id="runner-b") is not None
    assert services.repository.claim_operation(render_two.id, runner_id="runner-c") is None
    assert services.repository.operation(render_two.id).phase.value == "waiting_for_render_slot"


def test_heartbeat_prevents_interruption_until_extended_lease_expires(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(company="Heartbeat Co", target_role="Developer", job_text="Python role")
    )
    created = services.repository.create_operation(
        _stored_request(ingested.application_id),
        installation_id=services.workspace.installation_id(),
    )
    claimed = services.repository.claim_operation(
        created.id,
        runner_id="runner-a",
        lease_seconds=30,
        now="2026-08-19T08:00:00+00:00",
    )
    assert claimed is not None
    assert services.repository.interrupt_expired_operations(
        now="2026-08-19T08:00:20+00:00"
    ) == []

    services.repository.heartbeat_operation(
        created.id,
        runner_id="runner-a",
        lease_seconds=30,
        now="2026-08-19T08:00:20+00:00",
    )
    assert services.repository.interrupt_expired_operations(
        now="2026-08-19T08:00:49+00:00"
    ) == []
    assert services.repository.interrupt_expired_operations(
        now="2026-08-19T08:00:51+00:00"
    ) == [created.id]
    assert services.repository.operation(created.id).status is OperationStatus.INTERRUPTED


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


def _operation_for_runner(services, company: str = "Runner Co"):
    ingested = services.applications.ingest(
        IngestCommand(company=company, target_role="Developer", job_text="Python role")
    )
    operation = services.repository.create_operation(
        _stored_request(ingested.application_id, company.casefold().replace(" ", "-")),
        installation_id=services.workspace.installation_id(),
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
        runner_id="foreground-cli",
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

        def check(_operation, _repository):
            nonlocal checks
            checks += 1
            if checks == fail_on_check:
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
        technical_logger=lambda error: "logs/operation-failure.jsonl",
    ).run(failed_operation.id)
    assert failed.status is OperationStatus.FAILED
    assert failed.safe_failure_detail == "Operation execution failed."
    assert "secret traceback" not in failed.safe_failure_detail
    assert failed.technical_log_reference == "logs/operation-failure.jsonl"
