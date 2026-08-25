"""The local Web runtime: one FastAPI server and one Operation worker.

The ASGI app remains a transport object and never starts background work. This
supervisor owns both processes over one composition root, which keeps browser
commands and worker activation on the same Workspace and database.
"""

from __future__ import annotations

import json
import socket
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread
from time import monotonic, sleep
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import uvicorn

from ..api.app import API_PREFIX, DEFAULT_HOST, DEFAULT_PORT, create_app
from ..api.frontend import FrontendBuildError, validate_frontend_build
from .composition import Services, build_api_services
from .config import RuntimeConfig


class WebRuntimeError(RuntimeError):
    """The supervised local server could not start or stop safely."""


@dataclass(frozen=True)
class WebEndpoint:
    host: str
    port: int
    reuse_existing: bool = False

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


def source_frontend_dist() -> Path:
    """Return the packaged build, or the build beside a source checkout."""
    packaged = Path(__file__).resolve().parent / "frontend_dist"
    checkout = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    return packaged if (packaged / "index.html").is_file() else checkout


def _port_is_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


def _health_identity(endpoint: WebEndpoint) -> dict[str, Any] | None:
    request = Request(
        f"{endpoint.url}{API_PREFIX}/health",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=0.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _free_loopback_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.bind((host, 0))
        return int(candidate.getsockname()[1])


def select_web_endpoint(
    services: Services,
    *,
    preferred_port: int | None = None,
) -> WebEndpoint:
    preferred_port = DEFAULT_PORT if preferred_port is None else preferred_port
    if not 1 <= preferred_port <= 65535:
        raise WebRuntimeError("Web port must be between 1 and 65535")
    preferred = WebEndpoint(DEFAULT_HOST, preferred_port)
    if not _port_is_open(preferred.host, preferred.port):
        return preferred
    identity = _health_identity(preferred)
    if identity is not None and identity.get("workspace_id") == services.workspace.workspace_id:
        return WebEndpoint(preferred.host, preferred.port, reuse_existing=True)
    return WebEndpoint(DEFAULT_HOST, _free_loopback_port(DEFAULT_HOST))


class WebRuntime:
    """Own the server and worker lifecycles for one selected endpoint."""

    def __init__(
        self,
        services: Services,
        endpoint: WebEndpoint,
        frontend_dist: Path,
        *,
        config: RuntimeConfig | None = None,
    ) -> None:
        if endpoint.reuse_existing:
            raise WebRuntimeError("an existing endpoint does not need another runtime")
        self.services = services
        self.endpoint = endpoint
        try:
            self.frontend_dist = validate_frontend_build(frontend_dist)
        except FrontendBuildError as exc:
            raise WebRuntimeError(
                "frontend build is missing; run `cd frontend && npm run build` before "
                "`cv web`. To develop the frontend instead, no build is needed: run "
                "`cv web --no-open` for the API and `npm run dev` for the UI."
            ) from exc
        app = create_app(
            build_api_services(services, config=config),
            host=endpoint.host,
            port=endpoint.port,
            frontend_dist=self.frontend_dist,
        )
        self.server = uvicorn.Server(
            uvicorn.Config(
                app,
                host=endpoint.host,
                port=endpoint.port,
                log_level="info",
                access_log=False,
            )
        )
        self._worker_stop = Event()
        self._worker_failure: BaseException | None = None
        self._worker_thread = Thread(
            target=self._serve_worker,
            name="cv-operation-worker",
            daemon=False,
        )

    def _serve_worker(self) -> None:
        try:
            self.services.operation_worker.serve(self._worker_stop)
        except BaseException as exc:
            self._worker_failure = exc
            self.server.should_exit = True

    def wait_until_ready(self, timeout: float = 10.0) -> None:
        deadline = monotonic() + timeout
        while monotonic() < deadline:
            if self.server.started and _health_identity(self.endpoint) is not None:
                return
            if self.server.should_exit:
                break
            sleep(0.02)
        raise WebRuntimeError(f"Web server did not become ready at {self.endpoint.url}")

    def stop(self) -> None:
        self.server.should_exit = True

    def run(self, *, open_browser: bool = False) -> None:
        self._worker_thread.start()
        opener: Thread | None = None
        if open_browser:
            opener = Thread(target=self._open_when_ready, name="cv-browser-opener", daemon=True)
            opener.start()
        try:
            self.server.run()
        except KeyboardInterrupt:
            # Uvicorn 0.52 propagates Ctrl+C after completing ASGI shutdown.
            # For an interactive supervisor this is the expected clean exit,
            # not an error that should print a traceback or return 130.
            self.server.should_exit = True
        except (OSError, SystemExit) as exc:
            raise WebRuntimeError(
                f"could not bind the local Web server at {self.endpoint.url}"
            ) from exc
        finally:
            self._worker_stop.set()
            self._worker_thread.join(timeout=15)
            if self._worker_thread.is_alive():
                raise WebRuntimeError("Operation worker did not stop within 15 seconds")
            if self._worker_failure is not None:
                raise WebRuntimeError(
                    "Operation worker stopped unexpectedly"
                ) from self._worker_failure
            if opener is not None:
                opener.join(timeout=0.1)

    def _open_when_ready(self) -> None:
        try:
            self.wait_until_ready()
        except WebRuntimeError:
            return
        webbrowser.open(self.endpoint.url)


def open_existing(endpoint: WebEndpoint, *, open_browser: bool) -> None:
    if open_browser:
        webbrowser.open(endpoint.url)
