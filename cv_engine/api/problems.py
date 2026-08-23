"""One table from the application taxonomy to HTTP, and one Problem Details shape.

The table is exhaustive over the taxonomy and keyed by exception class. It never
inspects a message: the status comes from the class, the machine-readable `code`
comes from `ApplicationError.code`, and the message is free to be rewritten for a
human without moving an HTTP status.

`detail` and `context` are safe by construction. A stack trace, a local path, a
provider response, or an API key never reaches a client; those belong in the
structured logs.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from ..application.errors import (
    ApplicationError,
    DependencyUnavailable,
    InfrastructureFailure,
    KnowledgeRejected,
    LineageBroken,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
    ValidationBlocked,
)

PROBLEM_CONTENT_TYPE = "application/problem+json"

# Most specific first: the lookup walks the MRO, and `ValidationBlocked`,
# `LineageBroken`, and `KnowledgeRejected` all derive from `PreconditionFailed`.
# They share its 412 today; listing them explicitly means giving one of them a
# different status later is an edit here rather than a rewrite of the lookup.
STATUS_BY_ERROR: dict[type[ApplicationError], int] = {
    UnknownRecord: 404,
    StateConflict: 409,
    ValidationBlocked: 412,
    LineageBroken: 412,
    KnowledgeRejected: 412,
    PreconditionFailed: 412,
    DependencyUnavailable: 503,
    InfrastructureFailure: 500,
}

TITLES: dict[int, str] = {
    400: "Bad Request",
    404: "Not Found",
    409: "Conflict",
    412: "Precondition Failed",
    413: "Payload Too Large",
    422: "Unprocessable Content",
    500: "Internal Server Error",
    503: "Service Unavailable",
}


def status_for(error: ApplicationError) -> int:
    """The status for this refusal, resolved through the class hierarchy.

    A subclass nobody remembered to register still gets its parent's status
    rather than a 500, so adding an exception class cannot accidentally turn a
    domain refusal into a server error.
    """
    for cls in type(error).__mro__:
        if cls in STATUS_BY_ERROR:
            return STATUS_BY_ERROR[cls]
    return 500


def problem(
    status: int,
    code: str,
    detail: str,
    *,
    context: dict[str, Any] | None = None,
    instance: str | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"about:blank#{code.lower()}",
        "title": TITLES.get(status, "Error"),
        "status": status,
        "code": code,
        "detail": detail,
    }
    if context:
        body["context"] = context
    if instance:
        body["instance"] = instance
    return JSONResponse(status_code=status, content=body, media_type=PROBLEM_CONTENT_TYPE)


def _safe_context(error: ApplicationError) -> dict[str, Any] | None:
    """Extra machine-readable context, only where a client can act on it.

    A failed `ValidationRun` is data, not an accident, so the client is told
    which groups failed and how many issues there were. The issues themselves
    come from the validation endpoint, which returns them as a normal 200 body -
    this is the blocked-approval path, where the client needs to know *that* it
    is blocked.
    """
    if isinstance(error, ValidationBlocked) and error.report is not None:
        report = error.report
        groups = getattr(report, "groups", None)
        issues = getattr(report, "issues", None)
        context: dict[str, Any] = {}
        if isinstance(groups, dict):
            context["failed_groups"] = sorted(name for name, ok in groups.items() if not ok)
        if issues is not None:
            context["issue_count"] = len(issues)
        return context or None
    return None


async def application_error_handler(request: Request, exc: Exception) -> JSONResponse:
    error = exc if isinstance(exc, ApplicationError) else ApplicationError(str(exc))
    status = status_for(error)
    return problem(
        status,
        error.code,
        str(error),
        context=_safe_context(error),
        instance=request.url.path,
    )
