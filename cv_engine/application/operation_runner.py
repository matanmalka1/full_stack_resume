"""Synchronous Operation execution shared by runtime hosts."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from .operations import (
    ClaimReviewReason,
    FailureReason,
    OperationFailureCode,
    OperationOutputReference,
    OperationStatus,
    OperationType,
    PersistedOperation,
)
from .ports.operation_execution import OperationExecutionStore
from .ports.transactions import ReadTransaction, TransactionManager, WriteTransaction

logger = logging.getLogger("cv_engine.worker")


class OperationExecutionError(RuntimeError):
    def __init__(
        self,
        code: OperationFailureCode,
        safe_detail: str,
        *,
        technical_log_reference: str | None = None,
        reason: FailureReason | None = None,
    ):
        super().__init__(safe_detail)
        self.code = code
        self.safe_detail = safe_detail
        self.reason = reason
        self.technical_log_reference = technical_log_reference


class WorkerAlreadyRunning(RuntimeError):
    """Another worker process already holds this database's worker slot."""


class WorkerLockLost(RuntimeError):
    """The worker's slot was released underneath it; it must stop working."""


class SourceChanged(OperationExecutionError):
    def __init__(self, safe_detail: str = "Operation sources changed."):
        super().__init__(OperationFailureCode.SOURCE_CHANGED, safe_detail)


@dataclass(frozen=True)
class PreparedOperation:
    value: Any = None
    #: Proposed lines the execution withheld; recorded only if the Operation succeeds.
    withheld_claims: ClaimReviewReason | None = None


class OperationHandler(Protocol):
    def verify_sources(self, tx: ReadTransaction, operation: PersistedOperation) -> None: ...
    def execute(
        self, operation: PersistedOperation, still_owned: Callable[[], bool]
    ) -> PreparedOperation: ...
    def activate(
        self, tx: WriteTransaction, operation: PersistedOperation, prepared: PreparedOperation
    ) -> Sequence[OperationOutputReference]: ...
    def after_activation(
        self, operation: PersistedOperation, prepared: PreparedOperation
    ) -> None: ...
    def discard(self, operation: PersistedOperation, prepared: PreparedOperation) -> None:
        """Release what an executed result produced when it will never activate."""
        ...


class OperationRunner:
    def __init__(
        self,
        handlers: Mapping[OperationType, OperationHandler],
        *,
        runner_id: str,
        transactions: TransactionManager,
        execution_store: OperationExecutionStore,
        technical_logger: Callable[[BaseException], str | None] | None = None,
        operation_failure_logger: Callable[
            [BaseException, PersistedOperation, OperationFailureCode], str | None
        ]
        | None = None,
        operation_event_logger: Callable[
            [str, str, PersistedOperation | None, Mapping[str, object]], str | None
        ]
        | None = None,
    ):
        self.handlers = dict(handlers)
        self.transactions = transactions
        self.execution_store = execution_store
        self.runner_id = runner_id
        self.technical_logger = technical_logger or (lambda _error: None)
        self.operation_failure_logger = operation_failure_logger
        self.operation_event_logger = operation_event_logger

    def record_event(
        self,
        event: str,
        level: str,
        operation: PersistedOperation | None,
        fields: Mapping[str, object],
    ) -> None:
        if self.operation_event_logger is not None:
            try:
                self.operation_event_logger(event, level, operation, fields)
            except Exception as error:
                logger.warning(
                    "structured worker log unavailable event=%s exception_type=%s",
                    event,
                    type(error).__name__,
                )

    def _operation(self, operation_id: str) -> PersistedOperation:
        with self.transactions.read() as tx:
            return self.execution_store.operation(tx, operation_id)

    def operation(self, operation_id: str) -> PersistedOperation:
        return self._operation(operation_id)

    def record_unexpected_failure(
        self, error: BaseException, operation: PersistedOperation
    ) -> str | None:
        return self._record_technical_failure(
            error, operation.id, OperationFailureCode.VALIDATION_EXECUTION_FAILED
        )

    def _record_technical_failure(
        self,
        error: BaseException,
        operation_id: str,
        code: OperationFailureCode,
    ) -> str | None:
        try:
            if self.operation_failure_logger is None:
                return self.technical_logger(error)
            return self.operation_failure_logger(error, self._operation(operation_id), code)
        except Exception as logging_error:
            logger.warning(
                "structured worker failure log unavailable operation_id=%s exception_type=%s",
                operation_id,
                type(logging_error).__name__,
            )
            return None

    def _cancelled(self, operation_id: str) -> bool:
        with self.transactions.read() as tx:
            return self.execution_store.cancellation_requested(tx, operation_id)

    def _still_owned(self, operation_id: str) -> bool:
        """Running, held by this runner, and not asked to cancel: another call may start."""
        with self.transactions.read() as tx:
            return self.execution_store.execution_still_owned(
                tx, operation_id, runner_id=self.runner_id
            )

    def _complete(self, operation_id: str) -> PersistedOperation:
        with self.transactions.write() as tx:
            return self.execution_store.complete_operation(
                tx, operation_id, runner_id=self.runner_id
            )

    def _fail(self, operation_id: str, error: OperationExecutionError) -> PersistedOperation:
        with self.transactions.write() as tx:
            return self.execution_store.fail_operation(
                tx,
                operation_id,
                error.code,
                error.safe_detail,
                runner_id=self.runner_id,
                technical_log_reference=error.technical_log_reference,
                reason=error.reason,
            )

    def claim_next(self) -> PersistedOperation | None:
        with self.transactions.write() as tx:
            return self.execution_store.claim_next_operation(tx, runner_id=self.runner_id)

    def recover_previous_runner_claims(self) -> list[str]:
        """A fresh worker's one-time startup sweep: interrupt every claimed Operation.

        Only one worker runs at a time (`worker_exclusivity`), so before this
        process has claimed anything, every claim on a row belongs to a worker
        that no longer exists.
        """
        with self.transactions.write() as tx:
            return self.execution_store.interrupt_claims_from_previous_runners(tx)

    def run(self, operation_id: str) -> PersistedOperation:
        with self.transactions.write() as tx:
            operation = self.execution_store.claim_operation(
                tx, operation_id, runner_id=self.runner_id
            )
        return self._operation(operation_id) if operation is None else self.run_claimed(operation)

    def run_claimed(self, operation: PersistedOperation) -> PersistedOperation:
        if (
            operation.status is not OperationStatus.RUNNING
            or operation.lease_owner != self.runner_id
        ):
            raise ValueError("Operation is not claimed by this runner")
        handler = self.handlers.get(operation.operation_type)
        if handler is None:
            error = OperationExecutionError(
                OperationFailureCode.SCHEMA_VIOLATION,
                "No executor is registered for this Operation type.",
            )
            error.technical_log_reference = self._record_technical_failure(
                error, operation.id, error.code
            )
            return self._fail(operation.id, error)
        try:
            with self.transactions.read() as tx:
                handler.verify_sources(tx, operation)
            if self._cancelled(operation.id):
                return self._complete(operation.id)
            prepared = handler.execute(
                operation,
                lambda operation_id=operation.id: self._still_owned(operation_id),
            )
        except OperationExecutionError as error:
            if error.code is OperationFailureCode.CANCELLED_BEFORE_ACTIVATION:
                # A retry was due but the Operation was cancelled or lost to another
                # runner: it ends as its own record says, not as a provider failure.
                return self._complete(operation.id)
            if error.technical_log_reference is None:
                error.technical_log_reference = self._record_technical_failure(
                    error.__cause__ or error, operation.id, error.code
                )
            return self._fail(operation.id, error)
        except Exception as error:
            return self._fail(
                operation.id,
                OperationExecutionError(
                    OperationFailureCode.VALIDATION_EXECUTION_FAILED,
                    "Operation execution failed.",
                    technical_log_reference=self._record_technical_failure(
                        error, operation.id, OperationFailureCode.VALIDATION_EXECUTION_FAILED
                    ),
                ),
            )
        if self._cancelled(operation.id):
            self._discard(handler, operation, prepared)
            return self._complete(operation.id)
        try:
            result = self._activate(operation, prepared, handler)
        except OperationExecutionError as error:
            self._discard(handler, operation, prepared)
            if error.technical_log_reference is None:
                error.technical_log_reference = self._record_technical_failure(
                    error.__cause__ or error, operation.id, error.code
                )
            return self._fail(operation.id, error)
        except Exception as error:
            self._discard(handler, operation, prepared)
            return self._fail(
                operation.id,
                OperationExecutionError(
                    OperationFailureCode.VALIDATION_EXECUTION_FAILED,
                    "Operation activation failed.",
                    technical_log_reference=self._record_technical_failure(
                        error, operation.id, OperationFailureCode.VALIDATION_EXECUTION_FAILED
                    ),
                ),
            )
        if result.status is not OperationStatus.SUCCEEDED:
            # Cancelled under the activation lock: the result was never activated.
            self._discard(handler, operation, prepared)
        return result

    def _discard(
        self,
        handler: OperationHandler,
        operation: PersistedOperation,
        prepared: PreparedOperation,
    ) -> None:
        """Best-effort cleanup outside every scope; a failure here is only logged."""
        try:
            handler.discard(operation, prepared)
        except Exception as error:
            try:
                self.technical_logger(error)
            except Exception:
                logger.warning("discard log unavailable operation_id=%s", operation.id)

    def _activate(
        self,
        operation: PersistedOperation,
        prepared: PreparedOperation,
        handler: OperationHandler,
    ) -> PersistedOperation:
        with self.transactions.write() as tx:
            store = self.execution_store
            store.lock_application(tx, operation.application_id)
            operation = store.operation(tx, operation.id)
            handler.verify_sources(tx, operation)
            if store.cancellation_requested(tx, operation.id):
                result = store.complete_operation(tx, operation.id, runner_id=self.runner_id)
            else:
                for output in handler.activate(tx, operation, prepared):
                    store.record_operation_output(
                        tx, operation.id, output.output_type, output.output_id
                    )
                result = store.complete_operation(
                    tx,
                    operation.id,
                    runner_id=self.runner_id,
                    withheld_claims=prepared.withheld_claims,
                )
        if result.status is OperationStatus.SUCCEEDED:
            try:
                handler.after_activation(operation, prepared)
            except Exception as error:
                try:
                    self.technical_logger(error)
                except Exception as logging_error:
                    logger.warning(
                        "post-activation projection log unavailable operation_id=%s exception_type=%s",
                        operation.id,
                        type(logging_error).__name__,
                    )
        return result
