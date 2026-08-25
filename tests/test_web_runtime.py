from __future__ import annotations

import json
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from urllib.request import Request, urlopen

from helpers import ACCOUNT_MANAGER_JOB

from cv_engine.api.app import API_PREFIX
from cv_engine.cli import build_parser
from cv_engine.runtime.web import WebEndpoint, WebRuntime, WebRuntimeError, select_web_endpoint


def _frontend_build(root: Path) -> Path:
    root.mkdir()
    (root / "index.html").write_text(
        "<!doctype html><html lang='he' dir='rtl'><body>CV Web Runtime</body></html>",
        encoding="utf-8",
    )
    return root


def _read(url: str, *, accept: str = "application/json") -> tuple[int, bytes]:
    with urlopen(Request(url, headers={"Accept": accept}), timeout=1) as response:
        return response.status, response.read()


def _post_json(url: str, body: dict, *, origin: str) -> tuple[int, dict, str | None]:
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Idempotency-Key": "web-runtime-smoke",
            "Origin": origin,
        },
    )
    with urlopen(request, timeout=2) as response:
        return response.status, json.loads(response.read()), response.headers.get("Location")


def test_select_web_endpoint_reuses_the_same_workspace(services, monkeypatch) -> None:
    monkeypatch.setattr("cv_engine.runtime.web._port_is_open", lambda _host, _port: True)
    monkeypatch.setattr(
        "cv_engine.runtime.web._health_identity",
        lambda _endpoint: {
            "installation_id": services.workspace.installation_id(),
            "workspace_id": services.workspace.workspace_id,
        },
    )

    endpoint = select_web_endpoint(services)

    assert endpoint == WebEndpoint("127.0.0.1", 8765, reuse_existing=True)


def test_web_command_defaults_to_the_contract_endpoint_and_accepts_no_open() -> None:
    args = build_parser().parse_args(["web", "--no-open"])

    assert args.command == "web"
    assert args.port is None
    assert args.no_open is True


def test_web_runtime_reports_a_missing_frontend_build_without_a_traceback(
    services, tmp_path: Path
) -> None:
    try:
        WebRuntime(services, WebEndpoint("127.0.0.1", 18765), tmp_path / "missing")
    except WebRuntimeError as exc:
        assert "npm run build" in str(exc)
    else:
        raise AssertionError("a missing production build must refuse cv web")


def test_select_web_endpoint_avoids_a_foreign_process(services, monkeypatch) -> None:
    monkeypatch.setattr("cv_engine.runtime.web._port_is_open", lambda _host, _port: True)
    monkeypatch.setattr(
        "cv_engine.runtime.web._health_identity",
        lambda _endpoint: {"installation_id": "foreign", "workspace_id": "foreign"},
    )
    monkeypatch.setattr("cv_engine.runtime.web._free_loopback_port", lambda _host: 49152)

    endpoint = select_web_endpoint(services)

    assert endpoint == WebEndpoint("127.0.0.1", 49152)


def test_web_runtime_serves_real_http_and_stops_its_worker(services, tmp_path: Path) -> None:
    from cv_engine.runtime.web import _free_loopback_port

    endpoint = WebEndpoint("127.0.0.1", _free_loopback_port("127.0.0.1"))
    runtime = WebRuntime(services, endpoint, _frontend_build(tmp_path / "dist"))
    failure: list[BaseException] = []

    def run() -> None:
        try:
            runtime.run(open_browser=False)
        except BaseException as exc:  # surface a background failure below
            failure.append(exc)

    thread = Thread(target=run, name="test-web-runtime")
    thread.start()
    try:
        deadline = monotonic() + 10
        while True:
            try:
                status, body = _read(f"{endpoint.url}{API_PREFIX}/health")
                break
            except OSError:
                if monotonic() >= deadline:
                    raise
                sleep(0.02)
        assert status == 200
        health = json.loads(body)
        assert health["workspace_id"] == services.workspace.workspace_id
        index_status, index = _read(endpoint.url, accept="text/html")
        assert index_status == 200
        assert b"CV Web Runtime" in index

        created_status, created, _location = _post_json(
            f"{endpoint.url}{API_PREFIX}/applications",
            {
                "company": "Runtime Worker Co",
                "target_role": "Account Manager",
                "job_text": ACCOUNT_MANAGER_JOB,
                "acknowledged_duplicates": True,
            },
            origin=endpoint.url,
        )
        assert created_status == 201
        accepted_status, accepted, location = _post_json(
            f"{endpoint.url}{API_PREFIX}/applications/{created['application_id']}/analyses",
            {"job_snapshot_id": created["job_snapshot_id"]},
            origin=endpoint.url,
        )
        assert accepted_status == 202
        assert location == f"{API_PREFIX}/operations/{accepted['id']}"
        operation_deadline = monotonic() + 5
        while True:
            _operation_status, operation_body = _read(f"{endpoint.url}{location}")
            operation = json.loads(operation_body)
            if operation["is_terminal"]:
                break
            if monotonic() >= operation_deadline:
                raise AssertionError(f"Operation did not finish: {operation}")
            sleep(0.02)
        assert operation["status"] == "succeeded"
    finally:
        runtime.stop()
        thread.join(timeout=15)

    assert not thread.is_alive()
    assert failure == []


def test_web_runtime_treats_keyboard_interrupt_as_clean_shutdown(
    services, tmp_path: Path, monkeypatch
) -> None:
    endpoint = WebEndpoint("127.0.0.1", 18765)
    runtime = WebRuntime(services, endpoint, _frontend_build(tmp_path / "dist"))
    monkeypatch.setattr(runtime.server, "run", lambda: (_ for _ in ()).throw(KeyboardInterrupt()))

    runtime.run(open_browser=False)

    assert runtime.server.should_exit is True
