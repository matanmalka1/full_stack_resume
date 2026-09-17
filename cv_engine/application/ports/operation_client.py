"""Client-facing durable Operation persistence capabilities."""

from __future__ import annotations

from typing import Protocol

from ..operations import CreateOperation, PersistedOperation
from .transactions import ReadTransaction, WriteTransaction


class OperationClientStore(Protocol):
    """Submission and lifecycle persistence; transaction ownership stays above it."""

    def application(self, tx: ReadTransaction, application_id: str) -> dict[str, object]: ...

    def enqueue(
        self,
        tx: WriteTransaction,
        request: CreateOperation,
        *,
        operation_id: str,
        created_at: str | None = None,
    ) -> PersistedOperation: ...

    def operation(self, tx: ReadTransaction, operation_id: str) -> PersistedOperation: ...

    def request_cancellation(
        self, tx: WriteTransaction, operation_id: str, *, now: str | None = None
    ) -> PersistedOperation: ...
