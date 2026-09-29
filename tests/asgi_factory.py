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
from pathlib import Path

from fake_provider import FakeOpenAI
from fastapi import FastAPI

from cv_engine.api.app import create_app
from cv_engine.infrastructure.knowledge import FileKnowledge
from cv_engine.runtime.composition import build_api_services, build_services
from cv_engine.runtime.paths import AppPaths

__all__ = ["build_test_ai_app", "build_test_app"]


def build_test_app() -> FastAPI:
    return _build_test_app(with_test_provider=False)


def build_test_ai_app() -> FastAPI:
    """Expose provider availability; only the independent test worker calls it."""
    return _build_test_app(with_test_provider=True)


def _build_test_app(*, with_test_provider: bool) -> FastAPI:
    root = os.environ.get("CV_TEST_ASGI_ROOT")
    if not root:
        raise RuntimeError("CV_TEST_ASGI_ROOT must name the test project root")
    paths = AppPaths.from_root(Path(root))
    # No `config=`: composition resolves it against `paths.root`, so the test
    # project's own `.env` and config apply rather than the installation's.
    provider = None
    if with_test_provider:
        contracts = FileKnowledge(paths.knowledge_root, project_root=paths.root).task_contracts()
        provider = FakeOpenAI().provider(contracts)
    services = build_services(paths, provider=provider)
    frontend_dist = os.environ.get("CV_TEST_FRONTEND_DIST")
    return create_app(
        build_api_services(services),
        port=int(os.environ.get("CV_API_PORT", "8765")),
        # Browser integration tests opt into serving a fresh production build.
        frontend_dist=Path(frontend_dist) if frontend_dist else None,
    )
