from __future__ import annotations

import json as _json
import os
import socket
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest
from api_harness import api_with_worker
from fake_provider import FakeOpenAI
from fastapi.testclient import TestClient
from foreground import foreground_executor

from cv_engine.api.app import API_PREFIX, create_app
from cv_engine.runtime.composition import Services, build_api_services

TESTS_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class HttpReply:
    status: int
    body: str

    @property
    def json(self) -> Any:
        return _json.loads(self.body)


class LiveApiServer:
    """A real uvicorn process, addressed over a socket."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def _call(self, method: str, path: str, body: Any = None) -> HttpReply:
        data = _json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if method != "GET":
            headers["Origin"] = self.base_url
        request = Request(
            f"{self.base_url}{API_PREFIX}{path}", data=data, method=method, headers=headers
        )
        try:
            with urlopen(request, timeout=30) as response:
                return HttpReply(response.status, response.read().decode())
        except HTTPError as error:
            return HttpReply(error.code, error.read().decode())
        except URLError as error:
            return HttpReply(0, str(error))

    def get(self, path: str, params: dict[str, str] | None = None) -> HttpReply:
        query = f"?{urlencode(params)}" if params else ""
        return self._call("GET", f"{path}{query}")

    def post(self, path: str, body: Any) -> HttpReply:
        return self._call("POST", path, body)


@pytest.fixture
def live_api_server(project_root: Path, database_url: str) -> Iterator[LiveApiServer]:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "--factory",
            "asgi_factory:build_test_app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(TESTS_DIR),
        env={
            **os.environ,
            "CV_TEST_ASGI_ROOT": str(project_root),
            "CV_DATABASE_URL": database_url,
            "PYTHONPATH": str(TESTS_DIR),
            "CV_API_PORT": str(port),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    server = LiveApiServer(f"http://127.0.0.1:{port}")
    try:
        deadline = monotonic() + 60
        while monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail(f"API process exited early:\n{process.stdout.read()}")
            if server.get("/health").status == 200:
                break
            sleep(0.1)
        else:
            pytest.fail("API process did not become ready")
        yield server
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.fixture
def api_worker(services: Services):
    with api_with_worker(services) as harness:
        yield harness


@dataclass(frozen=True)
class PausedApiHarness:
    client: Any
    services: Services
    fake_openai: FakeOpenAI | None = None

    def run_operation(self, operation_id: str) -> dict[str, Any]:
        finished = foreground_executor(self.services).execute(operation_id)
        return finished.model_dump(mode="json")

    wait_for_operation = run_operation


@pytest.fixture
def api_paused(services: Services):
    with TestClient(create_app(build_api_services(services))) as client:
        yield PausedApiHarness(client=client, services=services)


@pytest.fixture
def ai_api_paused(ai_services: Services, fake_openai: FakeOpenAI):
    with TestClient(create_app(build_api_services(ai_services))) as client:
        yield PausedApiHarness(client=client, services=ai_services, fake_openai=fake_openai)


@pytest.fixture
def ai_api_worker(ai_services: Services, fake_openai: FakeOpenAI):
    with api_with_worker(ai_services, fake_openai=fake_openai) as harness:
        yield harness
