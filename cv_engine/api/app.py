"""The FastAPI application.

`create_app` builds a server and nothing else. It does not start the Operation
worker: the worker is its own process (`python -m cv_engine.worker`), because
FastAPI is a server rather than a process manager, and a worker tied to an app
lifespan would start a second one for every test client. The test harness runs an
app and a worker side by side, which is the same arrangement the two processes
make in production.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException

from ..application.errors import ApplicationError
from .dependencies import install_services
from .frontend import FrontendAssetsMiddleware, validate_frontend_build
from .problems import (
    REQUEST_VALIDATION_OPENAPI_RESPONSE,
    application_error_handler,
    http_error_handler,
    install_problem_details_openapi,
    request_validation_error_handler,
    unexpected_error_handler,
)
from .request_logging import RequestLoggingMiddleware, RuntimeEventSink, record_runtime_event
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
logger = logging.getLogger("cv_engine.server")


def create_app(
    services: ApiServices,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    frontend_dist: Path | None = None,
    event_sink: RuntimeEventSink | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "server started host=%s port=%s api_version=%s",
            host,
            port,
            services.identity.api_version,
        )
        record_runtime_event(
            event_sink,
            "server.started",
            "INFO",
            {"host": host, "port": port, "api_version": services.identity.api_version},
        )
        try:
            yield
        finally:
            record_runtime_event(
                event_sink,
                "server.stopped",
                "INFO",
                {"host": host, "port": port},
            )
            logger.info("server stopped host=%s port=%s", host, port)

    app = FastAPI(
        title="CV Engine local API",
        version=services.identity.api_version,
        docs_url=None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
        lifespan=lifespan,
    )
    app.state.event_sink = event_sink
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
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)

    for router in (
        health.router,
        applications.router,
        analyses.router,
        working_drafts.router,
        approved_revisions.router,
        artifacts.router,
        operations.router,
        facts.router,
        settings.router,
        tracking.router,
        validation_runs.router,
        maintenance.router,
    ):
        app.include_router(
            router,
            prefix=API_PREFIX,
            responses={422: REQUEST_VALIDATION_OPENAPI_RESPONSE},
        )
    install_problem_details_openapi(app)
    if frontend_dist is not None:
        # Added last, so it runs first. It handles only safe static GET/HEAD
        # requests and passes every API path through to the existing transport
        # security and routers unchanged.
        app.add_middleware(
            FrontendAssetsMiddleware,
            build_dir=validate_frontend_build(frontend_dist),
        )
    # Installed last so rejected requests and production frontend responses are
    # observable too. The middleware deliberately excludes query strings,
    # headers, and bodies from its log fields.
    app.add_middleware(RequestLoggingMiddleware, event_sink=event_sink)
    return app
