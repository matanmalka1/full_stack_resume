"""Running one Operation in the calling thread, for tests only.

Production has no foreground caller: the API creates Operations and the worker
process executes them. Tests still need a way to drive one Operation to a
terminal state synchronously - and one test needs a second claimant to race the
worker, which is what proves the claim contract holds for more than one worker.

Deliberately not in `cv_engine/`. Shipping a second execution host that nothing
runs would make the runtime model ambiguous to read.
"""

from __future__ import annotations

from time import sleep

from cv_engine.application.operation_runner import OperationRunner
from cv_engine.application.operations import PersistedOperation, is_terminal_operation
from cv_engine.application.ports import OperationRepository

__all__ = ["ForegroundOperationExecutor", "foreground_executor"]


class ForegroundOperationExecutor:
    """Drive or observe one durable Operation in the calling thread."""

    def __init__(
        self,
        repository: OperationRepository,
        runner: OperationRunner,
        *,
        poll_interval_seconds: float = 0.25,
        sleeper=sleep,
    ):
        self.repository = repository
        self.runner = runner
        self.poll_interval_seconds = poll_interval_seconds
        self.sleeper = sleeper

    def execute(self, operation_id: str) -> PersistedOperation:
        self.repository.interrupt_expired_operations()
        while True:
            current = self.repository.operation(operation_id)
            if is_terminal_operation(current.status):
                return current
            if current.status.value == "queued":
                current = self.runner.run(operation_id)
                if is_terminal_operation(current.status):
                    return current
            self.sleeper(self.poll_interval_seconds)


def foreground_executor(services) -> ForegroundOperationExecutor:
    """A foreground executor over a built `Services`' repository and runner."""
    return ForegroundOperationExecutor(services.repository, services.operation_runner)
