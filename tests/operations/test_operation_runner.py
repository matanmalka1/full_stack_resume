from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock, Thread
from time import monotonic

import pytest
from foreground import ForegroundOperationExecutor, foreground_executor
from helpers import (
    edit_document_claim,
    seed_document,
    seed_draft,
    seed_existing_analysis,
    stored_document,
)
from operations_support import (
    _claim_operation,
    _enqueue_operation,
    _execution_write,
    _Handler,
    _held_slot,
    _operation,
    _operation_for_runner,
    _runner,
    _stored_request,
)
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError

import cv_engine.infrastructure.rendering as rendering_adapter
from cv_engine.application.commands import (
    AnalyzeCommand,
    ApproveDocumentCommand,
    BuildFromAnalysisCommand,
    DraftCommand,
    IngestCommand,
    RenderCommand,
    UpdateDocumentCommand,
)
from cv_engine.application.errors import (
    MissingFactRendering,
    PreconditionFailed,
    StateConflict,
)
from cv_engine.application.operation_runner import (
    PreparedOperation,
    SourceChanged,
    WorkerAlreadyRunning,
    WorkerLockLost,
)
from cv_engine.application.operations import (
    CreateOperation,
    MissingFactRenderingReason,
    OperationFailureCode,
    OperationOutputReference,
    OperationPhase,
    OperationSources,
    OperationStatus,
    OperationType,
)
from cv_engine.domain.document import PreparationState
from cv_engine.infrastructure.operation_logging import OperationFailureLogger
from cv_engine.infrastructure.persistence.connection import SqlAlchemyTransactionManager
from cv_engine.infrastructure.persistence.operation_execution import (
    SqlAlchemyOperationExecutionStore,
    _lost_claim,
)
from cv_engine.infrastructure.persistence.tables import operations
from cv_engine.infrastructure.persistence.worker_lock import (
    WORKER_LOCK_KEY,
    worker_exclusivity,
)
from cv_engine.runtime.composition import Services
from cv_engine.runtime.execution import OperationWorker
from cv_engine.util import new_id


def test_racing_claimants_produce_one_claim_and_one_execution(
    services,
    database_engine,
) -> None:
    """Contending claimants produce one claim and one execution.

    Two runners racing one Operation get one claim, and the loser writes nothing. The
    two concrete hosts - foreground executor and worker - contend
    through the same durable claim contract and execute once.
    """
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
    stored = _operation(services, created.id)
    assert stored.status is OperationStatus.RUNNING
    assert stored.lease_owner == winner.lease_owner, "the loser must not overwrite the claim"

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
        exclusive=_held_slot,
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
        exclusive=_held_slot,
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
    # A claim moves the Operation straight to `executing`; nothing between the claim
    # and the end of the run writes a phase, so nothing logs one.
    assert [entry["event"] for entry in entries] == ["operation.claimed", "operation.succeeded"]
    assert entries[0]["phase"] == OperationPhase.EXECUTING.value
    assert all(entry["operation_id"] == operation.id for entry in entries)
    assert entries[-1]["duration_ms"] >= 0


def _application(services, company: str) -> str:
    return services.applications.ingest(
        IngestCommand(
            company=company,
            target_role="Developer",
            job_text="Python role",
            acknowledged_duplicates=True,
            client="web",
        )
    ).application_id


def _render_request(application_id: str, key: str) -> CreateOperation:
    return CreateOperation(
        application_id=application_id,
        operation_type=OperationType.RENDER_DOCUMENT,
        payload={"expected_document_hash": "a" * 64},
        idempotency_key=key,
        sources=OperationSources(expected_document_hash="a" * 64),
    )


def _concurrent_claims(database_engine, claims):
    """Run each `(runner_id, operation_id | None)` claim on its own connection at once.

    `None` claims the next ready Operation, as the worker does. Each claimant has
    its own transaction manager, so the race is between PostgreSQL sessions and
    the claim guards decide it, not anything in this process.
    """
    barrier = Barrier(len(claims))

    def claim(runner_id: str, operation_id: str | None):
        transactions = SqlAlchemyTransactionManager(database_engine)
        execution = SqlAlchemyOperationExecutionStore(transactions)
        barrier.wait(timeout=5)
        with transactions.write() as tx:
            if operation_id is None:
                return execution.claim_next_operation(tx, runner_id=runner_id)
            return execution.claim_operation(tx, operation_id, runner_id=runner_id)

    with ThreadPoolExecutor(max_workers=len(claims)) as pool:
        futures = [pool.submit(claim, runner, operation_id) for runner, operation_id in claims]
        return [future.result(timeout=10) for future in futures]


def test_claim_guards_queue_contending_work_and_derive_the_waiting_phase(services) -> None:
    """One running Operation per Application and one running render, as read phases.

    A refused claim writes nothing: the waiting phase is read from what is running,
    so it is exact while the blocker runs and gone the moment it stops.
    """
    first = _application(services, "Guard A")
    second = _application(services, "Guard B")
    third = _application(services, "Guard C")
    app_one = _enqueue_operation(services, _stored_request(first, "app-1"))
    same_app = _enqueue_operation(services, _stored_request(first, "app-2"))
    render_one = _enqueue_operation(services, _render_request(second, "render-1"))
    render_two = _enqueue_operation(services, _render_request(third, "render-2"))

    assert _operation(services, same_app.id).phase is OperationPhase.QUEUED
    assert _claim_operation(services, app_one.id, runner_id="runner-a") is not None
    assert _claim_operation(services, same_app.id, runner_id="runner-b") is None
    assert _operation(services, same_app.id).phase is OperationPhase.WAITING_FOR_APPLICATION
    assert _claim_operation(services, render_one.id, runner_id="runner-b") is not None
    assert _claim_operation(services, render_two.id, runner_id="runner-c") is None
    assert _operation(services, render_two.id).phase is OperationPhase.WAITING_FOR_RENDER_SLOT

    _execution_write(services, "complete_operation", render_one.id, runner_id="runner-b")
    assert _operation(services, render_two.id).phase is OperationPhase.QUEUED
    assert _claim_operation(services, render_two.id, runner_id="runner-c") is not None


def test_racing_claims_admit_one_per_application_and_one_render(services, database_engine) -> None:
    """Concurrent sessions: the database admits exactly one where a guard applies.

    Two Operations of one Application, and two renders of different Applications,
    each produce exactly one claim. An AI Operation and a render of different
    Applications contend for nothing and both run. Each case races twice: once by
    Operation identifier (the foreground host) and once through the worker's
    next-ready claim.
    """
    for by_id in (True, False):
        tag = "id" if by_id else "next"
        app = _application(services, f"Race Same {tag}")
        same = [
            _enqueue_operation(services, _stored_request(app, f"same-{tag}-{n}")) for n in (1, 2)
        ]
        claimed = _concurrent_claims(
            database_engine,
            [(f"same-{tag}-{n}", same[n].id if by_id else None) for n in (0, 1)],
        )
        assert len([result for result in claimed if result is not None]) == 1
        _finish_running(services, database_engine)

        renders = [
            _enqueue_operation(
                services,
                _render_request(_application(services, f"Race Render {tag} {n}"), f"r-{tag}-{n}"),
            )
            for n in (1, 2)
        ]
        claimed = _concurrent_claims(
            database_engine,
            [(f"render-{tag}-{n}", renders[n].id if by_id else None) for n in (0, 1)],
        )
        assert len([result for result in claimed if result is not None]) == 1
        _finish_running(services, database_engine)

        ai = _enqueue_operation(
            services,
            _stored_request(_application(services, f"Race AI {tag}"), f"ai-{tag}").model_copy(
                update={"provider": "openai", "model": "test-model"}
            ),
        )
        render = _enqueue_operation(
            services,
            _render_request(_application(services, f"Race Mixed {tag}"), f"mixed-{tag}"),
        )
        claimed = _concurrent_claims(
            database_engine,
            [
                (f"ai-{tag}", ai.id if by_id else None),
                (f"mixed-{tag}", render.id if by_id else None),
            ],
        )
        assert {result.id for result in claimed if result is not None} == {ai.id, render.id}
        _finish_running(services, database_engine)


def _finish_running(services, database_engine) -> None:
    """End every running Operation through its runner and cancel what lost, between cases."""
    with database_engine.connect() as connection:
        rows = connection.execute(
            select(operations.c.id, operations.c.status, operations.c.lease_owner).where(
                operations.c.status.in_(("queued", "running"))
            )
        ).all()
    for operation_id, status, owner in rows:
        if status == "running":
            _execution_write(services, "complete_operation", operation_id, runner_id=owner)
        else:
            services.operation_lifecycle.cancel(operation_id)


def test_a_claim_refused_by_a_guard_moves_on_to_the_next_candidate(
    services, database_engine
) -> None:
    """A loser waits only for the winner's commit, then claims other work.

    The rival holds the first Operation of an Application in an uncommitted claim.
    The next-ready claim cannot see it running yet, so it tries the second
    Operation of that Application: the unique check waits for the rival's commit,
    fails on the Application guard, rolls back to its savepoint, and claims the
    unrelated Operation behind it in the same transaction.
    """
    busy = _application(services, "Moves On Busy")
    free = _application(services, "Moves On Free")
    held = _enqueue_operation(
        services, _stored_request(busy, "held"), created_at="2026-08-19T07:00:00+00:00"
    )
    blocked = _enqueue_operation(
        services, _stored_request(busy, "blocked"), created_at="2026-08-19T07:00:01+00:00"
    )
    other = _enqueue_operation(
        services, _stored_request(free, "other"), created_at="2026-08-19T07:00:02+00:00"
    )

    rival = SqlAlchemyTransactionManager(database_engine)
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        with rival.write() as tx:
            store = SqlAlchemyOperationExecutionStore(rival)
            assert store.claim_operation(tx, held.id, runner_id="rival") is not None
            loser = pool.submit(lambda: _concurrent_claims(database_engine, [("loser", None)])[0])
            _wait_for_a_lock_wait(database_engine)
            # Leaving the block commits the rival's claim, which releases the waiter.
        claimed = loser.result(timeout=10)
    finally:
        pool.shutdown(wait=False)

    assert claimed is not None and claimed.id == other.id
    assert _operation(services, blocked.id).status is OperationStatus.QUEUED
    assert _operation(services, blocked.id).phase is OperationPhase.WAITING_FOR_APPLICATION


def _wait_for_a_lock_wait(database_engine, timeout: float = 5.0) -> None:
    """Block until some session waits on a lock - the loser on the rival's row."""
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        # A fresh transaction each poll: pg_stat_activity is a snapshot that stays
        # fixed for the rest of the transaction that first reads it.
        with database_engine.connect() as connection:
            waiting = connection.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND wait_event_type = 'Lock'"
                )
            ).scalar_one()
        if waiting:
            return
        Event().wait(0.02)
    raise AssertionError("the losing claim never waited on the rival's uncommitted row")


@pytest.mark.parametrize(
    ("sqlstate", "constraint", "lost"),
    [
        ("40001", None, True),
        ("23505", "uq_operations_running_application", True),
        ("23505", "uq_operations_running_render", True),
        ("23505", "uq_operations_operation_type_idempotency_key", False),
        ("23503", None, False),
    ],
)
def test_only_a_serialization_failure_or_a_claim_guard_is_a_lost_claim(
    sqlstate, constraint, lost
) -> None:
    """Any other unique violation is a real error, never swallowed as a lost race."""

    class Diag:
        constraint_name = constraint

    class Orig(Exception):
        diag = Diag()

    Orig.sqlstate = sqlstate
    error = DBAPIError("UPDATE operations", {}, Orig())
    assert _lost_claim(error) is lost


def test_startup_interrupts_work_held_by_previous_runners_and_one_worker_runs(
    services,
    database_engine,
) -> None:
    """Startup interrupts every running Operation, which is safe only with one worker.

    A running row belongs to a worker that no longer exists; only a running row can
    hold a lease, which the schema enforces. A queued Operation is left for the new
    worker. The advisory lock is what makes "no other worker is alive" true: a
    second holder is refused, and the slot frees when the first lets go.
    """
    running = _operation_for_runner(services, "Claimed Running Co")
    waiting = _operation_for_runner(services, "Unclaimed Co")
    with pytest.raises(IntegrityError, match="ck_operations_running_lease"):
        with database_engine.begin() as connection:
            connection.execute(
                update(operations)
                .where(operations.c.id == waiting.id)
                .values(lease_owner="dead-runner")
            )
    with database_engine.begin() as connection:
        connection.execute(
            update(operations)
            .where(operations.c.id == running.id)
            .values(status="running", lease_owner="dead-runner")
        )

    interrupted = _execution_write(services, "interrupt_claims_from_previous_runners")

    assert interrupted == [running.id]
    assert _operation(services, running.id).status is OperationStatus.INTERRUPTED
    assert _operation(services, waiting.id).status is OperationStatus.QUEUED

    with worker_exclusivity(database_engine):
        with pytest.raises(WorkerAlreadyRunning):
            with worker_exclusivity(database_engine):
                pass
    with worker_exclusivity(database_engine):
        pass


def test_worker_stops_when_its_lock_session_ends(services, database_engine) -> None:
    """Losing the lock session ends the worker instead of leaving it unguarded.

    PostgreSQL releases a session advisory lock with its session. A worker that
    kept claiming after that would be running beside whichever worker takes the
    lock next, so it stops, and the slot is free for that next worker.
    """
    worker = OperationWorker(
        _runner(services, {}, runner_id="lock-loser"),
        request_cancellation=services.operation_lifecycle.cancel,
        exclusive=lambda: worker_exclusivity(database_engine),
        concurrency=1,
        poll_interval_seconds=0.01,
        slot_check_interval_seconds=0,
    )
    errors: list[BaseException] = []
    stop = Event()

    def serve() -> None:
        try:
            worker.serve(stop)
        except BaseException as error:
            errors.append(error)

    # pg_locks spans the cluster; only this database's worker lock is the subject.
    lock_session = text(
        "SELECT pid FROM pg_locks WHERE locktype = 'advisory' AND granted "
        "AND database = (SELECT oid FROM pg_database WHERE datname = current_database()) "
        "AND classid = :high AND objid = :low AND objsubid = 1"
    )
    key = {"high": WORKER_LOCK_KEY >> 32, "low": WORKER_LOCK_KEY & 0xFFFFFFFF}
    thread = Thread(target=serve)
    thread.start()
    try:
        pid = None
        for _attempt in range(200):
            with database_engine.connect() as connection:
                pid = connection.execute(lock_session, key).scalar_one_or_none()
            if pid is not None:
                break
            Event().wait(0.01)
        assert pid is not None, "the worker never took its lock"

        with database_engine.connect() as connection:
            connection.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid})
            connection.commit()
        thread.join(timeout=5)
    finally:
        # Never leave a worker behind: it would claim the next tests' Operations.
        stop.set()
        thread.join(timeout=5)

    assert not thread.is_alive(), "the worker kept running without its lock"
    assert len(errors) == 1 and isinstance(errors[0], WorkerLockLost)
    with worker_exclusivity(database_engine):
        pass


def test_runner_activates_outputs_and_completes_in_one_activation_transaction(services) -> None:
    operation = _operation_for_runner(services)
    output_id = new_id()
    runner = _runner(
        services,
        {
            OperationType.ANALYZE_JOB: _Handler(
                execute=lambda *_args: PreparedOperation(value={"proposal": "validated"}),
                activate=lambda *_args: (
                    OperationOutputReference(output_type="job_analysis", output_id=output_id),
                ),
            )
        },
        runner_id="foreground-test",
    )

    result = runner.run(operation.id)

    assert result.status is OperationStatus.SUCCEEDED
    assert [item.output_id for item in result.outputs] == [output_id]


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

    def prepare_that_fails(_command, *, operation_id=None, still_owned=None):
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
    # The same reason, structured, as read back from the database.
    assert completed.failure_reason == MissingFactRenderingReason(
        fact_id="situational.agentic_multi_agent", language="he"
    )
    assert completed.outputs == []
    with pytest.raises(StateConflict, match="cannot be retried"):
        services.operation_lifecycle.retry(completed.id, idempotency_key="meaningless-retry")
    assert attempts == 1


def _runner_touches_row(database_engine, operation_id: str) -> None:
    with database_engine.begin() as connection:
        connection.execute(
            update(operations)
            .where(operations.c.id == operation_id, operations.c.status == "running")
            .values(message="")
        )


def test_worker_shutdown_requests_cancellation_and_prevents_activation(
    services, monkeypatch, database_engine
) -> None:
    operation = _operation_for_runner(services, "Worker Shutdown Co")
    started = Event()
    original_cancel = services.operation_lifecycle.operations.request_cancellation
    cancellation_attempts = []

    def cancel_after_runner_write(tx, operation_id):
        cancellation_attempts.append(operation_id)
        if len(cancellation_attempts) == 1:
            # Establish the cancellation snapshot, then commit a runner write to the
            # row on another connection. It must force cancellation to retry.
            services.operation_runner.execution_store.operation(tx, operation_id)
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(_runner_touches_row, database_engine, operation_id).result(timeout=2)
        return original_cancel(tx, operation_id)

    monkeypatch.setattr(
        services.operation_lifecycle.operations, "request_cancellation", cancel_after_runner_write
    )

    def execute(_operation, still_owned):
        started.set()
        while still_owned():
            Event().wait(0.01)
        return PreparedOperation()

    runner = _runner(
        services,
        {OperationType.ANALYZE_JOB: _Handler(execute=execute)},
        runner_id="shutdown-worker",
    )
    worker = OperationWorker(
        runner,
        request_cancellation=services.operation_lifecycle.cancel,
        exclusive=_held_slot,
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


def _run(services: Services, operation_id: str):
    return ForegroundOperationExecutor(services.operation_runner).execute(operation_id)


def _submit_draft(services: Services, application_id: str, document_hash: str):
    return services.operation_submissions.submit_draft(
        DraftCommand(application_id=application_id, expected_document_hash=document_hash),
        idempotency_key=new_id(),
        draft_service=services.drafts,
    )


@pytest.mark.parametrize("race_phase", ["queued", "prepared"])
def test_create_draft_activates_only_against_the_hash_it_froze(
    ai_services: Services, fake_openai, monkeypatch, race_phase
) -> None:
    """A document change before execution or activation yields SOURCE_CHANGED.

    The failure is not retryable; a new Operation against the current hash is how
    the user continues, and it writes the content.
    """
    services = ai_services
    ingested, _analysis = seed_document(services, "Race Co")
    application_id = ingested.application_id
    document = stored_document(services, application_id)
    fake_openai.script_draft()
    queued = _submit_draft(services, application_id, document.document_hash)

    def move_document():
        newer = seed_existing_analysis(services, ingested)
        services.repin.build_from_analysis(
            BuildFromAnalysisCommand(
                application_id=application_id,
                analysis_id=newer.analysis_id,
                expected_document_hash=document.document_hash,
            )
        )

    prepare = services.drafts.prepare

    def prepare_then_move(*args, **kwargs):
        prepared = prepare(*args, **kwargs)
        move_document()
        return prepared

    with monkeypatch.context() as patch:
        if race_phase == "queued":
            move_document()
        else:
            patch.setattr(services.drafts, "prepare", prepare_then_move)
        failed = _run(services, queued.id)
    moved = stored_document(services, application_id)
    assert moved.document_hash != document.document_hash
    assert failed.status is OperationStatus.FAILED
    assert failed.failure_code is OperationFailureCode.SOURCE_CHANGED
    assert stored_document(services, application_id).content is None
    with pytest.raises(StateConflict):
        services.operation_lifecycle.retry(queued.id, idempotency_key=new_id())

    succeeded = _run(services, _submit_draft(services, application_id, moved.document_hash).id)
    assert succeeded.status is OperationStatus.SUCCEEDED, succeeded.safe_failure_detail
    written = stored_document(services, application_id)
    assert written.content is not None
    assert [item.output_type for item in succeeded.outputs] == ["cv_document"]
    # The writer's call is in the AI call log, and the Operation reports its usage.
    assert succeeded.total_tokens is not None
    assert ("cv_document", written.id) in {
        (item.output_type, item.output_id) for item in succeeded.outputs
    }
    with pytest.raises(PreconditionFailed):
        _submit_draft(services, application_id, written.document_hash)


def test_a_failed_render_keeps_the_approval_and_a_retry_reaches_ready(
    services: Services, deterministic_renderer, monkeypatch
) -> None:
    """§5.4: a render failure leaves the document approved and records why.

    `last_render_error` carries the structured failure while the hash still matches;
    the attempt's own files are gone; a retry is a new Operation that reaches Ready and
    clears the error.
    """
    ingested, _analysis = seed_document(services, "Render Co")
    application_id = ingested.application_id
    document_hash = seed_draft(services, application_id).document_hash
    assert services.draft_approval.approve_document(
        ApproveDocumentCommand(
            application_id=application_id, expected_document_hash=document_hash, client="web"
        )
    ).passed

    working = rendering_adapter.render_pdf

    def crash(_html_path, _pdf_path):
        raise RuntimeError("renderer crashed")

    monkeypatch.setattr(rendering_adapter, "render_pdf", crash)
    queued = services.operation_submissions.submit_render(
        RenderCommand(application_id=application_id, expected_document_hash=document_hash),
        idempotency_key=new_id(),
        rendering_service=services.rendering,
    )
    failed = _run(services, queued.id)
    assert failed.status is OperationStatus.FAILED
    assert failed.failure_code is OperationFailureCode.RENDER_FAILED
    detail = services.queries.application_detail(application_id)
    assert detail.preparation_state is PreparationState.APPROVED
    assert detail.last_render_error is not None
    assert detail.last_render_error["failure_code"] == "RENDER_FAILED"
    assert detail.recommended_action == "render"
    attempts = services.paths.artifacts_root / "documents" / application_id
    assert not [path for path in attempts.rglob("*") if path.is_file()]

    monkeypatch.setattr(rendering_adapter, "render_pdf", working)
    current = stored_document(services, application_id)
    assert current.content is not None
    section = next(
        s
        for s in current.content.sections
        if len(s.claims) > 1 and all(c.style not in {"heading", "date"} for c in s.claims)
    )
    changed = services.drafts.update_document(
        UpdateDocumentCommand(
            application_id=application_id,
            expected_document_hash=current.document_hash,
            claim_orders={section.name: [c.claim_id for c in reversed(section.claims)]},
        )
    )
    assert services.draft_approval.approve_document(
        ApproveDocumentCommand(
            application_id=application_id,
            expected_document_hash=changed.document_hash,
            client="web",
        )
    ).passed
    retried = services.operation_lifecycle.retry(queued.id, idempotency_key=new_id())
    retry_record = services.operation_runner.operation(retried.id)
    assert retry_record.sources.expected_document_hash == changed.document_hash
    assert retry_record.payload["expected_document_hash"] == changed.document_hash
    assert retried.retry_of_operation_id == queued.id
    completed = _run(services, retried.id)
    assert completed.status is OperationStatus.SUCCEEDED, completed.safe_failure_detail
    detail = services.queries.application_detail(application_id)
    assert detail.preparation_state is PreparationState.READY
    assert detail.last_render_error is None
    assert len([path for path in attempts.rglob("*.pdf")]) == 1


@pytest.mark.parametrize("outcome", ["cancel", "edit"])
def test_render_discards_unactivated_files(
    approved_application, deterministic_renderer, monkeypatch, outcome
):

    setup = approved_application("Render Activation Race")
    services, app_id = setup
    document = stored_document(services, app_id)
    assert document.content is not None
    claim = document.content.sections[0].claims[0]
    queued = services.operation_submissions.submit_render(
        RenderCommand(application_id=app_id, expected_document_hash=document.document_hash),
        idempotency_key=new_id(),
        rendering_service=services.rendering,
    )
    execute = services.rendering.execute
    attempts = []

    def render_then_interfere(prepared):
        result = execute(prepared)
        attempts.append(result.files)
        if outcome == "cancel":
            services.operation_lifecycle.cancel(queued.id)
        else:
            edit_document_claim(
                services,
                app_id,
                claim.claim_id,
                list(claim.fact_ids),
                text="manual edit during render",
            )
        return result

    monkeypatch.setattr(services.rendering, "execute", render_then_interfere)
    completed = _run(services, queued.id)
    assert completed.status is (
        OperationStatus.CANCELLED if outcome == "cancel" else OperationStatus.FAILED
    )
    if outcome == "edit":
        assert completed.failure_code is OperationFailureCode.SOURCE_CHANGED
    assert attempts
    assert all(
        not (services.paths.root / path).exists()
        for files in attempts
        for path in (files.html, files.pdf)
    )
    assert stored_document(services, app_id).rendered_basis is None


def test_successful_rerender_discards_superseded_files(ready_application):
    setup = ready_application("Superseded Render")
    services, app_id = setup
    before = stored_document(services, app_id)
    assert before.content is not None
    section = next(
        s
        for s in before.content.sections
        if len(s.claims) > 1 and all(c.style not in {"heading", "date"} for c in s.claims)
    )
    edited = services.drafts.update_document(
        UpdateDocumentCommand(
            application_id=app_id,
            expected_document_hash=before.document_hash,
            claim_orders={section.name: [c.claim_id for c in reversed(section.claims)]},
        )
    )
    assert services.draft_approval.approve_document(
        ApproveDocumentCommand(
            application_id=app_id, expected_document_hash=edited.document_hash, client="web"
        )
    ).passed
    services.rendering.render(
        RenderCommand(application_id=app_id, expected_document_hash=edited.document_hash)
    )
    after = stored_document(services, app_id)
    assert after.pdf_path != before.pdf_path and after.html_path != before.html_path
    assert before.pdf_path is not None and before.html_path is not None
    assert not (services.paths.root / before.pdf_path).exists()
    assert not (services.paths.root / before.html_path).exists()
