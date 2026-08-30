"""Rotating structured runtime logs which never propagate to the console."""

from __future__ import annotations

import logging
import traceback
from collections.abc import Mapping
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock

from ..util import canonical_json, utc_now
from .log_redaction import redact_log_text
from .paths import relative_within


class ConciseExceptionFilter(logging.Filter):
    """Keep a logger's exception headline while leaving its traceback file-only."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


def keep_uvicorn_console_concise() -> None:
    """Remove duplicate ASGI tracebacks after the structured middleware captured them."""
    uvicorn_error = logging.getLogger("uvicorn.error")
    if not any(isinstance(item, ConciseExceptionFilter) for item in uvicorn_error.filters):
        uvicorn_error.addFilter(ConciseExceptionFilter())


class StructuredRuntimeLogger:
    """Write full server lifecycle and failure records to one JSONL file."""

    def __init__(self, project_root: Path, logs_root: Path, filename: str):
        self.project_root = Path(project_root).resolve()
        self.path = Path(logs_root).resolve() / filename
        self.log_reference = relative_within(self.project_root, self.path).as_posix()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._logger = logging.getLogger(f"cv_engine.runtime.{self.path}")
        self._logger.setLevel(logging.INFO)
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

    def record(
        self,
        event: str,
        level: str,
        fields: Mapping[str, object],
        error: BaseException | None = None,
    ) -> str:
        entry: dict[str, object] = {
            "occurred_at": utc_now(),
            "level": level,
            "event": event,
            "log_reference": self.log_reference,
            **fields,
        }
        if error is not None:
            entry.update(
                {
                    "exception_type": type(error).__name__,
                    "exception_detail": redact_log_text(str(error)),
                    "traceback": redact_log_text(
                        "".join(
                            traceback.format_exception(type(error), error, error.__traceback__)
                        )
                    ),
                }
            )
        with self._lock:
            self._logger.log(getattr(logging, level, logging.INFO), canonical_json(entry))
            for handler in self._logger.handlers:
                handler.flush()
        return self.log_reference
