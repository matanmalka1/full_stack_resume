"""Foreground and supervised-local hosts for the shared Operation runner."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event
from time import sleep

from ..application.operation_runner import OperationRunner
from ..application.operations import PersistedOperation, is_terminal_operation
from ..application.ports import OperationRepository


class ForegroundOperationExecutor:
    """Drive or observe one durable Operation without FastAPI or ``cv web``."""

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


class OperationWorker:
    """Small in-process worker pool intended for supervision by ``cv web``."""

    def __init__(
        self,
        repository: OperationRepository,
        runner: OperationRunner,
        *,
        concurrency: int = 2,
        poll_interval_seconds: float = 0.25,
    ):
        if concurrency < 1:
            raise ValueError("worker concurrency must be positive")
        self.repository = repository
        self.runner = runner
        self.concurrency = concurrency
        self.poll_interval_seconds = poll_interval_seconds

    def recover_startup(self) -> list[str]:
        return self.repository.interrupt_expired_operations()

    def run_once(self) -> PersistedOperation | None:
        claimed = self.repository.claim_next_operation(
            runner_id=self.runner.runner_id,
            lease_seconds=self.runner.lease_seconds,
        )
        if claimed is None:
            return None
        return self.runner.run_claimed(claimed)

    def serve(self, stop: Event) -> None:
        self.recover_startup()
        futures: set[Future[PersistedOperation | None]] = set()
        with ThreadPoolExecutor(
            max_workers=self.concurrency, thread_name_prefix="operation-worker"
        ) as pool:
            while not stop.is_set():
                completed = {future for future in futures if future.done()}
                for future in completed:
                    future.result()
                futures -= completed
                while len(futures) < self.concurrency and not stop.is_set():
                    future = pool.submit(self.run_once)
                    futures.add(future)
                    # A completed None means the queue is empty; avoid spinning up
                    # the remaining slots until the next poll.
                    if future.done() and future.result() is None:
                        break
                stop.wait(self.poll_interval_seconds)
