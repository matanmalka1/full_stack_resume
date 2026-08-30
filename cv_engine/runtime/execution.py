"""Where an Operation actually runs: the worker pool that hosts it.

The runner itself is `application/operation_runner.py`. This is the host it
runs inside, which is why the module is named for the role rather than for
Operations. Its siblings here are named the same way: composition, config,
application paths.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event, Lock

from ..application.operation_runner import OperationRunner
from ..application.operations import PersistedOperation
from ..application.ports import OperationRepository


class OperationWorker:
    """Small in-process worker pool, hosted by ``python -m cv_engine.worker``."""

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
        self._active_ids: set[str] = set()
        self._active_lock = Lock()

    def recover_startup(self) -> list[str]:
        return self.repository.interrupt_expired_operations()

    def run_once(self) -> PersistedOperation | None:
        claimed = self.repository.claim_next_operation(
            runner_id=self.runner.runner_id,
            lease_seconds=self.runner.lease_seconds,
        )
        if claimed is None:
            return None
        with self._active_lock:
            self._active_ids.add(claimed.id)
        try:
            return self.runner.run_claimed(claimed)
        finally:
            with self._active_lock:
                self._active_ids.discard(claimed.id)

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
            with self._active_lock:
                active = tuple(self._active_ids)
            for operation_id in active:
                self.repository.request_operation_cancellation(operation_id)
