from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from threading import Barrier, Event, Lock, Thread

import pytest
from foreground import ForegroundOperationExecutor, foreground_executor
from helpers import seed_document, stored_document
from operations_support import (
    _claim_operation,
    _enqueue_operation,
    _execution_write,
    _Handler,
    _operation,
    _operation_for_runner,
    _runner,
    _stored_request,
)
from sqlalchemy import select, update

import cv_engine.infrastructure.rendering as rendering_adapter
from cv_engine.application.commands import (
    AnalyzeCommand,
    ApproveDocumentCommand,
    DraftCommand,
    IngestCommand,
    ProposeSelectionCommand,
    RenderCommand,
    UpdateDocumentCommand,
    UpdateSelectionCommand,
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
from cv_engine.domain.contracts.providers import SelectionProposal
from cv_engine.domain.document import PreparationState
from cv_engine.infrastructure.operation_logging import OperationFailureLogger
from cv_engine.infrastructure.persistence.artifact_catalog import SqlAlchemyArtifactCatalog
from cv_engine.infrastructure.persistence.connection import (
    SqlAlchemyTransactionManager,
    worker_exclusivity,
)
from cv_engine.infrastructure.persistence.operation_execution import (
    SqlAlchemyOperationExecutionStore,
)
from cv_engine.infrastructure.persistence.tables import (
    operation_resource_leases,
    operations,
)
from cv_engine.runtime.composition import Services
from cv_engine.runtime.execution import OperationWorker
from cv_engine.util import new_id


def _artifact_version(services, *args):
    transactions = services.operation_runner.transactions
    with transactions.read() as tx:
        return SqlAlchemyArtifactCatalog(transactions).artifact_version(tx, *args)


def _artifact_versions(services, *args):
    transactions = services.operation_runner.transactions
    with transactions.read() as tx:
        return SqlAlchemyArtifactCatalog(transactions).artifact_versions(tx, *args)


def _latest_artifact_version(services, *args):
    transactions = services.operation_runner.transactions
    with transactions.read() as tx:
        return SqlAlchemyArtifactCatalog(transactions).latest_artifact_version(tx, *args)


def test_racing_claimants_produce_one_claim_and_one_execution(
    services,
    database_engine,
) -> None:
    """Contending claimants produce one claim and one execution.

    Two runners racing one Operation get one claim, and the loser releases only
    what it took. The two concrete hosts - foreground executor and worker - contend
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
    # The loser must release only what it took. Releasing by operation_id
    # deleted the winner's resource slots while it was still running under them.
    with services.operation_runner.transactions.read() as tx:
        connection = services.operation_runner.transactions.connection_for(tx)
        held = connection.execute(
            select(operation_resource_leases.c.resource_kind).where(
                operation_resource_leases.c.operation_id == created.id,
                operation_resource_leases.c.lease_owner == winner.lease_owner,
            )
        ).scalars()
        assert sorted(held) == sorted(resource.kind.value for resource in winner.resources)

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
        exclusive=nullcontext,
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
        exclusive=nullcontext,
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
        operation_type=OperationType.RENDER_DOCUMENT,
        payload={"expected_document_hash": "a" * 64},
        idempotency_key="render-1",
        sources=OperationSources(expected_document_hash="a" * 64),
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


def test_startup_interrupts_work_held_by_previous_runners_and_one_worker_runs(
    services,
    database_engine,
) -> None:
    """Startup interrupts every claimed Operation, which is safe only with one worker.

    Any claim left on a row belongs to a worker that no longer exists, queued or
    running. An unclaimed queued Operation is left for the new worker. The
    advisory lock is what makes "no other worker is alive" true: a second
    holder is refused, and the slot frees when the first lets go.
    """
    queued = _operation_for_runner(services, "Claimed Queued Co")
    running = _operation_for_runner(services, "Claimed Running Co")
    waiting = _operation_for_runner(services, "Unclaimed Co")
    with database_engine.begin() as connection:
        connection.execute(
            update(operations).where(operations.c.id == queued.id).values(lease_owner="dead-runner")
        )
        connection.execute(
            update(operations)
            .where(operations.c.id == running.id)
            .values(status="running", lease_owner="dead-runner")
        )

    interrupted = _execution_write(services, "interrupt_claims_from_previous_runners")

    assert sorted(interrupted) == sorted([queued.id, running.id])
    assert _operation(services, queued.id).status is OperationStatus.INTERRUPTED
    assert _operation(services, running.id).status is OperationStatus.INTERRUPTED
    assert _operation(services, waiting.id).status is OperationStatus.QUEUED

    with worker_exclusivity(database_engine):
        with pytest.raises(WorkerAlreadyRunning):
            with worker_exclusivity(database_engine):
                pass
    with worker_exclusivity(database_engine):
        pass


def test_runner_activates_outputs_and_completes_in_one_activation_transaction(services) -> None:
    operation = _operation_for_runner(services)
    output_id = new_id()
    prepared = PreparedOperation(
        value={"proposal": "validated"},
        outputs=(
            OperationOutputReference(
                output_type="provider_response",
                output_id=output_id,
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
    assert [(item.output_id, item.active) for item in result.outputs] == [(output_id, True)]


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
    # The same reason, structured, as read back from the database.
    assert completed.failure_reason == MissingFactRenderingReason(
        fact_id="situational.agentic_multi_agent", language="he"
    )
    assert completed.outputs == []
    with pytest.raises(StateConflict, match="cannot be retried"):
        services.operation_lifecycle.retry(completed.id, idempotency_key="meaningless-retry")
    assert completed.attempts_completed == 1
    assert attempts == 1


def test_worker_shutdown_requests_cancellation_and_prevents_activation(
    services, monkeypatch
) -> None:
    operation = _operation_for_runner(services, "Worker Shutdown Co")
    started = Event()
    original_cancel = services.operation_lifecycle.operations.request_cancellation
    cancellation_attempts = []

    def cancel_after_runner_write(tx, operation_id):
        cancellation_attempts.append(operation_id)
        if len(cancellation_attempts) == 1:
            # Establish the cancellation snapshot, then commit a runner phase
            # update on another connection. It must force cancellation to retry.
            services.operation_runner.execution_store.operation(tx, operation_id)
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(
                    _execution_write,
                    services,
                    "set_operation_phase",
                    operation_id,
                    OperationPhase.EXECUTING,
                    runner_id="shutdown-worker",
                ).result(timeout=2)
        return original_cancel(tx, operation_id)

    monkeypatch.setattr(
        services.operation_lifecycle.operations, "request_cancellation", cancel_after_runner_write
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
    )
    worker = OperationWorker(
        runner,
        request_cancellation=services.operation_lifecycle.cancel,
        exclusive=nullcontext,
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
    services: Services, monkeypatch, race_phase
) -> None:
    """A selection change before execution or activation yields SOURCE_CHANGED.

    The failure is not retryable; a new Operation against the current hash is how
    the user continues, and it writes the content.
    """
    ingested, _analysis = seed_document(services, "Race Co")
    application_id = ingested.application_id
    document = stored_document(services, application_id)
    queued = _submit_draft(services, application_id, document.document_hash)

    def move_selection():
        services.selection.update_selection(
            UpdateSelectionCommand(
                application_id=application_id,
                expected_document_hash=document.document_hash,
                emphasis_override=document.selection.emphasis.value,
            )
        )

    prepare = services.drafts.prepare

    def prepare_then_move(*args, **kwargs):
        prepared = prepare(*args, **kwargs)
        move_selection()
        return prepared

    with monkeypatch.context() as patch:
        if race_phase == "queued":
            move_selection()
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
    assert [(item.output_type, item.output_id, item.active) for item in succeeded.outputs] == [
        ("cv_document", written.id, True)
    ]
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
    document_hash = services.drafts.draft(
        DraftCommand(
            application_id=application_id,
            expected_document_hash=stored_document(services, application_id).document_hash,
        )
    ).document_hash
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


def test_an_ai_selection_proposal_is_provenance_on_the_selection_it_activates(
    ai_services: Services, fake_openai
) -> None:
    """§14 `propose_selection`: activated through the same policy, recorded as `ai`.

    Only while the document has no content; the rationale is kept verbatim and never
    read back.
    """
    services = ai_services
    ingested, _analysis = seed_document(services, "Proposal Co")
    application_id = ingested.application_id
    document = stored_document(services, application_id)
    fake_openai.script(
        "propose_selection_plan",
        SelectionProposal(pinned_fact_ids=[], excluded_fact_ids=[], rationale="keep it"),
    )
    queued = services.operation_submissions.submit_selection_proposal(
        ProposeSelectionCommand(
            application_id=application_id, expected_document_hash=document.document_hash
        ),
        idempotency_key=new_id(),
        analysis_service=services.analysis,
    )
    completed = _run(services, queued.id)
    assert completed.status is OperationStatus.SUCCEEDED, completed.safe_failure_detail

    proposed = stored_document(services, application_id)
    assert proposed.selection.proposed_by == "ai"
    assert proposed.selection.proposal_rationale == "keep it"
    assert proposed.selection.selected_fact_ids == document.selection.selected_fact_ids
    assert proposed.document_hash != document.document_hash
    outputs = {(item.output_type, item.active) for item in completed.outputs}
    assert ("cv_document", True) in outputs and ("provider_response", True) in outputs

    services.drafts.draft(
        DraftCommand(application_id=application_id, expected_document_hash=proposed.document_hash)
    )
    with pytest.raises(PreconditionFailed):
        services.operation_submissions.submit_selection_proposal(
            ProposeSelectionCommand(
                application_id=application_id,
                expected_document_hash=stored_document(services, application_id).document_hash,
            ),
            idempotency_key=new_id(),
            analysis_service=services.analysis,
        )


@pytest.mark.parametrize("outcome", ["cancel", "edit"])
def test_render_discards_unactivated_files(
    approved_application, deterministic_renderer, monkeypatch, outcome
):
    from helpers import edit_document_claim

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
