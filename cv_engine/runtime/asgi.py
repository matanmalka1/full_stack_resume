"""The ASGI application, loadable by any server.

    uvicorn cv_engine.runtime.asgi:app

This module builds one composition root at import and exposes the FastAPI
application it produces. It lives in `runtime` because that is what it is: the
API is handed its services rather than reaching for them, so `api` never
imports `runtime`. It starts no background work: the Operation worker is
its own process (`python -m cv_engine.worker`), which is what lets the API be
served by an ordinary ASGI server. See `api/app.py` for why an app-lifespan
worker was rejected.

The frontend production build is served when one is present. Without it the API
runs alone, which is what `npm run dev` proxies to.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from ..api.app import create_app
from ..api.frontend import FrontendBuildError, source_frontend_dist, validate_frontend_build
from ..infrastructure.runtime_logging import (
    StructuredRuntimeLogger,
    keep_uvicorn_console_concise,
)
from .composition import build_api_services, build_services
from .paths import AppPaths, resolve_root

__all__ = ["app", "build_app"]


def build_app() -> FastAPI:
    """Build the API over the fixed application root.

    Exposed for `uvicorn --factory` and for callers that need a fresh
    application rather than the module-level one.
    """
    root, config = resolve_root()
    # Our middleware emits the access summary without query strings. Keeping
    # uvicorn's default access logger too would duplicate every request and can
    # place the raw query string on the terminal.
    logging.getLogger("uvicorn.access").disabled = True
    keep_uvicorn_console_concise()
    services = build_services(AppPaths.from_root(root), config=config)
    server_logger = StructuredRuntimeLogger(root, services.paths.logs_root, "server.jsonl")
    try:
        frontend_dist = validate_frontend_build(source_frontend_dist())
    except FrontendBuildError:
        # A production build is optional: without one the API still serves,
        # which is the arrangement the Vite dev server proxies to.
        frontend_dist = None
    return create_app(
        build_api_services(services, config=config),
        # Where the API is reached, which is what the origin policy allows.
        # Serving on another port means telling the app so, not only uvicorn.
        host=str(config.get("api_host")),
        port=int(config.get("api_port")),
        frontend_dist=frontend_dist,
        event_sink=server_logger,
    )


app = build_app()
