"""The FastAPI application.

`create_app` builds a server and nothing else. It does not start the Operation
worker: the worker is its own process (`python -m cv_engine.worker`), because
FastAPI is a server rather than a process manager, and a worker tied to an app
lifespan would start a second one for every test client. The test harness runs an
app and a worker side by side, which is the same arrangement the two processes
make in production.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request

from ..application.errors import ApplicationError
from .dependencies import install_services
from .frontend import FrontendAssetsMiddleware, validate_frontend_build
from .problems import application_error_handler, problem
from .routers import (
    analyses,
    applications,
    approved_revisions,
    artifacts,
    facts,
    health,
    maintenance,
    operations,
    settings,
    tracking,
    validation_runs,
    working_drafts,
)
from .security import BodySizeLimitMiddleware, OriginPolicyMiddleware, allowed_origins
from .services import ApiServices
from .versioning import API_PREFIX, API_VERSION

__all__ = ["API_PREFIX", "API_VERSION", "DEFAULT_HOST", "DEFAULT_PORT", "create_app"]

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def create_app(
    services: ApiServices,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    frontend_dist: Path | None = None,
) -> FastAPI:
    app = FastAPI(
        title="CV Engine local API",
        version=services.identity.api_version,
        docs_url=None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    install_services(app, services)

    origins = allowed_origins(host, port, services.limits.dev_origin)
    # Order matters: middleware added last runs first, so the body limit is
    # enforced before the Origin check reads a header, and both run before any
    # route. `allow_origins` is an explicit list; `allow_credentials` stays off
    # and there is no wildcard.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "If-Match", "Idempotency-Key"],
        expose_headers=["ETag", "Location"],
    )
    app.add_middleware(OriginPolicyMiddleware, allowed=origins)
    app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=services.limits.max_body_bytes)

    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(500, _unexpected_error_handler)

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(applications.router, prefix=API_PREFIX)
    app.include_router(analyses.router, prefix=API_PREFIX)
    app.include_router(working_drafts.router, prefix=API_PREFIX)
    app.include_router(approved_revisions.router, prefix=API_PREFIX)
    app.include_router(artifacts.router, prefix=API_PREFIX)
    app.include_router(operations.router, prefix=API_PREFIX)
    app.include_router(facts.router, prefix=API_PREFIX)
    app.include_router(settings.router, prefix=API_PREFIX)
    app.include_router(tracking.router, prefix=API_PREFIX)
    app.include_router(validation_runs.router, prefix=API_PREFIX)
    app.include_router(maintenance.router, prefix=API_PREFIX)
    if frontend_dist is not None:
        # Added last, so it runs first. It handles only safe static GET/HEAD
        # requests and passes every API path through to the existing transport
        # security and routers unchanged.
        app.add_middleware(
            FrontendAssetsMiddleware,
            build_dir=validate_frontend_build(frontend_dist),
        )
    return app


async def _unexpected_error_handler(request: Request, _exc: Exception) -> JSONResponse:
    """An unexpected failure says so and nothing more.

    Whatever went wrong is in the structured logs with its Operation and
    Application IDs. The response carries no exception text, because an
    exception message is exactly where a path or a provider response leaks.
    """
    return problem(
        500,
        "INTERNAL_ERROR",
        "The request could not be completed.",
        instance=request.url.path,
    )
