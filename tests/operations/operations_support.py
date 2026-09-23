from __future__ import annotations

from cv_engine.application.commands import (
    IngestCommand,
)
from cv_engine.application.operation_runner import (
    OperationRunner,
    PreparedOperation,
)
from cv_engine.application.operations import (
    CreateOperation,
    OperationSources,
    OperationType,
)
from cv_engine.util import new_id


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


def _execution_write(services, method, *args, **options):
    with services.operation_runner.transactions.write() as tx:
        return getattr(services.operation_runner.execution_store, method)(tx, *args, **options)


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
