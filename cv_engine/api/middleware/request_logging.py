"""Secret-free HTTP lifecycle logging for the API process."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from time import monotonic
from typing import Protocol

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("cv_engine.server")


class RuntimeEventSink(Protocol):
    def record(
        self,
        event: str,
        level: str,
        fields: Mapping[str, object],
        error: BaseException | None = None,
    ) -> str: ...


def record_runtime_event(
    event_sink: RuntimeEventSink | None,
    event: str,
    level: str,
    fields: Mapping[str, object],
    error: BaseException | None = None,
) -> str | None:
    """Keep observability failure from changing an HTTP outcome."""
    if event_sink is None:
        return None
    try:
        return event_sink.record(event, level, fields, error)
    except Exception as logging_error:
        logger.warning(
            "structured server log unavailable event=%s exception_type=%s",
            event,
            type(logging_error).__name__,
        )
        return None


class RequestLoggingMiddleware:
    """Log one terminal line per HTTP request without bodies, queries, or headers."""

    def __init__(self, app: ASGIApp, event_sink: RuntimeEventSink | None = None):
        self.app = app
        self.event_sink = event_sink

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = monotonic()
        status_code: int | None = None

        async def record_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, record_status)
        except Exception as error:
            logger.error(
                "request crashed method=%s path=%s duration_ms=%s exception_type=%s",
                scope["method"],
                scope["path"],
                round((monotonic() - started) * 1000),
                type(error).__name__,
            )
            record_runtime_event(
                self.event_sink,
                "request.crashed",
                "ERROR",
                {
                    "method": scope["method"],
                    "path": scope["path"],
                    "duration_ms": round((monotonic() - started) * 1000),
                },
                error,
            )
            raise

        duration_ms = round((monotonic() - started) * 1000)
        values = (scope["method"], scope["path"], status_code, duration_ms)
        message = "request completed method=%s path=%s status=%s duration_ms=%s"
        if status_code is not None and status_code >= 500:
            level = "ERROR"
            logger.error(message, *values)
        elif status_code is not None and status_code >= 400:
            level = "WARNING"
            logger.warning(message, *values)
        else:
            level = "INFO"
            logger.info(message, *values)
        record_runtime_event(
            self.event_sink,
            "request.completed",
            level,
            {
                "method": scope["method"],
                "path": scope["path"],
                "status": status_code,
                "duration_ms": duration_ms,
            },
        )
