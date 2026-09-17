"""Atomic operation activation boundary used by the execution host."""

from __future__ import annotations

from typing import Protocol

from ..operations import OperationPhase, PersistedOperation
from .transactions import ReadTransaction, WriteTransaction


class OperationActivationStore(Protocol):
    def lock_application(self, tx: WriteTransaction, application_id: str) -> None: ...

    def operation(self, tx: ReadTransaction, operation_id: str) -> PersistedOperation: ...

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

    def complete_operation(
        self,
        tx: WriteTransaction,
        operation_id: str,
        *,
        runner_id: str,
        now: str | None = None,
    ) -> PersistedOperation: ...
