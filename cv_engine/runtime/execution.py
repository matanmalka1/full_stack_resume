"""Where an Operation actually runs: the worker pool that hosts it.

The runner itself is `application/operation_runner.py`. This is the host it
runs inside, which is why the module is named for the role rather than for
Operations. Its siblings here are named the same way: composition, config,
application paths.
"""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event, Lock
from time import monotonic

from ..application.operation_runner import OperationRunner
from ..application.operations import OperationStatus, PersistedOperation
from ..application.ports import OperationRepository

logger = logging.getLogger("cv_engine.worker")


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
