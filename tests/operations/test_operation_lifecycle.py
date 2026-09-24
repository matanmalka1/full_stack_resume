from __future__ import annotations

import pytest
from foreground import foreground_executor
from helpers import (
    ACCOUNT_MANAGER_JOB,
    analysis_proposal,
)
from operations_support import (
    _claim_operation,
    _enqueue_operation,
    _execution_write,
    _Handler,
    _ingest_for_operation,
    _operation,
    _operation_for_runner,
    _runner,
    _stored_request,
)
from pydantic import ValidationError
from sqlalchemy import delete, update
from sqlalchemy.exc import ProgrammingError

from cv_engine.application.commands import (
    AnalyzeCommand,
    IngestCommand,
)
from cv_engine.application.errors import (
    IDEMPOTENCY_KEY_REUSED,
    InfrastructureFailure,
    StateConflict,
    UnknownRecord,
)
from cv_engine.application.operation_runner import (
    OperationExecutionError,
    PreparedOperation,
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
from cv_engine.infrastructure.persistence.application_projections import (
    SqlAlchemyApplicationProjectionReader,
)
from cv_engine.infrastructure.persistence.tables import (
    OPERATION_FAILURE_CODES,
    operations,
)
from cv_engine.util import new_id


def _active_operation(services, *args):
    transactions = services.operation_runner.transactions
    with transactions.read() as tx:
        return SqlAlchemyApplicationProjectionReader(transactions).active_operation(tx, *args)


def _claim_next_operation(services, **options):
    with services.operation_runner.transactions.write() as tx:
        return services.operation_runner.execution_store.claim_next_operation(tx, **options)


def test_operation_lifecycle_transitions_are_forward_only_and_terminal_is_final() -> None:
    """The domain transition table: forward only, terminal is final, actions derived.

    Queued and running move forward to their listed targets; every terminal status
    refuses every transition; and the actions a status offers are derived from the
    lifecycle, including the terminal failures no retry can fix.
    """
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

    for terminal in list(OperationStatus)[2:]:
        assert is_terminal_operation(terminal)
        for target in OperationStatus:
            with pytest.raises(OperationContractError):
                require_operation_transition(terminal, target)

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


_OPERATION_ACTION_CASES = [
    (OperationStatus.QUEUED, None, None, (OperationAction.CANCEL,)),
    (OperationStatus.RUNNING, None, None, (OperationAction.CANCEL,)),
    (OperationStatus.RUNNING, "2026-08-24T07:01:00Z", None, ()),
    (OperationStatus.FAILED, None, None, (OperationAction.RETRY,)),
    (OperationStatus.SUCCEEDED, None, None, (OperationAction.RETRY,)),
    (OperationStatus.CANCELLED, None, None, (OperationAction.RETRY,)),
    (OperationStatus.INTERRUPTED, None, None, (OperationAction.RETRY,)),
]


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


def test_failure_classification_and_retry_budget(
    services,
    monkeypatch,
) -> None:
    """Failure classification and the retry budget, from the policy to the runner.

    Only the four transient codes earn one automatic retry. The runner takes it
    after a transient failure; an unclassified exception keeps its detail out of
    the result; and an unclassified infrastructure failure is the default arm,
    `VALIDATION_EXECUTION_FAILED`, and stops on the first attempt - which is what
    stops a message that merely *reads* like a timeout from buying a second
    provider call.
    """
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


def test_operation_creation_is_idempotent_by_key_and_projects_active_work(
    services,
    ai_services,
    fake_openai,
    requirement_concepts,
) -> None:
    """One idempotency key names one request, and replaying it is the same Operation.

    Creation with the same key returns the stored Operation and projects it as the
    active work; the same key with another payload is refused with the contracted
    code rather than prose; and a foreground run reuses an explicit key end to end.
    """
    ingested = services.applications.ingest(
        IngestCommand(
            company="Operation Co", target_role="Developer", job_text="Python role", client="web"
        )
    )
    request = _stored_request(ingested.application_id)

    operation_id = new_id()
    created = _enqueue_operation(
        services,
        request,
        operation_id=operation_id,
        created_at="2026-08-19T08:00:00+00:00",
    )
    repeated = _enqueue_operation(
        services,
        request,
        operation_id=new_id(),
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

    ingested = services.applications.ingest(
        IngestCommand(
            company="Conflict Co",
            target_role="Developer",
            job_text="Python role",
            acknowledged_duplicates=True,
            client="web",
        )
    )
    request = _stored_request(ingested.application_id, key="conflict-request")
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


def test_output_after_cancellation_stays_inactive_and_cannot_be_activated(
    services,
) -> None:
    """Output after cancellation stays inactive and can never be activated later.

    An output the runner created after cancellation is recorded inactive. At the
    store, completing a cancelled Operation records cancellation rather than
    success, and neither activation nor `active=True` on recording can bring an
    output back once cancellation closed the window.
    """
    operation = _operation_for_runner(services, "Cancel Output Co")
    inactive_output_id = new_id()

    def execute(_operation, _cancelled):
        services.operation_lifecycle.cancel(operation.id)
        return PreparedOperation(
            outputs=(
                OperationOutputReference(
                    output_type="provider_response", output_id=inactive_output_id, active=False
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

    operation = _queued(services, "Cancel Co", key="cancel-request")
    _claim_operation(services, operation.id, runner_id="owner", now="2026-08-19T08:00:00+00:00")
    services.operation_lifecycle.cancel(operation.id)

    completed = _execution_write(services, "complete_operation", operation.id, runner_id="owner")
    assert completed.status is OperationStatus.CANCELLED
    assert completed.failure_code is OperationFailureCode.CANCELLED_BEFORE_ACTIVATION
    assert completed.finished_at

    operation = _queued(services, "Output Co", key="output-request")
    _claim_operation(services, operation.id, runner_id="owner", now="2026-08-19T08:00:00+00:00")

    output_id = new_id()
    _execution_write(services, "record_operation_output", operation.id, "analysis", output_id)
    _execution_write(services, "activate_operation_output", operation.id, "analysis", output_id)
    with pytest.raises(StateConflict, match="cannot be activated"):
        _execution_write(services, "activate_operation_output", operation.id, "analysis", output_id)
    with pytest.raises(StateConflict, match="cannot be activated"):
        _execution_write(services, "activate_operation_output", operation.id, "analysis", new_id())

    with pytest.raises(UnknownRecord):
        _execution_write(services, "record_operation_output", new_id(), "analysis", new_id())

    # Cancellation closes the window: an output may still be recorded, but it
    # cannot be activated either by the activation method or by active=True on
    # the recording method.
    services.operation_lifecycle.cancel(operation.id)
    cancelled_output_id = new_id()
    _execution_write(
        services, "record_operation_output", operation.id, "analysis", cancelled_output_id
    )
    with pytest.raises(StateConflict, match="cannot be activated"):
        _execution_write(
            services, "activate_operation_output", operation.id, "analysis", cancelled_output_id
        )
    with pytest.raises(StateConflict, match="cannot be activated"):
        _execution_write(
            services, "record_operation_output", operation.id, "analysis", new_id(), active=True
        )


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
