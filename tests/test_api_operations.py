"""M3 Stage C: the Operations surface, and the harness that makes it observable.

Stage D onwards submits Operations over HTTP. Until those endpoints exist the
work is submitted through the application service the CLI already uses, which is
the point: the Operation is the same durable row either way, and the endpoints
under test are the ones that report and steer it.
"""

from __future__ import annotations

from api_harness import MUTATION_HEADERS
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
    assert cancelled.json()["available_actions"] == ["retry"]
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
    assert retried.json()["available_actions"] == ["cancel"]
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
