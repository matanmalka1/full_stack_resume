"""Worker-only persistence capabilities for durable Operation execution."""

from __future__ import annotations

from typing import Protocol

from ..operations import OperationFailureCode, OperationPhase, PersistedOperation
from .transactions import ReadTransaction, WriteTransaction


class OperationExecutionStore(Protocol):
    """Token-scoped claim, lease, attempt, output, and completion persistence."""

    def operation(self, tx: ReadTransaction, operation_id: str) -> PersistedOperation: ...
    def claim_operation(
        self,
        tx: WriteTransaction,
        operation_id: str,
        *,
        runner_id: str,
        lease_seconds: int = 30,
        now: str | None = None,
    ) -> PersistedOperation | None: ...
    def claim_next_operation(
        self,
        tx: WriteTransaction,
        *,
        runner_id: str,
        lease_seconds: int = 30,
        now: str | None = None,
    ) -> PersistedOperation | None: ...
    def heartbeat_operation(
        self,
        tx: WriteTransaction,
        operation_id: str,
        *,
        runner_id: str,
        lease_seconds: int = 30,
        now: str | None = None,
    ) -> None: ...
    def interrupt_expired_operations(
        self, tx: WriteTransaction, *, now: str | None = None
    ) -> list[str]: ...
    def lock_application(self, tx: WriteTransaction, application_id: str) -> None: ...
    def set_operation_phase(
        self,
        tx: WriteTransaction,
        operation_id: str,
        phase: OperationPhase,
        *,
        runner_id: str,
        message: str = "",
    ) -> None: ...
    def cancellation_requested(self, tx: ReadTransaction, operation_id: str) -> bool: ...
    def record_operation_output(
        self,
        tx: WriteTransaction,
        operation_id: str,
        output_type: str,
        output_id: str,
        *,
        active: bool = False,
        created_at: str | None = None,
    ) -> str: ...
    def activate_operation_output(
        self,
        tx: WriteTransaction,
        operation_id: str,
        output_type: str,
        output_id: str,
        *,
        now: str | None = None,
    ) -> None: ...
    def record_operation_attempt(
        self,
        tx: WriteTransaction,
        operation_id: str,
        *,
        runner_id: str,
        retry_at: str | None = None,
    ) -> int: ...
    def complete_operation(
        self, tx: WriteTransaction, operation_id: str, *, runner_id: str, now: str | None = None
    ) -> PersistedOperation: ...
    def fail_operation(
        self,
        tx: WriteTransaction,
        operation_id: str,
        code: OperationFailureCode,
        safe_detail: str,
        *,
        runner_id: str,
        technical_log_reference: str | None = None,
        now: str | None = None,
    ) -> PersistedOperation: ...
