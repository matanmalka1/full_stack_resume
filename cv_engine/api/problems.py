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

from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from ..application.errors import (
    ApplicationError,
    DependencyUnavailable,
    DuplicateAcknowledgementRequired,
    InfrastructureFailure,
    KnowledgeRejected,
    LineageBroken,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
    ValidationBlocked,
)
from .request_logging import RuntimeEventSink, record_runtime_event

PROBLEM_CONTENT_TYPE = "application/problem+json"

# FastAPI otherwise documents its native ``{"detail": [...]}`` validation body
# even when a custom handler serves Problem Details. Kept beside the serializer so
# the runtime and generated contract have one owner.
PROBLEM_DETAILS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["type", "title", "status", "code", "detail"],
    "properties": {
        "type": {"type": "string"},
        "title": {"type": "string"},
        "status": {"type": "integer"},
        "code": {"type": "string"},
        "detail": {"type": "string"},
        "context": {"type": "object", "additionalProperties": True},
        "instance": {"type": "string"},
    },
}
REQUEST_VALIDATION_OPENAPI_RESPONSE: dict[str, Any] = {
    "description": "The request did not match the API contract.",
    "content": {
        PROBLEM_CONTENT_TYPE: {
            "schema": {"$ref": "#/components/schemas/ProblemDetails"},
        }
    },
}


def install_problem_details_openapi(app: FastAPI) -> None:
    """Register the shared error component referenced by router responses."""
    default_openapi = app.openapi

    def openapi_with_problem_details() -> dict[str, Any]:
        schema = default_openapi()
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        components["ProblemDetails"] = PROBLEM_DETAILS_SCHEMA
        return schema

    app.openapi = openapi_with_problem_details


# Most specific first: the lookup walks the MRO, and `ValidationBlocked`,
# `LineageBroken`, and `KnowledgeRejected` all derive from `PreconditionFailed`.
# They share its 412 today; listing them explicitly means giving one of them a
# different status later is an edit here rather than a rewrite of the lookup.
STATUS_BY_ERROR: dict[type[ApplicationError], int] = {
    UnknownRecord: 404,
    StateConflict: 409,
    DuplicateAcknowledgementRequired: 412,
    ValidationBlocked: 412,
    LineageBroken: 412,
    KnowledgeRejected: 412,
    PreconditionFailed: 412,
    DependencyUnavailable: 503,
    InfrastructureFailure: 500,
}

TITLES: dict[int, str] = {
    400: "Bad Request",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",
    412: "Precondition Failed",
    413: "Payload Too Large",
    422: "Unprocessable Content",
    500: "Internal Server Error",
    503: "Service Unavailable",
}

HTTP_ERROR_CODES: dict[int, str] = {
    400: "BAD_REQUEST",
    403: "FORBIDDEN",
    404: "ROUTE_NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    413: "PAYLOAD_TOO_LARGE",
    422: "REQUEST_VALIDATION_FAILED",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
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
    headers: Mapping[str, str] | None = None,
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
    return JSONResponse(
        status_code=status,
        content=body,
        headers=headers,
        media_type=PROBLEM_CONTENT_TYPE,
    )


def _safe_context(error: ApplicationError) -> dict[str, Any] | None:
    """Extra machine-readable context, only where a client can act on it.

    A failed `ValidationRun` is data, not an accident, so the client is told
    which groups failed and how many issues there were. The issues themselves
    come from the validation endpoint, which returns them as a normal 200 body -
    this is the blocked-approval path, where the client needs to know *that* it
    is blocked.
    """
    if isinstance(error, DuplicateAcknowledgementRequired):
        return {"matches": error.matches}
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


def _safe_detail(error: ApplicationError) -> str:
    """Keep dependency diagnostics out of the HTTP representation.

    Expected domain refusals are written for the user and may retain their
    message. Infrastructure and provider exceptions commonly carry local
    paths, credentials, response text, or transport diagnostics; those details
    belong only in the structured technical log.
    """
    if isinstance(error, DependencyUnavailable):
        return "A required dependency is unavailable."
    if isinstance(error, InfrastructureFailure):
        return "An internal dependency failed."
    return str(error)


async def application_error_handler(request: Request, exc: Exception) -> JSONResponse:
    error = exc if isinstance(exc, ApplicationError) else ApplicationError(str(exc))
    status = status_for(error)
    return _request_problem(
        request,
        status,
        error.code,
        _safe_detail(error),
        context=_safe_context(error),
        error=error,
    )


async def request_validation_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Turn FastAPI/Pydantic request failures into the one public error shape.

    Pydantic includes the rejected input in its native error dictionaries. Only
    locations and stable error types cross the HTTP boundary so request bodies do
    not get reflected back or copied into logs.
    """
    error = exc if isinstance(exc, RequestValidationError) else None
    issues = (
        []
        if error is None
        else [
            {
                "location": [str(part) for part in issue["loc"]],
                "type": issue["type"],
            }
            for issue in error.errors()
        ]
    )
    return _request_problem(
        request,
        422,
        "REQUEST_VALIDATION_FAILED",
        "The request did not match the API contract.",
        context={"issues": issues} if issues else None,
    )


async def http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Normalize router and framework HTTP errors without echoing exception detail."""
    status = exc.status_code if isinstance(exc, HTTPException) else 500
    code = HTTP_ERROR_CODES.get(status, f"HTTP_{status}")
    headers = exc.headers if isinstance(exc, HTTPException) else None
    return _request_problem(
        request,
        status,
        code,
        TITLES.get(status, "Request failed."),
        headers=headers,
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Record an unexpected failure and expose no exception text."""
    return _request_problem(
        request,
        500,
        "INTERNAL_ERROR",
        "The request could not be completed.",
        error=exc,
    )


def _request_problem(
    request: Request,
    status: int,
    code: str,
    detail: str,
    *,
    context: dict[str, Any] | None = None,
    error: BaseException | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Shared logging and response path for failures owned by the HTTP adapter."""
    event_sink: RuntimeEventSink | None = getattr(request.app.state, "event_sink", None)
    is_server_failure = status >= 500
    record_runtime_event(
        event_sink,
        "request.failed" if is_server_failure else "request.refused",
        "ERROR" if is_server_failure else "WARNING",
        {
            "method": request.method,
            "path": request.url.path,
            "status": status,
            "error_code": code,
        },
        error if is_server_failure else None,
    )
    return problem(
        status,
        code,
        detail,
        context=context,
        headers=headers,
        instance=request.url.path,
    )
