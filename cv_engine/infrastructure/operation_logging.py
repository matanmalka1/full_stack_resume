from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock

from ..util import canonical_json, utc_now
from .paths import relative_within


class OperationFailureLogger:
    """Structured rotating technical log kept outside safe Operation responses."""

    def __init__(self, project_root: Path, logs_root: Path):
        self.project_root = Path(project_root).resolve()
        self.path = Path(logs_root).resolve() / "operations.jsonl"
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

    def record(self, error: BaseException) -> str:
        cause = error.__cause__
        entry = {
            "occurred_at": utc_now(),
            "exception_type": type(error).__name__,
            "detail": str(error),
            "cause_type": type(cause).__name__ if cause is not None else None,
            "cause_detail": str(cause) if cause is not None else None,
        }
        with self._lock:
            self._logger.error(canonical_json(entry))
            for handler in self._logger.handlers:
                handler.flush()
        return relative_within(self.project_root, self.path).as_posix()
