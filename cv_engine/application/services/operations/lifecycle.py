"""Client-visible Operation lifecycle commands and reads."""

from __future__ import annotations

from ....util import new_id
from ...errors import StateConflict, UnknownRecord
from ...operations import (
    CreateOperation,
    OperationFailureCode,
    OperationView,
    as_operation_view,
    is_terminal_operation,
)
from ...ports.operation_client import OperationClientStore
from ...ports.transactions import TransactionManager


class OperationLifecycleService:
    def __init__(self, transactions: TransactionManager, operations: OperationClientStore):
        self.transactions = transactions
        self.operations = operations

    def get(self, operation_id: str) -> OperationView:
        with self.transactions.read() as tx:
            return as_operation_view(self.operations.operation(tx, operation_id))

    def cancel(self, operation_id: str) -> OperationView:
        with self.transactions.write() as tx:
            operation = self.operations.request_cancellation(tx, operation_id)
        return as_operation_view(operation)

    def retry(self, operation_id: str, *, idempotency_key: str) -> OperationView:
        with self.transactions.read() as tx:
            original = self.operations.operation(tx, operation_id)
            try:
                application = self.operations.application(tx, original.application_id)
            except UnknownRecord as exc:
                raise UnknownRecord(f"unknown application: {original.application_id}") from exc
        if application.get("deleted_at") is not None:
            raise StateConflict(f"application is deleted: {original.application_id}")
        if not is_terminal_operation(original.status):
            raise StateConflict("only a terminal Operation can be retried")
        failure_code = original.failure_code
        if failure_code is not None and failure_code in {
            OperationFailureCode.MISSING_FACT_RENDERING,
            OperationFailureCode.SOURCE_CHANGED,
        }:
            raise StateConflict(
                f"an Operation that failed with {failure_code.value} cannot be retried "
                "against the same frozen sources"
            )
        request = CreateOperation(
            application_id=original.application_id,
            operation_type=original.operation_type,
            payload=original.payload,
            idempotency_key=idempotency_key,
            sources=original.sources,
            provider=original.provider,
            model=original.model,
            reasoning_effort=original.reasoning_effort,
            retry_of_operation_id=original.id,
        )
        with self.transactions.write() as tx:
            queued = self.operations.enqueue(tx, request, operation_id=new_id())
        return as_operation_view(queued)
