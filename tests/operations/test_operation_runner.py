from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock, Thread

import pytest
from foreground import ForegroundOperationExecutor, foreground_executor
from helpers import (
    ACCOUNT_MANAGER_JOB,
    artifact_path,
    seed_analysis_for_command,
    validate_active_draft,
)
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
    PreparedOperation,
    SourceChanged,
)
from cv_engine.application.operations import (
    CreateOperation,
    OperationFailureCode,
    OperationOutputReference,
    OperationPhase,
    OperationSources,
    OperationStatus,
    OperationType,
)
from cv_engine.domain.contracts.validation import ValidationIssue, ValidationReport
from cv_engine.infrastructure.operation_logging import OperationFailureLogger
from cv_engine.infrastructure.payloads import PayloadStore
from cv_engine.infrastructure.persistence.artifact_catalog import SqlAlchemyArtifactCatalog
from cv_engine.infrastructure.persistence.connection import SqlAlchemyTransactionManager
from cv_engine.infrastructure.persistence.draft_lifecycle import SqlAlchemyDraftLifecycleRepository
from cv_engine.infrastructure.persistence.operation_execution import (
    SqlAlchemyOperationExecutionStore,
)
from cv_engine.infrastructure.persistence.render_context import SqlAlchemyRenderContextReader
from cv_engine.infrastructure.persistence.tables import (
    operation_resource_leases,
    operations,
    payload_write_leases,
)
from cv_engine.infrastructure.persistence.validation_store import SqlAlchemyValidationRepository
from cv_engine.runtime.execution import OperationWorker
from cv_engine.util import new_id


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


def _claim_receipt(services, *args, **options):
    with services.draft_approval.transactions.write() as tx:
        return services.draft_approval.receipts.claim_idempotency_receipt(tx, *args, **options)


def _read_receipt(services, command_type, idempotency_key):
    with services.draft_approval.transactions.read() as tx:
        return services.draft_approval.receipts.idempotency_receipt(
            tx, command_type, idempotency_key
        )


def _payload_lease(services, group_key: str):
    transactions = services.draft_approval.transactions
    with transactions.read() as tx:
        return (
            transactions.connection_for(tx)
            .execute(
                select(payload_write_leases).where(payload_write_leases.c.group_key == group_key)
            )
            .mappings()
            .one()
        )


def _complete_receipt(services, receipt_id, result):
    with services.draft_approval.transactions.write() as tx:
        return services.draft_approval.receipts.complete_idempotency_receipt(tx, receipt_id, result)


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


def test_heartbeat_extends_the_lease_and_skips_inflight_cancellation(
    services,
) -> None:
    """A heartbeat extends the lease, and never fails an Operation being cancelled.

    Interruption waits until the extended lease expires. A heartbeat that meets a
    cancellation holding the row lock skips it rather than waiting and raising a
    serialization error, and the Operation then completes as cancelled.
    """
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


def test_startup_interrupts_work_held_by_previous_runners(
    services,
    database_engine,
) -> None:
    """Startup interrupts dead runners' work, expired or not.

    A queued Operation holding an expired runner lease is interrupted. A fast
    restart must not leave a dead predecessor's claim stuck either:
    `interrupt_expired_operations` deliberately waits out the TTL, which is right
    for a periodic sweep that must not disturb another live claimant, but a
    process's one-time startup sweep has no claimant to protect, so it reclaims
    unconditionally.
    """
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
    transaction_manager,
) -> None:
    setup = ready_application("Invalid Render Operation Co")
    failed_report = ValidationReport.from_findings(
        groups={"page_count": False},
        issues=[
            ValidationIssue(
                group="page_count",
                code="page-count",
                message="2 pages; maximum 1",
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
    assert failed.safe_failure_detail == "Rendered PDF has 2 pages; maximum 1."
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
    pdf_output = next(output for output in failed.outputs if output.output_type == "resume_pdf")
    with transaction_manager.read() as tx:
        stored_report = SqlAlchemyValidationRepository(transaction_manager).validation_for_artifact(
            tx,
            setup.application_id,
            "post-render",
            pdf_output.output_id,
        )
    assert stored_report == failed_report

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


def test_render_registration_is_all_or_nothing(
    ready_application,
    monkeypatch,
) -> None:
    """Both artifacts are one render: both are registered, or neither is.

    The first repair moved registration into `execute` so the rows survive a
    cancellation. Left as independent writes that would have bought the opposite
    bug: a failure partway leaves rows committed while `execute` raises, so the
    runner records no Operation output and the Application carries registered
    artifacts belonging to a render that never reported. That is not reachable
    through cancellation or `SOURCE_CHANGED`, which is why neither of those tests
    would have found it. It is driven here twice - a registry failure on the
    second registration, and a failure ingesting the second payload - and what is
    asserted is that nothing from the first survived.
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

    with pytest.MonkeyPatch.context() as scoped:
        scoped.setattr(SqlAlchemyArtifactCatalog, "register_artifact_version", fail_on_the_second)
        scoped.setattr(
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
            output
            for output in failed.outputs
            if output.output_type in {"resume_html", "resume_pdf"}
        ]

        # The registry and matching patches above must not reach the second render.

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
def test_approval_recovery_refuses_changed_inputs(drafted_application, receipt_status) -> None:
    """Every frozen input is part of the reservation, in either receipt state.

    The four inputs are one invariant - a change to any of them is key reuse -
    so they are looped rather than parametrized; the receipt state is the
    distinct recovery path.
    """
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
    for changed_input, changed_value in changed_values.items():
        changed = command.model_copy(update={changed_input: changed_value})
        with pytest.raises(StateConflict) as refused:
            setup.services.draft_approval.approve_idempotent(
                changed,
                idempotency_key="approval-frozen-inputs",
            )
        assert refused.value.code == IDEMPOTENCY_KEY_REUSED, changed_input
        after = _read_receipt(setup.services, "approve_draft", "approval-frozen-inputs")
        assert after["status"] == receipt_status, changed_input
        assert after["payload"] == receipt["payload"], changed_input
        assert _approved_revisions(setup.services, setup.application_id) == [
            _approved_revision(setup.services, committed.revision_id)
        ], changed_input
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
    lease = _payload_lease(
        setup.services,
        f"revision:{setup.application_id}:{receipt['reserved_entity_id']}",
    )
    references = lease["keys_json"]
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
    revision = _approved_revisions(setup.services, setup.application_id)[0]
    committed_references = [
        revision.resume_json_reference,
        revision.resume_markdown_reference,
    ]
    assert [
        setup.services.payloads.read_payload_text(reference) for reference in committed_references
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
