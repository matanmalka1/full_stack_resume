"""Client-facing durable Operation persistence capabilities."""

from __future__ import annotations

from typing import Protocol

from ..operations import CreateOperation, PersistedOperation
from .transactions import ReadTransaction, WriteTransaction


class OperationClientStore(Protocol):
    """Submission and lifecycle persistence; transaction ownership stays above it."""

    def application(
        self, tx: ReadTransaction, application_id: str, user_id: str
    ) -> dict[str, object]: ...

    def enqueue(
        self,
        tx: WriteTransaction,
        request: CreateOperation,
        user_id: str,
        *,
        operation_id: str,
        created_at: str | None = None,
    ) -> PersistedOperation:
        """Queue on the user's Application; the idempotency key is scoped to it."""
        ...

    def operation(self, tx: ReadTransaction, operation_id: str, user_id: str) -> PersistedOperation:
        """An Operation on one of the user's Applications; any other is `UnknownRecord`."""
        ...

    def request_cancellation(
        self, tx: WriteTransaction, operation_id: str, user_id: str, *, now: str | None = None
    ) -> PersistedOperation: ...


class OperationContinuationStore(Protocol):
    """Queue the Operation a succeeded one continues into, inside its activation scope.

    The one client capability the runner side holds: it can add queued work that a
    user's own request asked for, and nothing else the API can do.
    """

    def enqueue(
        self,
        tx: WriteTransaction,
        request: CreateOperation,
        user_id: str,
        *,
        operation_id: str,
        created_at: str | None = None,
    ) -> PersistedOperation:
        """`user_id` is the owner the runner derived from the succeeded Operation."""
        ...
