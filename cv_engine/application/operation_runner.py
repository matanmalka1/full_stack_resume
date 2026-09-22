"""Synchronous Operation execution shared by runtime hosts."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Event, Thread
from time import sleep
from typing import Any, Protocol

from .operations import (
    OperationFailureCode,
    OperationOutputReference,
    OperationPhase,
    OperationStatus,
    OperationType,
    PersistedOperation,
    allows_automatic_retry,
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
        outputs: Sequence[OperationOutputReference] = (),
    ):
        super().__init__(safe_detail)
        self.code = code
        self.safe_detail = safe_detail
        self.technical_log_reference = technical_log_reference
        self.outputs = tuple(outputs)


class SourceChanged(OperationExecutionError):
    def __init__(self, safe_detail: str = "Operation sources changed."):
        super().__init__(OperationFailureCode.SOURCE_CHANGED, safe_detail)


@dataclass(frozen=True)
class PreparedOperation:
    value: Any = None
    outputs: tuple[OperationOutputReference, ...] = ()
    activate_outputs: bool = True
    terminal_failure: OperationExecutionError | None = None


class OperationHandler(Protocol):
    def verify_sources(self, tx: ReadTransaction, operation: PersistedOperation) -> None: ...
    def verify_external_sources(self, operation: PersistedOperation) -> None: ...
    def execute(
        self, operation: PersistedOperation, cancellation_requested: Callable[[], bool]
    ) -> PreparedOperation: ...
    def activate(
        self, tx: WriteTransaction, operation: PersistedOperation, prepared: PreparedOperation
    ) -> Sequence[OperationOutputReference]: ...
    def after_activation(
        self, operation: PersistedOperation, prepared: PreparedOperation
    ) -> None: ...


class OperationRunner:
    def __init__(
        self,
        handlers: Mapping[OperationType, OperationHandler],
        *,
        runner_id: str,
        transactions: TransactionManager,
        execution_store: OperationExecutionStore,
        retry_delay_seconds: float = 0.25,
        sleeper: Callable[[float], None] = sleep,
        technical_logger: Callable[[BaseException], str | None] | None = None,
        operation_failure_logger: Callable[
            [BaseException, PersistedOperation, OperationFailureCode], str | None
        ]
        | None = None,
        operation_event_logger: Callable[
            [str, str, PersistedOperation | None, Mapping[str, object]], str | None
        ]
        | None = None,
        lease_seconds: int = 30,
        heartbeat_interval_seconds: float = 10.0,
    ):
        self.handlers = dict(handlers)
        self.transactions = transactions
        self.execution_store = execution_store
        self.runner_id = runner_id
        self.retry_delay_seconds = retry_delay_seconds
        self.sleeper = sleeper
        self.technical_logger = technical_logger or (lambda _error: None)
        self.operation_failure_logger = operation_failure_logger
        self.operation_event_logger = operation_event_logger
        self.lease_seconds = lease_seconds
        self.heartbeat_interval_seconds = heartbeat_interval_seconds

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

    def _set_phase(self, operation_id: str, phase: OperationPhase) -> PersistedOperation:
        with self.transactions.write() as tx:
            self.execution_store.set_operation_phase(
                tx, operation_id, phase, runner_id=self.runner_id
            )
            operation = self.execution_store.operation(tx, operation_id)
        self.record_event(
            "operation.phase_changed", "INFO", operation, {"runner_id": self.runner_id}
        )
        return operation

    def _complete(self, operation_id: str) -> PersistedOperation:
        with self.transactions.write() as tx:
            return self.execution_store.complete_operation(
                tx, operation_id, runner_id=self.runner_id
            )

    def _fail(self, operation_id: str, error: OperationExecutionError) -> PersistedOperation:
        with self.transactions.write() as tx:
            for output in error.outputs:
                self.execution_store.record_operation_output(
                    tx, operation_id, output.output_type, output.output_id, active=False
                )
            return self.execution_store.fail_operation(
                tx,
                operation_id,
                error.code,
                error.safe_detail,
                runner_id=self.runner_id,
                technical_log_reference=error.technical_log_reference,
            )

    def _record_inactive_outputs(
        self, operation_id: str, outputs: Sequence[OperationOutputReference]
    ) -> None:
        if not outputs:
            return
        with self.transactions.write() as tx:
            for output in outputs:
                self.execution_store.record_operation_output(
                    tx, operation_id, output.output_type, output.output_id, active=False
                )

    @contextmanager
    def _heartbeat(self, operation_id: str) -> Iterator[None]:
        stopped, errors = Event(), []

        def pump() -> None:
            while not stopped.wait(self.heartbeat_interval_seconds):
                try:
                    with self.transactions.write() as tx:
                        self.execution_store.heartbeat_operation(
                            tx,
                            operation_id,
                            runner_id=self.runner_id,
                            lease_seconds=self.lease_seconds,
                        )
                except Exception as error:
                    errors.append(error)
                    stopped.set()

        thread = Thread(target=pump, name=f"operation-heartbeat-{operation_id}", daemon=True)
        thread.start()
        try:
            yield
        finally:
            stopped.set()
            thread.join(timeout=max(1.0, self.heartbeat_interval_seconds + 1.0))
        if errors:
            raise errors[0]

    def claim_next(self) -> PersistedOperation | None:
        with self.transactions.write() as tx:
            return self.execution_store.claim_next_operation(
                tx, runner_id=self.runner_id, lease_seconds=self.lease_seconds
            )

    def recover_expired(self) -> list[str]:
        with self.transactions.write() as tx:
            return self.execution_store.interrupt_expired_operations(tx)

    def recover_previous_runner_claims(self) -> list[str]:
        """A fresh process's one-time startup sweep: reclaim every held lease.

        Distinct from `recover_expired`, which only reclaims a lease whose TTL
        has actually passed. At startup, before this process has claimed
        anything of its own, nothing legitimate could hold a lease it needs
        protected - so there is no reason to wait out a TTL that only widens
        the window in which a fast restart fails to recover a dead
        predecessor's rows.
        """
        with self.transactions.write() as tx:
            return self.execution_store.interrupt_claims_from_previous_runners(tx)

    def run(self, operation_id: str) -> PersistedOperation:
        with self.transactions.write() as tx:
            operation = self.execution_store.claim_operation(
                tx, operation_id, runner_id=self.runner_id, lease_seconds=self.lease_seconds
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
        while True:
            try:
                operation = self._set_phase(operation.id, OperationPhase.PRE_EXECUTION_CHECK)
                handler.verify_external_sources(operation)
                with self.transactions.read() as tx:
                    handler.verify_sources(tx, operation)
                if self._cancelled(operation.id):
                    return self._complete(operation.id)
                self._set_phase(operation.id, OperationPhase.EXECUTING)
                with self._heartbeat(operation.id):
                    prepared = handler.execute(
                        operation,
                        lambda operation_id=operation.id: self._cancelled(operation_id),
                    )
                break
            except OperationExecutionError as error:
                if error.technical_log_reference is None:
                    error.technical_log_reference = self._record_technical_failure(
                        error.__cause__ or error, operation.id, error.code
                    )
                attempt = self._operation(operation.id).attempts_completed + 1
                if allows_automatic_retry(error.code, attempt):
                    self._record_inactive_outputs(operation.id, error.outputs)
                    with self.transactions.write() as tx:
                        self.execution_store.record_operation_attempt(
                            tx, operation.id, runner_id=self.runner_id
                        )
                        current = self.execution_store.operation(tx, operation.id)
                    self.record_event(
                        "operation.retrying",
                        "WARNING",
                        current,
                        {
                            "runner_id": self.runner_id,
                            "error_code": error.code.value,
                            "attempt": attempt,
                        },
                    )
                    self.sleeper(self.retry_delay_seconds)
                    continue
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
        self._record_inactive_outputs(operation.id, prepared.outputs)
        if self._cancelled(operation.id):
            return self._complete(operation.id)
        try:
            return self._activate(operation, prepared, handler)
        except OperationExecutionError as error:
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
                    "Operation activation failed.",
                    technical_log_reference=self._record_technical_failure(
                        error, operation.id, OperationFailureCode.VALIDATION_EXECUTION_FAILED
                    ),
                ),
            )

    def _activate(
        self,
        operation: PersistedOperation,
        prepared: PreparedOperation,
        handler: OperationHandler,
    ) -> PersistedOperation:
        phase_events = []
        handler.verify_external_sources(operation)
        with self.transactions.write() as tx:
            store = self.execution_store
            store.lock_application(tx, operation.application_id)
            operation = store.operation(tx, operation.id)
            store.set_operation_phase(
                tx, operation.id, OperationPhase.PRE_ACTIVATION_CHECK, runner_id=self.runner_id
            )
            phase_events.append(store.operation(tx, operation.id))
            handler.verify_sources(tx, operation)
            if store.cancellation_requested(tx, operation.id):
                result = store.complete_operation(tx, operation.id, runner_id=self.runner_id)
            else:
                store.set_operation_phase(
                    tx, operation.id, OperationPhase.ACTIVATING, runner_id=self.runner_id
                )
                phase_events.append(store.operation(tx, operation.id))
                activated = handler.activate(tx, operation, prepared)
                known = {(item.output_type, item.output_id) for item in prepared.outputs}
                if prepared.activate_outputs:
                    for output in prepared.outputs:
                        store.activate_operation_output(
                            tx, operation.id, output.output_type, output.output_id
                        )
                for output in activated:
                    if (output.output_type, output.output_id) not in known:
                        store.record_operation_output(
                            tx, operation.id, output.output_type, output.output_id, active=True
                        )
                if prepared.terminal_failure is not None:
                    raise prepared.terminal_failure
                result = store.complete_operation(tx, operation.id, runner_id=self.runner_id)
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
        for phase_operation in phase_events:
            self.record_event(
                "operation.phase_changed", "INFO", phase_operation, {"runner_id": self.runner_id}
            )
        return result
