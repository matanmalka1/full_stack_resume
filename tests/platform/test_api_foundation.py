"""The API foundation: identity, refusal mapping, transport limits, contract drift.

These tests drive the real application through Starlette's `TestClient`. No ASGI
server is involved: the client speaks
ASGI to the app directly.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from cv_engine.api import FrontendBuildError
from cv_engine.api.app import API_PREFIX, DEFAULT_PORT, create_app
from cv_engine.api.middleware.security import BodySizeLimitMiddleware
from cv_engine.api.problems import PROBLEM_CONTENT_TYPE, status_for
from cv_engine.application.errors import (
    ApplicationIntakeInvalid,
    DependencyUnavailable,
    InfrastructureFailure,
    KnowledgeRejected,
    LineageBroken,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
    ValidationBlocked,
)
from cv_engine.infrastructure.runtime_logging import (
    ConciseExceptionFilter,
    StructuredRuntimeLogger,
)
from cv_engine.runtime.composition import build_api_services

ALLOWED_ORIGIN = f"http://127.0.0.1:{DEFAULT_PORT}"
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "openapi"))

from generate_openapi import OUTPUT, build_schema, render  # noqa: E402


@pytest.fixture
def api(services):
    """The real app over the isolated test project.

    The Operation worker is deliberately absent: `create_app` builds a server,
    not a process host. Tests that need a worker start one alongside the app,
    matching the two independent production processes.
    """
    with TestClient(create_app(build_api_services(services))) as client:
        yield client


# --- identity ---------------------------------------------------------------


def test_health_reports_this_instance_and_its_version_surfaces(api, services) -> None:
    response = api.get(f"{API_PREFIX}/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # Runtime identity is versioned product state, not a selectable root ID.
    assert "workspace_id" not in body
    assert body["api_version"] == "1"
    assert body["knowledge"] == services.knowledge_queries.knowledge_versions().model_dump()


def test_logs_summarise_requests_keep_tracebacks_in_file_and_redact_secrets(
    services, caplog, tmp_path: Path
) -> None:
    """The server log is secret-free, the structured file keeps a redacted
    traceback, and the console keeps the message without the traceback."""
    caplog.set_level("INFO", logger="cv_engine.server")
    event_sink = StructuredRuntimeLogger(tmp_path, tmp_path / "logs", "server.jsonl")
    app = create_app(build_api_services(services), event_sink=event_sink)

    with TestClient(app) as client:
        response = client.get(f"{API_PREFIX}/health?token=must-not-be-logged")

    assert response.status_code == 200
    assert any("server started host=127.0.0.1" in message for message in caplog.messages)
    assert any(
        f"request completed method=GET path={API_PREFIX}/health status=200" in message
        for message in caplog.messages
    )
    assert any("server stopped host=127.0.0.1" in message for message in caplog.messages)
    assert all("must-not-be-logged" not in message for message in caplog.messages)
    entries = [
        json.loads(line)
        for line in (tmp_path / "logs" / "server.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [entry["event"] for entry in entries] == [
        "server.started",
        "request.completed",
        "server.stopped",
    ]
    request_entry = entries[1]
    assert request_entry["method"] == "GET"
    assert request_entry["path"] == f"{API_PREFIX}/health"
    assert request_entry["status"] == 200
    assert "must-not-be-logged" not in json.dumps(entries)

    failure_sink = StructuredRuntimeLogger(tmp_path, tmp_path / "failures", "server.jsonl")
    try:
        raise RuntimeError("Authorization: Bearer token-value api_key=plain-value sk-live-secret")
    except RuntimeError as error:
        failure_sink.record("request.failed", "ERROR", {"path": "/api/v1/example"}, error)

    raw = (tmp_path / "failures" / "server.jsonl").read_text(encoding="utf-8")
    entry = json.loads(raw)
    assert entry["exception_type"] == "RuntimeError"
    assert "Traceback" in entry["traceback"]
    assert "[REDACTED]" in raw
    for secret in ("token-value", "plain-value", "live-secret"):
        assert secret not in raw

    try:
        raise RuntimeError("file-only detail")
    except RuntimeError:
        record = logging.LogRecord(
            "uvicorn.error",
            logging.ERROR,
            __file__,
            1,
            "Exception in ASGI application",
            (),
            sys.exc_info(),
        )

    assert ConciseExceptionFilter().filter(record)
    assert record.getMessage() == "Exception in ASGI application"
    assert record.exc_info is None


def test_orphan_inventory_reports_and_reclaim_removes_only_unregistered_payloads(
    api, services
) -> None:
    """Inventory is read-only; reclaim removes exactly what it reported.

    Ingest registers the snapshot without registering an artifact version, and a
    derived working projection is not a payload, so neither is a candidate.
    """
    from cv_engine.application.commands import IngestCommand

    ingested = services.applications.ingest(
        IngestCommand(
            company="Inventory Co", target_role="Engineer", job_text="Stored posting", client="web"
        )
    )
    orphan = services.payloads.commit_snapshot("unregistered", "snapshot", "pending payload")
    services.paths.artifacts_root.joinpath("working", "projection").mkdir(parents=True)
    services.paths.artifacts_root.joinpath("working", "projection", "resume.md").write_text(
        "derived"
    )
    before = services.payloads.payload_inventory()
    response = api.get(f"{API_PREFIX}/maintenance/orphans")
    assert response.status_code == 200, response.text
    assert response.json() == {"candidates": [orphan.reference]}
    assert services.payloads.payload_inventory() == before
    assert services.payloads.read_snapshot(orphan.reference, orphan.sha256) == "pending payload"
    assert ingested.job_snapshot_id

    response = api.post(
        f"{API_PREFIX}/maintenance/orphans/reclaim",
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"removed": [orphan.reference]}
    assert services.maintenance.inspect_orphans().candidates == []


# --- refusals ---------------------------------------------------------------


def test_every_refusal_maps_to_one_status_and_one_code() -> None:
    cases = [
        (UnknownRecord("gone"), 404, "UNKNOWN_RECORD"),
        (StateConflict("moved"), 409, "STATE_CONFLICT"),
        (PreconditionFailed("not yet"), 412, "PRECONDITION_FAILED"),
        (ApplicationIntakeInvalid("job_text", "invalid text"), 412, "APPLICATION_INTAKE_INVALID"),
        (ValidationBlocked("blocked"), 412, "VALIDATION_BLOCKED"),
        (LineageBroken("wrong owner"), 412, "LINEAGE_BROKEN"),
        (KnowledgeRejected("refused"), 412, "KNOWLEDGE_REJECTED"),
        (DependencyUnavailable("no provider"), 503, "DEPENDENCY_UNAVAILABLE"),
        (InfrastructureFailure("disk"), 500, "INFRASTRUCTURE_FAILURE"),
    ]
    for error, status, code in cases:
        assert status_for(error) == status, type(error).__name__
        assert error.code == code

    class NotRegistered(PreconditionFailed):
        pass

    assert status_for(NotRegistered("x")) == 412
    assert NotRegistered("x").code == "NOT_REGISTERED"


def test_problem_details_carry_a_stable_code_and_leak_nothing(
    api, services, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unknown routes, internal failures, request validation and method errors all
    answer in Problem Details with a stable code, and none reflects input or internals."""
    response = api.post(f"{API_PREFIX}/does-not-exist", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 404
    assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
    assert response.json()["code"] == "ROUTE_NOT_FOUND"
    assert response.json()["instance"] == f"{API_PREFIX}/does-not-exist"
    assert "Traceback" not in response.text
    assert str(REPO_ROOT) not in response.text

    leaked = (
        f"provider said invalid token sk-live-secret at {REPO_ROOT}/private.db; "
        "Traceback: provider wire message"
    )

    def fail_ingest(_command):
        raise InfrastructureFailure(leaked)

    monkeypatch.setattr(services.applications, "ingest", fail_ingest)
    failed = api.post(
        f"{API_PREFIX}/applications",
        json={
            "company": "Safe Problem Co",
            "target_role": "Developer",
            "job_text": "Python role",
            "acknowledged_duplicates": True,
        },
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert failed.status_code == 500
    assert failed.json()["detail"] == "An internal dependency failed."
    for secret in ("private.db", "Traceback", "sk-live-secret", "provider wire message"):
        assert secret not in failed.text

    invalid = api.post(
        f"{API_PREFIX}/applications",
        json={"company": {"must": "not be reflected"}},
        headers={"Origin": ALLOWED_ORIGIN},
    )

    assert invalid.status_code == 422
    assert invalid.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
    body = invalid.json()
    assert body["code"] == "REQUEST_VALIDATION_FAILED"
    assert body["instance"] == f"{API_PREFIX}/applications"
    assert body["context"]["issues"]
    assert all(set(issue) == {"location", "type"} for issue in body["context"]["issues"])
    assert "must not be reflected" not in invalid.text

    method = api.delete(
        f"{API_PREFIX}/health",
        headers={"Origin": ALLOWED_ORIGIN},
    )

    assert method.status_code == 405
    assert method.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
    assert method.headers["allow"] == "GET"
    assert method.json()["code"] == "METHOD_NOT_ALLOWED"


# --- transport limits -------------------------------------------------------


def test_body_limit_refuses_oversize_bodies_and_preserves_what_it_allows(services) -> None:
    """The limit refuses what it must and never eats what it allows.

    Oversize: 413 before routing, on a path that does not exist, so an oversize
    body is never read into a route and the response does not reveal whether the
    path was real.

    Allowed request body: reading a body inside `BaseHTTPMiddleware` exhausts the
    receive channel and leaves the route with nothing. That is invisible against a
    404, so the middleware is driven over a route that echoes what it received.

    Streamed response: `StreamingResponse` runs `listen_for_disconnect(receive)`
    concurrently with its send loop and cancels the task group the moment
    `receive()` reports a disconnect. The replay channel used to fabricate one as
    soon as the buffered body had been handed over, so every streamed response
    came back `200` with an empty body. No JSON response listens for disconnect,
    so this surfaced only with the first streaming route. The regression lives at
    the middleware, not on an artifact route, so it outlives any one endpoint.
    """
    small = 512
    base = build_api_services(services)
    limited = replace(base, limits=replace(base.limits, max_body_bytes=small))
    with TestClient(create_app(limited)) as client:
        response = client.post(
            f"{API_PREFIX}/does-not-exist",
            content=b"x" * (small + 1),
            headers={"Origin": ALLOWED_ORIGIN, "Content-Type": "application/json"},
        )

    assert response.status_code == 413
    assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
    body = response.json()
    assert body["code"] == "BODY_LIMIT_EXCEEDED"
    assert body["context"]["max_body_bytes"] == small

    with TestClient(_echo_app()) as client:
        echoed = client.post("/echo", content=b"the exact bytes")

    assert echoed.status_code == 200
    assert echoed.json() == {"seen": "the exact bytes"}

    app = FastAPI()

    @app.get("/stream")
    def stream() -> StreamingResponse:
        return StreamingResponse(iter([b"first-", b"second"]), media_type="text/plain")

    app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=1024)

    with TestClient(app) as client:
        streamed = client.get("/stream")

    assert streamed.status_code == 200
    assert streamed.content == b"first-second"


def _echo_app() -> FastAPI:
    """A minimal app whose one route reads the body the middleware replayed."""
    app = FastAPI()

    @app.post("/echo")
    async def echo(request: Request) -> dict[str, str]:
        return {"seen": (await request.body()).decode()}

    app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=1024)
    return app


# --- origin policy ----------------------------------------------------------


def test_origin_policy_guards_mutations_only_and_admits_the_configured_dev_origin(
    api, services
) -> None:
    foreign = "http://evil.example"
    for headers in ({}, {"Origin": foreign}):
        response = api.post(f"{API_PREFIX}/does-not-exist", json={}, headers=headers)

        assert response.status_code == 403
        assert response.json()["code"] == "ORIGIN_NOT_ALLOWED"
        assert foreign not in response.text

    assert api.get(f"{API_PREFIX}/health").status_code == 200
    read = api.get(f"{API_PREFIX}/health", headers={"Origin": ALLOWED_ORIGIN})

    assert read.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    for value in read.headers.values():
        assert value != "*"

    vite = "http://127.0.0.1:5173"
    base = build_api_services(services)
    without = create_app(base)
    with TestClient(without) as client:
        refused = client.post(f"{API_PREFIX}/does-not-exist", json={}, headers={"Origin": vite})
    assert refused.status_code == 403

    with_vite = replace(base, limits=replace(base.limits, dev_origin=vite))
    with TestClient(create_app(with_vite)) as client:
        accepted = client.post(f"{API_PREFIX}/does-not-exist", json={}, headers={"Origin": vite})
    assert accepted.status_code == 404


# --- production frontend ---------------------------------------------------


def test_the_production_frontend_serves_its_build_without_shadowing_api_or_escaping_it(
    services, tmp_path: Path
) -> None:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<main>frontend-entry</main>", encoding="utf-8")
    (assets / "app.js").write_text("globalThis.frontendLoaded = true;", encoding="utf-8")

    app = create_app(build_api_services(services), frontend_dist=dist)
    with TestClient(app) as client:
        root = client.get("/", headers={"Accept": "text/html"})
        nested = client.get("/applications/application-id/draft", headers={"Accept": "text/html"})
        asset = client.get("/assets/app.js")
        health = client.get(f"{API_PREFIX}/health", headers={"Accept": "text/html"})
        unknown_api = client.get(f"{API_PREFIX}/does-not-exist", headers={"Accept": "text/html"})
        missing_asset = client.get("/assets/missing.js")

    assert root.status_code == 200
    assert nested.status_code == 200
    assert root.text == nested.text == "<main>frontend-entry</main>"
    assert root.headers["cache-control"] == "no-cache"
    assert asset.status_code == 200
    assert asset.text == "globalThis.frontendLoaded = true;"
    assert health.status_code == 200
    assert health.headers["content-type"].startswith("application/json")
    assert unknown_api.status_code == 404
    assert "frontend-entry" not in unknown_api.text
    assert missing_asset.status_code == 404
    assert "frontend-entry" not in missing_asset.text

    secret = tmp_path / "secret.txt"
    secret.write_text("must-not-leak", encoding="utf-8")
    (dist / "leak.txt").symlink_to(secret)

    app = create_app(build_api_services(services), frontend_dist=dist)
    with TestClient(app) as client:
        leak = client.get("/leak.txt", headers={"Accept": "text/plain"})

    assert leak.status_code == 404
    assert "must-not-leak" not in leak.text

    missing = tmp_path / "missing"
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()

    for build in (missing, incomplete):
        with pytest.raises(FrontendBuildError) as exc_info:
            create_app(build_api_services(services), frontend_dist=build)
        assert str(exc_info.value)


# --- contract drift ---------------------------------------------------------


def test_the_committed_openapi_schema_matches_the_application() -> None:
    """The same shape as the frozen schema record.

    A committed contract that silently disagrees with the code is worse than no
    committed contract: the TypeScript types are generated from this file, so a
    drifted schema means the frontend is typed against an API that no longer
    exists.
    """
    schema = build_schema()
    validation_response = schema["paths"][f"{API_PREFIX}/applications"]["post"]["responses"]["422"]

    assert set(validation_response["content"]) == {PROBLEM_CONTENT_TYPE}
    validation_schema = validation_response["content"][PROBLEM_CONTENT_TYPE]["schema"]
    assert validation_schema == {"$ref": "#/components/schemas/ProblemDetails"}
    problem_schema = schema["components"]["schemas"]["ProblemDetails"]
    assert set(problem_schema["required"]) == {
        "type",
        "title",
        "status",
        "code",
        "detail",
    }
    selection_responses = schema["paths"][f"{API_PREFIX}/analyses/{{analysis_id}}/selection-plans"][
        "post"
    ]["responses"]
    assert selection_responses["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CreateSelectionPlanResponse"
    }
    assert selection_responses["202"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/OperationResponse"
    }
    assert OUTPUT.is_file(), (
        "openapi/openapi.json is missing; run `python openapi/generate_openapi.py`"
    )
    assert OUTPUT.read_text(encoding="utf-8") == render(schema), (
        "openapi/openapi.json is stale; regenerate it with "
        "`python openapi/generate_openapi.py` and state the diff in the commit message"
    )


# --- no endpoint accepts or exposes a path ----------------------------------

#: Response fields whose name looks filesystem-shaped and is not. One entry,
#: stated deliberately, so that forgetting to register a genuinely new one fails
#: the guard instead of passing it. `entity_references` maps a reason or warning
#: to the *entity IDs* it concerns - `{"approved_revision_id": "..."}` - which is
#: the opposite of a stored location.
PATH_SHAPED_NAME_EXCEPTIONS = frozenset({"entity_references"})

PATH_SHAPED_NAME = re.compile(
    r"(^|_)(path|paths|reference|references|filename|file|directory|dir|location)$"
)


def _path_shaped_contract_names(schema: dict) -> list[str]:
    offenders = []
    for name, model in schema["components"]["schemas"].items():
        for prop in model.get("properties") or {}:
            if PATH_SHAPED_NAME.search(prop) and prop not in PATH_SHAPED_NAME_EXCEPTIONS:
                offenders.append(f"schema {name}.{prop}")
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            for parameter in operation.get("parameters") or []:
                parameter_name = parameter["name"]
                if (
                    PATH_SHAPED_NAME.search(parameter_name)
                    and parameter_name not in PATH_SHAPED_NAME_EXCEPTIONS
                ):
                    offenders.append(f"parameter {method.upper()} {path} {parameter_name}")
            body = (operation.get("requestBody") or {}).get("content") or {}
            for media in body.values():
                for prop in (media.get("schema") or {}).get("properties") or {}:
                    if PATH_SHAPED_NAME.search(prop) and prop not in PATH_SHAPED_NAME_EXCEPTIONS:
                        offenders.append(f"body {method.upper()} {path} {prop}")
    return sorted(offenders)


def test_no_endpoint_accepts_or_exposes_a_filesystem_path() -> None:
    """The derived form of architecture §14's "no endpoint accepts local paths".

    Read from the generated contract rather than from the routers, because the
    contract is what a client actually sees: a path that reached a response
    model through an inherited field would never appear in a router's source,
    and this is exactly how `ApprovedRevision`'s two `*_reference` columns could
    have arrived at a browser.

    A prose check for the word "path" could not find that. Reading every schema
    property, query parameter, and request-body property can, and it fails here
    rather than arriving as an ad hoc exemption somewhere else.

    A blind guard reporting zero is worse than no guard (M3 Stage A, lesson 3),
    so the detector is first run against a planted schema that does contain the
    shape it hunts for. If that stops finding anything, the pattern is broken and
    the real check below has quietly stopped proving anything.
    """
    planted = {
        "components": {
            "schemas": {
                "Planted": {
                    "properties": {
                        "resume_markdown_reference": {},
                        "pdf_path": {},
                        "entity_references": {},
                        "application_id": {},
                    }
                }
            }
        },
        "paths": {},
    }
    assert _path_shaped_contract_names(planted) == [
        "schema Planted.pdf_path",
        "schema Planted.resume_markdown_reference",
    ]

    assert _path_shaped_contract_names(build_schema()) == []
