"""Serve one already-built frontend without teaching the API repository layout.

The runtime supplies the build directory explicitly. Development uses Vite and
does not install this middleware; schema generation and API-only tests therefore
remain independent of Node and of a checked-out ``frontend/`` directory.
"""

from __future__ import annotations

from pathlib import Path

from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from .versioning import API_PREFIX


class FrontendBuildError(RuntimeError):
    """The caller requested production UI serving without a complete build."""


class FrontendAssetsMiddleware:
    """Serve Vite output and fall back to ``index.html`` for browser routes.

    API paths always pass through untouched. Missing assets also pass through
    rather than receiving HTML, while an HTML navigation receives the SPA entry
    point. Resolved paths must remain inside the supplied build root, including
    after symlink resolution.
    """

    def __init__(self, app: ASGIApp, build_dir: Path) -> None:
        self.app = app
        self._root = validate_frontend_build(build_dir)
        self._index = self._root / "index.html"
        self._static = StaticFiles(directory=self._root, check_dir=True)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in {"GET", "HEAD"}:
            await self.app(scope, receive, send)
            return

        request_path = scope.get("path", "")
        if _is_api_path(request_path):
            await self.app(scope, receive, send)
            return

        try:
            static_response = await self._static.get_response(request_path.lstrip("/"), scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                await self.app(scope, receive, send)
                return
        else:
            await static_response(scope, receive, send)
            return

        accept = Headers(scope=scope).get("accept", "")
        if "text/html" in accept and not request_path.startswith("/assets/"):
            await FileResponse(self._index, headers={"Cache-Control": "no-cache"})(
                scope, receive, send
            )
            return

        await self.app(scope, receive, send)


def _is_api_path(request_path: str) -> bool:
    return request_path == API_PREFIX or request_path.startswith(f"{API_PREFIX}/")


def validate_frontend_build(build_dir: Path) -> Path:
    root = Path(build_dir).resolve()
    if not root.is_dir() or not (root / "index.html").is_file():
        raise FrontendBuildError(
            "frontend production build is missing its dist directory or index.html"
        )
    return root
