"""The API foundation: identity, refusal mapping, transport limits, contract drift.

These tests drive the real application through Starlette's `TestClient`. No ASGI
server is involved: `uvicorn` and `cv web` are M6 scope, and the client speaks
ASGI to the app directly.
"""

from __future__ import annotations

import re
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from cv_engine.api.app import API_PREFIX, DEFAULT_PORT, create_app
from cv_engine.api.problems import PROBLEM_CONTENT_TYPE, status_for
from cv_engine.api.security import BodySizeLimitMiddleware
from cv_engine.application.errors import (
    DependencyUnavailable,
    InfrastructureFailure,
    KnowledgeRejected,
    LineageBroken,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
    ValidationBlocked,
)
from cv_engine.runtime.composition import build_api_services

ALLOWED_ORIGIN = f"http://127.0.0.1:{DEFAULT_PORT}"
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "openapi"))

from generate_openapi import OUTPUT, build_schema, render  # noqa: E402


@pytest.fixture
def api(services):
    """The real app over the isolated test Workspace.

    The Operation worker is deliberately absent: `create_app` builds a server,
    and the worker is hosted by the supervisor. Stages that need one start it
    alongside the app rather than inside it.
    """
    with TestClient(create_app(build_api_services(services))) as client:
        yield client


# --- identity ---------------------------------------------------------------


def test_health_reports_this_instance_and_its_version_surfaces(api, services) -> None:
    response = api.get(f"{API_PREFIX}/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # The two values `cv web` probes to tell its own instance from a foreign
    # process on the same port.
    assert body["installation_id"] == services.workspace.installation_id()
    assert body["workspace_id"] == services.workspace.workspace_id
    assert body["api_version"] == "1"
    assert body["knowledge"] == services.knowledge_lifecycle.knowledge_versions().model_dump()


# --- refusals ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (UnknownRecord("gone"), 404, "UNKNOWN_RECORD"),
        (StateConflict("moved"), 409, "STATE_CONFLICT"),
        (PreconditionFailed("not yet"), 412, "PRECONDITION_FAILED"),
        (ValidationBlocked("blocked"), 412, "VALIDATION_BLOCKED"),
        (LineageBroken("wrong owner"), 412, "LINEAGE_BROKEN"),
        (KnowledgeRejected("refused"), 412, "KNOWLEDGE_REJECTED"),
        (DependencyUnavailable("no provider"), 503, "DEPENDENCY_UNAVAILABLE"),
        (InfrastructureFailure("disk"), 500, "INFRASTRUCTURE_FAILURE"),
    ],
)
def test_every_refusal_maps_to_one_status_and_one_code(error, status, code) -> None:
    assert status_for(error) == status
    assert error.code == code


def test_an_unregistered_subclass_inherits_its_parents_status() -> None:
    """Adding an exception class cannot turn a domain refusal into a 500.

    The lookup walks the MRO, so a subclass nobody remembered to register still
    answers 412 rather than falling through to a server error.
    """

    class NotRegistered(PreconditionFailed):
        pass

    assert status_for(NotRegistered("x")) == 412
    assert NotRegistered("x").code == "NOT_REGISTERED"


def test_problem_details_carry_a_stable_code_and_leak_nothing(
    api, services, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = api.post(f"{API_PREFIX}/does-not-exist", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 404
    # FastAPI's own 404 is not a Problem Details document; what matters here is
    # that no handler leaks a path or a traceback. The Problem shape itself is
    # asserted on the refusals the middlewares produce, below.
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


# --- transport limits -------------------------------------------------------


def test_oversize_body_is_refused_before_routing(services) -> None:
    """413 with a declared Content-Length, and 413 without one.

    The path does not exist. That is the point: the refusal comes from
    middleware that runs before routing, so an oversize body is never read into
    a route, and the response does not reveal whether the path was real.
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


def test_a_body_within_the_limit_arrives_intact_at_the_route() -> None:
    """The limit must not eat the body it allows.

    Reading a request body inside `BaseHTTPMiddleware` exhausts the receive
    channel and leaves the route with nothing. That failure is invisible against
    a 404 - the status is the same either way - so this drives the middleware
    over a route that echoes what it received. If the replay were dropped, the
    echo would come back empty.
    """
    with TestClient(_echo_app()) as client:
        response = client.post("/echo", content=b"the exact bytes")

    assert response.status_code == 200
    assert response.json() == {"seen": "the exact bytes"}


def test_a_streaming_response_survives_the_body_limit_middleware() -> None:
    """The limit must not eat the *response* either, and once it did.

    `StreamingResponse` runs `listen_for_disconnect(receive)` concurrently with
    its send loop and cancels the whole task group the moment `receive()`
    reports a disconnect. The middleware's replay channel used to fabricate one
    as soon as the buffered body had been handed over, so every streamed
    response was cancelled before a single byte was written: `200`, correct
    headers, empty body.

    No JSON response listens for disconnect, so this was invisible from Stage A
    through Stage E and only surfaced when Stage F added the first streaming
    route. The regression lives here, at the middleware, rather than on an
    artifact route - the defect is not about artifacts, and a test on the
    download endpoint would stop covering it the day that endpoint changed.
    """
    app = FastAPI()

    @app.get("/stream")
    def stream() -> StreamingResponse:
        return StreamingResponse(iter([b"first-", b"second"]), media_type="text/plain")

    app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=1024)

    with TestClient(app) as client:
        response = client.get("/stream")

    assert response.status_code == 200
    assert response.content == b"first-second"


def _echo_app() -> FastAPI:
    """A minimal app whose one route reads the body the middleware replayed."""
    app = FastAPI()

    @app.post("/echo")
    async def echo(request: Request) -> dict[str, str]:
        return {"seen": (await request.body()).decode()}

    app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=1024)
    return app


# --- origin policy ----------------------------------------------------------


def test_a_mutation_without_an_origin_is_refused(api) -> None:
    response = api.post(f"{API_PREFIX}/does-not-exist", json={})

    assert response.status_code == 403
    assert response.json()["code"] == "ORIGIN_NOT_ALLOWED"


def test_a_mutation_from_a_foreign_origin_is_refused_without_echoing_it(api) -> None:
    foreign = "http://evil.example"
    response = api.post(f"{API_PREFIX}/does-not-exist", json={}, headers={"Origin": foreign})

    assert response.status_code == 403
    assert response.json()["code"] == "ORIGIN_NOT_ALLOWED"
    assert foreign not in response.text


def test_a_read_needs_no_origin(api) -> None:
    assert api.get(f"{API_PREFIX}/health").status_code == 200


def test_cors_is_never_a_wildcard(api) -> None:
    response = api.get(f"{API_PREFIX}/health", headers={"Origin": ALLOWED_ORIGIN})

    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    for value in response.headers.values():
        assert value != "*"


def test_the_development_origin_is_one_origin_and_only_when_configured(services) -> None:
    vite = "http://localhost:5173"
    base = build_api_services(services)
    without = create_app(base)
    with TestClient(without) as client:
        refused = client.post(f"{API_PREFIX}/does-not-exist", json={}, headers={"Origin": vite})
    assert refused.status_code == 403

    with_vite = replace(base, limits=replace(base.limits, dev_origin=vite))
    with TestClient(create_app(with_vite)) as client:
        accepted = client.post(f"{API_PREFIX}/does-not-exist", json={}, headers={"Origin": vite})
    assert accepted.status_code == 404


# --- contract drift ---------------------------------------------------------


def test_the_committed_openapi_schema_matches_the_application() -> None:
    """The same shape as the frozen SQLite fingerprint.

    A committed contract that silently disagrees with the code is worse than no
    committed contract: the TypeScript types are generated from this file, so a
    drifted schema means the frontend is typed against an API that no longer
    exists.
    """
    assert OUTPUT.is_file(), (
        "openapi/openapi.json is missing; run `python openapi/generate_openapi.py`"
    )
    assert OUTPUT.read_text(encoding="utf-8") == render(build_schema()), (
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
    """
    assert _path_shaped_contract_names(build_schema()) == []


def test_the_path_shaped_name_guard_actually_matches_something() -> None:
    """A blind guard reporting zero is worse than no guard (M3 Stage A, lesson 3).

    So the detector is run against a schema that does contain the shape it hunts
    for. If this stops finding anything, the pattern has been broken and the
    test above has quietly stopped proving anything.
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
