"""One synchronous Operation execution contract shared by both runtime hosts."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
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
from .ports import OperationRepository, UnitOfWork


class OperationExecutionError(RuntimeError):
    """A classified, safely reportable execution failure."""

    def __init__(
        self,
        code: OperationFailureCode,
        safe_detail: str,
        *,
        technical_log_reference: str | None = None,
    ):
        super().__init__(safe_detail)
        self.code = code
        self.safe_detail = safe_detail
        self.technical_log_reference = technical_log_reference


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
    def check_sources(
        self, operation: PersistedOperation, repository: OperationRepository
    ) -> None: ...

    def execute(
        self,
        operation: PersistedOperation,
        cancellation_requested: Callable[[], bool],
    ) -> PreparedOperation: ...

    def activate(
        self,
        operation: PersistedOperation,
        prepared: PreparedOperation,
        repository: OperationRepository,
    ) -> Sequence[OperationOutputReference]: ...


class OperationRunnerRepository(OperationRepository, Protocol):
    def unit_of_work(self) -> UnitOfWork: ...

    def bind(self, uow: UnitOfWork) -> OperationRunnerRepository: ...


class OperationRunner:
    def __init__(
        self,
        repository: OperationRunnerRepository,
        handlers: Mapping[OperationType, OperationHandler],
        *,
        runner_id: str,
        retry_delay_seconds: float = 0.25,
        sleeper: Callable[[float], None] = sleep,
        technical_logger: Callable[[BaseException], str | None] | None = None,
        lease_seconds: int = 30,
        heartbeat_interval_seconds: float = 10.0,
    ):
        self.repository = repository
        self.handlers = dict(handlers)
        self.runner_id = runner_id
        self.retry_delay_seconds = retry_delay_seconds
        self.sleeper = sleeper
        self.technical_logger = technical_logger or (lambda _error: None)
        self.lease_seconds = lease_seconds
        self.heartbeat_interval_seconds = heartbeat_interval_seconds

    def _cancelled(self, operation_id: str) -> bool:
        return self.repository.cancellation_requested(operation_id)

    def _fail(
        self, operation_id: str, error: OperationExecutionError
    ) -> PersistedOperation:
        return self.repository.fail_operation(
            operation_id,
            error.code,
            error.safe_detail,
            runner_id=self.runner_id,
            technical_log_reference=error.technical_log_reference,
        )

    @contextmanager
    def _heartbeat(self, operation_id: str):
        stopped = Event()
        errors: list[Exception] = []

        def pump() -> None:
            while not stopped.wait(self.heartbeat_interval_seconds):
                try:
                    self.repository.heartbeat_operation(
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

    def run(self, operation_id: str) -> PersistedOperation:
        operation = self.repository.claim_operation(
            operation_id,
            runner_id=self.runner_id,
            lease_seconds=self.lease_seconds,
        )
        if operation is None:
            return self.repository.operation(operation_id)
        return self.run_claimed(operation)

    def run_claimed(self, operation: PersistedOperation) -> PersistedOperation:
        operation_id = operation.id
        if (
            operation.status is not OperationStatus.RUNNING
            or operation.lease_owner != self.runner_id
        ):
            raise ValueError("Operation is not claimed by this runner")
        handler = self.handlers.get(operation.operation_type)
        if handler is None:
            return self._fail(
                operation_id,
                OperationExecutionError(
                    OperationFailureCode.SCHEMA_VIOLATION,
                    "No executor is registered for this Operation type.",
                ),
            )

        while True:
            try:
                self.repository.set_operation_phase(
                    operation_id,
                    OperationPhase.PRE_EXECUTION_CHECK,
                    runner_id=self.runner_id,
                )
                operation = self.repository.operation(operation_id)
                handler.check_sources(operation, self.repository)
                if self._cancelled(operation_id):
                    return self.repository.complete_operation(
                        operation_id, runner_id=self.runner_id
                    )
                self.repository.set_operation_phase(
                    operation_id, OperationPhase.EXECUTING, runner_id=self.runner_id
                )
                with self._heartbeat(operation_id):
                    prepared = handler.execute(
                        operation, lambda: self._cancelled(operation_id)
                    )
                break
            except OperationExecutionError as error:
                if error.technical_log_reference is None:
                    error = OperationExecutionError(
                        error.code,
                        error.safe_detail,
                        technical_log_reference=self.technical_logger(
                            error.__cause__ or error
                        ),
                    )
                current = self.repository.operation(operation_id)
                attempts_after_failure = current.attempts_completed + 1
                if allows_automatic_retry(error.code, attempts_after_failure):
                    self.repository.record_operation_attempt(
                        operation_id, runner_id=self.runner_id
                    )
                    self.sleeper(self.retry_delay_seconds)
                    continue
                return self._fail(operation_id, error)
            except Exception as error:
                reference = self.technical_logger(error)
                return self._fail(
                    operation_id,
                    OperationExecutionError(
                        OperationFailureCode.VALIDATION_EXECUTION_FAILED,
                        "Operation execution failed.",
                        technical_log_reference=reference,
                    ),
                )

        for output in prepared.outputs:
            self.repository.record_operation_output(
                operation_id,
                output.output_type,
                output.output_id,
                active=False,
            )
        if self._cancelled(operation_id):
            return self.repository.complete_operation(
                operation_id, runner_id=self.runner_id
            )

        try:
            with self.repository.unit_of_work() as uow:
                bound = self.repository.bind(uow)
                operation = bound.operation(operation_id)
                bound.set_operation_phase(
                    operation_id,
                    OperationPhase.PRE_ACTIVATION_CHECK,
                    runner_id=self.runner_id,
                )
                handler.check_sources(operation, bound)
                if bound.cancellation_requested(operation_id):
                    result = bound.complete_operation(
                        operation_id, runner_id=self.runner_id
                    )
                    uow.commit()
                    return result
                bound.set_operation_phase(
                    operation_id, OperationPhase.ACTIVATING, runner_id=self.runner_id
                )
                activated = handler.activate(operation, prepared, bound)
                known = {(item.output_type, item.output_id) for item in prepared.outputs}
                if prepared.activate_outputs:
                    for output in prepared.outputs:
                        bound.activate_operation_output(
                            operation_id, output.output_type, output.output_id
                        )
                for output in activated:
                    if (output.output_type, output.output_id) not in known:
                        bound.record_operation_output(
                            operation_id,
                            output.output_type,
                            output.output_id,
                            active=True,
                        )
                if prepared.terminal_failure is not None:
                    terminal_failure = prepared.terminal_failure
                    reference = terminal_failure.technical_log_reference
                    if reference is None:
                        reference = self.technical_logger(
                            terminal_failure.__cause__ or terminal_failure
                        )
                    result = bound.fail_operation(
                        operation_id,
                        terminal_failure.code,
                        terminal_failure.safe_detail,
                        runner_id=self.runner_id,
                        technical_log_reference=reference,
                    )
                else:
                    result = bound.complete_operation(
                        operation_id, runner_id=self.runner_id
                    )
                uow.commit()
                return result
        except OperationExecutionError as error:
            return self._fail(operation_id, error)
        except Exception as error:
            reference = self.technical_logger(error)
            return self._fail(
                operation_id,
                OperationExecutionError(
                    OperationFailureCode.VALIDATION_EXECUTION_FAILED,
                    "Operation activation failed.",
                    technical_log_reference=reference,
                ),
            )
