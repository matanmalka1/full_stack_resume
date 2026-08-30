"""An ASGI app over a test project root, for subprocess-served API tests.

Production resolves its root from the installed code location and offers no way
to move it. A test that needs the API in a separate process therefore cannot
point the real entry point at a temporary directory - it builds its own app
here instead, from the same composition root, and uvicorn is told to load this
factory rather than `cv_engine.runtime.asgi`.

The root arrives in `CV_TEST_ASGI_ROOT`, read only by this module. Production
runtime never looks for it.
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from cv_engine.api.app import create_app
from cv_engine.runtime.composition import build_api_services, build_services
from cv_engine.runtime.paths import AppPaths

__all__ = ["build_test_app"]


def build_test_app() -> FastAPI:
    root = os.environ.get("CV_TEST_ASGI_ROOT")
    if not root:
        raise RuntimeError("CV_TEST_ASGI_ROOT must name the test project root")
    paths = AppPaths.from_root(root)
    # No `config=`: composition resolves it against `paths.root`, so the test
    # project's own `.env` and config apply rather than the installation's.
    services = build_services(paths)
    return create_app(
        build_api_services(services),
        port=int(os.environ.get("CV_API_PORT", "8765")),
        # A test project has no frontend build, and the API is what is served.
        frontend_dist=None,
    )
