"""Where an Operation actually runs: the worker pool that hosts it.

The runner itself is `application/operation_runner.py`. This is the host it
runs inside, which is why the module is named for the role rather than for
Operations. Its siblings here are named the same way: composition, config,
application paths.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import AbstractContextManager
from threading import Event, Lock
from time import monotonic
from typing import Protocol

from ..application.operation_runner import OperationRunner, WorkerLockLost
from ..application.operations import OperationStatus, PersistedOperation

logger = logging.getLogger("cv_engine.worker")


class WorkerSlot(Protocol):
    """Proof that this worker is still the only one."""

    def held(self) -> bool: ...


class OperationWorker:
    """Small in-process worker pool, hosted by ``python -m cv_engine.worker``."""

    def __init__(
        self,
        runner: OperationRunner,
        *,
        request_cancellation: Callable[[str], object],
        exclusive: Callable[[], AbstractContextManager[WorkerSlot]],
        concurrency: int = 2,
        poll_interval_seconds: float = 0.25,
        slot_check_interval_seconds: float = 5.0,
    ):
        if concurrency < 1:
            raise ValueError("worker concurrency must be positive")
        self.runner = runner
        self.request_cancellation = request_cancellation
        self._exclusive = exclusive
        self.concurrency = concurrency
        self.poll_interval_seconds = poll_interval_seconds
        self.slot_check_interval_seconds = slot_check_interval_seconds
        self._active_ids: set[str] = set()
        self._active_lock = Lock()

    def recover_startup(self) -> list[str]:
        return self.runner.recover_previous_runner_claims()

    def run_once(self) -> PersistedOperation | None:
        claimed = self.runner.claim_next()
        if claimed is None:
            return None
        logger.info(
            "operation claimed id=%s type=%s",
            claimed.id,
            claimed.operation_type.value,
        )
        self.runner.record_event(
            "operation.claimed",
            "INFO",
            claimed,
            {"runner_id": self.runner.runner_id},
        )
        started = monotonic()
        with self._active_lock:
            self._active_ids.add(claimed.id)
        try:
            result = self.runner.run_claimed(claimed)
        except Exception as error:
            reference = self.runner.record_unexpected_failure(error, claimed)
            duration_ms = round((monotonic() - started) * 1000)
            logger.error(
                "operation crashed id=%s type=%s log=%s",
                claimed.id,
                claimed.operation_type.value,
                reference,
            )
            self.runner.record_event(
                "operation.crashed",
                "ERROR",
                claimed,
                {
                    "runner_id": self.runner.runner_id,
                    "duration_ms": duration_ms,
                    "error_code": "VALIDATION_EXECUTION_FAILED",
                    "technical_log_reference": reference,
                },
            )
            raise
        else:
            self._log_result(result, round((monotonic() - started) * 1000))
            return result
        finally:
            with self._active_lock:
                self._active_ids.discard(claimed.id)

    def _log_result(self, operation: PersistedOperation, duration_ms: int) -> None:
        failure_code = operation.failure_code.value if operation.failure_code is not None else None
        fields = {
            "runner_id": self.runner.runner_id,
            "attempts_completed": operation.attempts_completed,
            "duration_ms": duration_ms,
            "error_code": failure_code,
            "technical_log_reference": operation.technical_log_reference,
            "output_count": len(operation.outputs),
        }
        if operation.status is OperationStatus.FAILED:
            level = "ERROR"
            logger.error(
                "operation failed id=%s code=%s log=%s",
                operation.id,
                failure_code,
                operation.technical_log_reference,
            )
        elif operation.status is OperationStatus.CANCELLED:
            level = "WARNING"
            logger.warning("operation cancelled id=%s", operation.id)
        elif operation.status is OperationStatus.INTERRUPTED:
            level = "WARNING"
            logger.warning("operation interrupted id=%s", operation.id)
        else:
            level = "INFO"
            logger.info("operation completed id=%s duration_ms=%s", operation.id, duration_ms)
        self.runner.record_event(f"operation.{operation.status.value}", level, operation, fields)

    def serve(self, stop: Event) -> None:
        """Hold the worker slot, recover, and claim until `stop` is set.

        Startup recovery interrupts every claimed Operation, so it runs only
        inside `exclusive`: a second worker is refused before it can touch the
        first one's work. The slot is re-checked while serving; losing it stops
        claiming, requests cancellation of held work, and raises
        `WorkerLockLost`. Until the loss is noticed, a second worker that starts
        can interrupt this one's Operations, but not corrupt them: every runner
        write, activation included, requires `lease_owner` to still be this
        runner, so interrupted work can no longer activate.
        """
        with self._exclusive() as slot:
            self._serve(stop, slot)

    def _serve(self, stop: Event, slot: WorkerSlot) -> None:
        recovered = self.recover_startup()
        if recovered:
            logger.warning(
                "startup recovered interrupted operations count=%s operation_ids=%s",
                len(recovered),
                ",".join(recovered),
            )
            self.runner.record_event(
                "worker.recovered",
                "WARNING",
                None,
                {
                    "runner_id": self.runner.runner_id,
                    "count": len(recovered),
                    "operation_ids": recovered,
                },
            )
        futures: set[Future[PersistedOperation | None]] = set()
        slot_lost = False
        next_slot_check = monotonic() + self.slot_check_interval_seconds
        with ThreadPoolExecutor(
            max_workers=self.concurrency, thread_name_prefix="operation-worker"
        ) as pool:
            while not stop.is_set():
                if monotonic() >= next_slot_check:
                    if not slot.held():
                        slot_lost = True
                        logger.error("worker lost its exclusive slot; stopping")
                        break
                    next_slot_check = monotonic() + self.slot_check_interval_seconds
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
                self.request_cancellation(operation_id)
        if slot_lost:
            raise WorkerLockLost("the worker lock session ended while the worker was running")
