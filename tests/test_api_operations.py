"""M3 Stage C: the Operations surface, and the harness that makes it observable.

Stage D onwards submits Operations over HTTP. Until those endpoints exist the
work is submitted through the application service the CLI already uses, which is
the point: the Operation is the same durable row either way, and the endpoints
under test are the ones that report and steer it.
"""

from __future__ import annotations

import pytest
from api_harness import MUTATION_HEADERS, OPERATION_RESPONSE_FIELDS
from fastapi.testclient import TestClient
from helpers import ACCOUNT_MANAGER_JOB

from cv_engine.api.app import API_PREFIX, create_app
from cv_engine.application.commands import AnalyzeCommand, IngestCommand
from cv_engine.runtime.composition import build_api_services


def _queued_analysis(services, company: str, *, idempotency_key: str = "stage-c-analysis"):
    """One real queued Operation: exactly what `cv analyze` submits."""
    ingested = services.applications.ingest(
        IngestCommand(
            company=company,
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
            acknowledged_duplicates=True,
        )
    )
    return services.operations.submit_analysis(
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_snapshot_id=ingested.job_snapshot_id,
        ),
        idempotency_key=idempotency_key,
        analysis_service=services.analysis,
    )


# --- the harness ------------------------------------------------------------


def test_a_worker_beside_the_app_drives_a_queued_operation_to_success(api_worker) -> None:
    """The harness is the subject: the app answers while the worker executes.

    `create_app` starts nothing. If the two were not running side by side this
    Operation would stay queued forever, so a terminal status here is the proof
    that the arrangement works - and the same proof stages D to G depend on.
    """
    operation = _queued_analysis(api_worker.services, "Harness Co")
    assert operation.status.value == "queued"

    finished = api_worker.wait_for_operation(operation.id)

    assert finished["status"] == "succeeded"
    assert finished["phase"] == "completed"
    assert finished["failure_code"] is None
    assert finished["started_at"] is not None and finished["finished_at"] is not None
    assert {output["output_type"] for output in finished["outputs"]} == {
        "job_analysis",
        "selection_plan",
    }
    assert all(output["active"] for output in finished["outputs"])


def test_the_operation_response_carries_no_runner_only_field(api_worker) -> None:
    """The narrowing is asserted at the wire, not only in the type.

    The payload is the command the caller already sent, the sources and the
    lease are runner state, and the idempotency key is the credential for
    replaying a write. The field set is compared against the schema rather than
    a hand-written list, so a field added to `PersistedOperation` cannot appear
    here without this failing.
    """
    operation = _queued_analysis(api_worker.services, "Narrowing Co")
    body = api_worker.wait_for_operation(operation.id)

    assert set(body) == OPERATION_RESPONSE_FIELDS
    assert not {
        "payload",
        "payload_hash",
        "idempotency_key",
        "sources",
        "resources",
        "installation_id",
        "lease_owner",
        "lease_expires_at",
        "heartbeat_at",
        "attempts_completed",
        "technical_log_reference",
    } & set(body)


def test_active_operation_is_projected_as_the_same_operation_representation(services) -> None:
    """One representation, whether polled directly or read from the projection.

    This is also the regression test for a leak that predates Stage C: the
    adapter narrowed `active_operation` by handing the record to
    `OperationView.model_validate`, which returns a `PersistedOperation`
    untouched rather than narrowing it. The projection then dumped all of it, so
    `GET /applications/{id}` carried the payload, the frozen sources, the lease,
    and the idempotency key inside `active_operation`.
    """
    operation = _queued_analysis(services, "Projection Co")

    with TestClient(create_app(build_api_services(services))) as api:
        polled = api.get(f"{API_PREFIX}/operations/{operation.id}")
        detail = api.get(f"{API_PREFIX}/applications/{operation.application_id}")

    assert polled.status_code == 200
    assert detail.status_code == 200
    assert set(detail.json()["active_operation"]) == OPERATION_RESPONSE_FIELDS
    assert detail.json()["active_operation"] == polled.json()


# --- cancel -----------------------------------------------------------------


def test_cancelling_queued_work_is_recorded_and_the_work_never_runs(services) -> None:
    """No worker here on purpose: queued work must be cancelled before it starts."""
    operation = _queued_analysis(services, "Cancel Co")

    with TestClient(create_app(build_api_services(services))) as api:
        cancelled = api.post(
            f"{API_PREFIX}/operations/{operation.id}/cancel",
            headers=MUTATION_HEADERS,
        )
        read_back = api.get(f"{API_PREFIX}/operations/{operation.id}")

    assert cancelled.status_code == 200
    assert "Location" not in cancelled.headers
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancellation_requested_at"] is not None
    assert read_back.json() == cancelled.json()
    assert services.repository.analyses(operation.application_id) == []


# --- retry ------------------------------------------------------------------


def test_retry_accepts_with_a_location_and_leaves_the_original_immutable(services) -> None:
    operation = _queued_analysis(services, "Retry Co")
    original_record = services.repository.operation(operation.id)

    with TestClient(create_app(build_api_services(services))) as api:
        api.post(f"{API_PREFIX}/operations/{operation.id}/cancel", headers=MUTATION_HEADERS)
        retried = api.post(
            f"{API_PREFIX}/operations/{operation.id}/retry",
            headers={**MUTATION_HEADERS, "Idempotency-Key": "stage-c-retry"},
        )
        followed = api.get(retried.headers["Location"])

    assert retried.status_code == 202
    queued_id = retried.json()["id"]
    assert queued_id != operation.id
    assert retried.headers["Location"] == f"{API_PREFIX}/operations/{queued_id}"
    assert retried.json()["retry_of_operation_id"] == operation.id
    assert retried.json()["status"] == "queued"
    assert followed.status_code == 200
    assert followed.json() == retried.json()
    assert services.repository.operation(operation.id).status.value == "cancelled"
    assert services.repository.operation(operation.id).payload == original_record.payload


def test_retry_replaying_a_used_idempotency_key_returns_the_same_operation(services) -> None:
    """Replay safety is what the header buys; without it every call is a new attempt."""
    operation = _queued_analysis(services, "Replay Co")

    with TestClient(create_app(build_api_services(services))) as api:
        api.post(f"{API_PREFIX}/operations/{operation.id}/cancel", headers=MUTATION_HEADERS)
        headers = {**MUTATION_HEADERS, "Idempotency-Key": "stage-c-replay"}
        first = api.post(f"{API_PREFIX}/operations/{operation.id}/retry", headers=headers)
        replayed = api.post(f"{API_PREFIX}/operations/{operation.id}/retry", headers=headers)
        generated = api.post(
            f"{API_PREFIX}/operations/{operation.id}/retry",
            headers=MUTATION_HEADERS,
        )

    assert replayed.status_code == 202
    assert replayed.json() == first.json()
    # No header means the boundary generates a key, so this is a second attempt
    # rather than a replay of the first.
    assert generated.status_code == 202
    assert generated.json()["id"] not in {first.json()["id"], operation.id}


def test_retrying_work_that_is_not_terminal_is_a_conflict(services) -> None:
    operation = _queued_analysis(services, "Live Retry Co")

    with TestClient(create_app(build_api_services(services))) as api:
        refused = api.post(
            f"{API_PREFIX}/operations/{operation.id}/retry",
            headers=MUTATION_HEADERS,
        )

    assert refused.status_code == 409
    assert refused.json()["code"] == "STATE_CONFLICT"
    assert refused.json()["type"] == "about:blank#state_conflict"


# --- refusals ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/operations/missing-operation"),
        ("post", "/operations/missing-operation/cancel"),
        ("post", "/operations/missing-operation/retry"),
    ],
)
def test_an_unknown_operation_is_a_404_on_every_route(services, method: str, path: str) -> None:
    with TestClient(create_app(build_api_services(services))) as api:
        response = getattr(api, method)(f"{API_PREFIX}{path}", headers=MUTATION_HEADERS)

    assert response.status_code == 404
    assert response.json()["code"] == "UNKNOWN_RECORD"


@pytest.mark.parametrize("path", ["/cancel", "/retry"])
def test_steering_an_operation_requires_a_known_origin(services, path: str) -> None:
    operation = _queued_analysis(services, f"Origin {path.strip('/')} Co")

    with TestClient(create_app(build_api_services(services))) as api:
        refused = api.post(f"{API_PREFIX}/operations/{operation.id}{path}")

    assert refused.status_code == 403
    assert refused.json()["code"] == "ORIGIN_NOT_ALLOWED"
    assert services.repository.operation(operation.id).status.value == "queued"
