from __future__ import annotations

import logging
import traceback
from collections.abc import Mapping
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock

from ..application.operations import (
    OperationFailureCode,
    PersistedOperation,
)
from ..util import canonical_json, utc_now
from .log_redaction import redact_log_text
from .paths import relative_within


class OperationFailureLogger:
    """Structured rotating Operation lifecycle and technical log."""

    def __init__(self, project_root: Path, logs_root: Path):
        self.project_root = Path(project_root).resolve()
        self.path = Path(logs_root).resolve() / "operations.jsonl"
        self.log_reference = relative_within(self.project_root, self.path).as_posix()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._logger = logging.getLogger(f"cv_engine.operations.{self.path}")
        self._logger.setLevel(logging.ERROR)
        self._logger.propagate = False
        if not self._logger.handlers:
            handler = RotatingFileHandler(
                self.path,
                maxBytes=1_000_000,
                backupCount=3,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)

    def _record(self, entry: dict[str, object]) -> str:
        with self._lock:
            self._logger.error(canonical_json(entry))
            for handler in self._logger.handlers:
                handler.flush()
        return self.log_reference

    def record(self, error: BaseException) -> str:
        """Record an unscoped technical error for compatibility with other hosts."""
        cause = error.__cause__
        entry = {
            "occurred_at": utc_now(),
            "level": "ERROR",
            "event": "operation.failure_detail",
            "operation_id": None,
            "application_id": None,
            "operation_type": None,
            "phase": None,
            "error_code": None,
            "log_reference": self.log_reference,
            "exception_type": type(error).__name__,
            "detail": redact_log_text(str(error)),
            "cause_type": type(cause).__name__ if cause is not None else None,
            "cause_detail": redact_log_text(str(cause)) if cause is not None else None,
            "traceback": redact_log_text(
                "".join(traceback.format_exception(type(error), error, error.__traceback__))
            ),
        }
        return self._record(entry)

    def record_operation_failure(
        self,
        error: BaseException,
        operation: PersistedOperation,
        error_code: OperationFailureCode,
    ) -> str:
        """Record a failure with the durable Operation context required by the spec."""
        cause = error.__cause__
        return self._record(
            {
                "occurred_at": utc_now(),
                "level": "ERROR",
                "event": "operation.failure_detail",
                "operation_id": operation.id,
                "application_id": operation.application_id,
                "operation_type": operation.operation_type.value,
                "phase": operation.phase.value,
                "error_code": error_code.value,
                "log_reference": self.log_reference,
                "exception_type": type(error).__name__,
                "detail": redact_log_text(str(error)),
                "cause_type": type(cause).__name__ if cause is not None else None,
                "cause_detail": redact_log_text(str(cause)) if cause is not None else None,
                "traceback": redact_log_text(
                    "".join(traceback.format_exception(type(error), error, error.__traceback__))
                ),
            }
        )

    def record_event(
        self,
        event: str,
        level: str,
        operation: PersistedOperation | None,
        fields: Mapping[str, object],
    ) -> str:
        """Record a complete worker lifecycle event beside technical failures."""
        operation_fields: dict[str, object] = {
            "operation_id": None,
            "application_id": None,
            "operation_type": None,
            "status": None,
            "phase": None,
            "error_code": None,
        }
        if operation is not None:
            operation_fields.update(
                {
                    "operation_id": operation.id,
                    "application_id": operation.application_id,
                    "operation_type": operation.operation_type.value,
                    "status": operation.status.value,
                    "phase": operation.phase.value,
                }
            )
        return self._record(
            {
                "occurred_at": utc_now(),
                "level": level,
                "event": event,
                "log_reference": self.log_reference,
                **operation_fields,
                **fields,
            }
        )
