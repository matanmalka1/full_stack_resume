"""The app and an `OperationWorker`, side by side, as the two processes run them.

`create_app` starts no worker: FastAPI is a server, not a process manager, and a
worker bound to an app lifespan would start a second one for every `TestClient`.
The harness therefore starts the two hosts side by side, as independent
production processes would run them.

It has to exist for the Operation endpoints to mean anything. A `202` and a
`Location` are only true if something is executing the queue, and a status that
never becomes terminal is not progress. Polling over HTTP - rather than reading
the repository - is deliberate: the polling surface is what a client actually
has, so that is what the tests drive.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from threading import Event, Thread
from time import monotonic, sleep
from typing import Any

from fake_provider import FakeOpenAI
from fastapi.testclient import TestClient
from helpers import trivial_requirement_extraction

from cv_engine.api.app import API_PREFIX, DEFAULT_PORT, create_app
from cv_engine.api.schemas.operations import OperationResponse
from cv_engine.application.operations import TERMINAL_OPERATION_STATUSES
from cv_engine.domain.models import JobClassificationProposal
from cv_engine.runtime.composition import Services, build_api_services

ALLOWED_ORIGIN = f"http://127.0.0.1:{DEFAULT_PORT}"
MUTATION_HEADERS = {"Origin": ALLOWED_ORIGIN}

#: Derived from the lifecycle contract rather than restated, so a new terminal
#: status cannot leave the harness waiting forever for work that has finished.
TERMINAL_STATUSES = frozenset(status.value for status in TERMINAL_OPERATION_STATUSES)

#: What the Operation representation actually publishes, for the several tests that
#: assert the wire carries the schema and nothing wider. `model_fields` alone is not
#: that set: `is_terminal` is a computed field, so it appears on the wire and in the
#: OpenAPI schema while living in `model_computed_fields`. The union keeps those
#: assertions exact in both directions - a runner-only field leaking onto the wire is
#: in neither collection and still fails - and it lives here rather than in each test
#: module so the three call sites cannot drift apart.
OPERATION_RESPONSE_FIELDS = frozenset(OperationResponse.model_fields) | frozenset(
    OperationResponse.model_computed_fields
)

WORKER_STOP_TIMEOUT_SECONDS = 5.0
OPERATION_TIMEOUT_SECONDS = 20.0

#: A generic, always-accepted classification for tests whose subject is not
#: analysis semantics - only that some analysis exists to build on.
_OFFLINE_CLASSIFICATION = JobClassificationProposal(
    track="sales",
    profile="account-manager",
    emphasis="account-growth",
    language="en",
    confidence=0.99,
    rationale="fixture",
    keywords=[],
)


@dataclass(frozen=True)
class ApiHarness:
    """One HTTP client and the application services the worker shares with it.

    `fake_openai` is set only on a provider-backed harness (`ai_api_worker`);
    a plain one (`api_worker`) leaves it `None`, and `analyze_offline` refuses
    to run without it rather than reaching the network.
    """

    client: TestClient
    services: Services
    fake_openai: FakeOpenAI | None = None

    def operation(self, operation_id: str) -> dict[str, Any]:
        response = self.client.get(f"{API_PREFIX}/operations/{operation_id}")
        assert response.status_code == 200, response.text
        return response.json()

    def wait_for_operation(
        self,
        operation_id: str,
        *,
        timeout: float = OPERATION_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        """Poll the real endpoint until the Operation is terminal.

        A timeout reports the last body it saw. "Never finished" and "finished
        as something I did not expect" are different failures, and a bare
        timeout cannot tell them apart.
        """
        deadline = monotonic() + timeout
        while True:
            body = self.operation(operation_id)
            if body["status"] in TERMINAL_STATUSES:
                return body
            if monotonic() >= deadline:
                raise AssertionError(
                    f"Operation {operation_id} was still {body['status']} after {timeout}s: {body}"
                )
            sleep(0.02)


def analyze_offline(harness, application_id: str, job_text: str) -> dict[str, str]:
    """Create an analysis over HTTP with no real provider reachable.

    Works over any harness exposing `.client`, `.fake_openai`, and
    `.wait_for_operation()` - the worker-backed `ApiHarness` and the
    foreground-executed `PausedApiHarness` alike.

    D5 (product-spec.md §2) requires a configured AI provider for every new
    JobAnalysis - there is no rules-based fallback. `fake_openai` answers with
    a trivial extraction (every requirement-bearing line declared unmapped, so
    the analysis is honestly `extraction-failed`) and a generic classification,
    then the incomplete-analysis review reason is explicitly accepted the same
    way a user would through Apply Decisions - never silently, and never by
    widening what the analyze endpoint itself accepts
    (`AnalyzeCommand.accept_incomplete_analysis` does not exist for exactly
    that reason).

    For a test asserting on requirements, coverage, confidence, or Fit, script
    `fake_openai` explicitly instead and call this only for what it is: a way
    to reach a draftable analysis without asserting what is in it.
    """
    assert harness.fake_openai is not None, "analyze_offline needs a provider-backed harness"
    concepts = harness.services.analysis.load_knowledge().requirement_concepts
    harness.fake_openai.script(
        "propose_requirement_extraction",
        trivial_requirement_extraction(job_text, concepts),
    )
    harness.fake_openai.script("propose_job_analysis", _OFFLINE_CLASSIFICATION)
    detail = harness.client.get(f"{API_PREFIX}/applications/{application_id}")
    assert detail.status_code == 200, detail.text
    response = harness.client.post(
        f"{API_PREFIX}/applications/{application_id}/analyses",
        json={"job_snapshot_id": detail.json()["active_job_snapshot_id"]},
        headers=MUTATION_HEADERS,
    )
    assert response.status_code == 202, response.text
    finished = harness.wait_for_operation(response.json()["id"])
    assert finished["status"] == "succeeded", finished
    outputs = {item["output_type"]: item["output_id"] for item in finished["outputs"]}
    accepted = harness.client.post(
        f"{API_PREFIX}/analyses/{outputs['job_analysis']}/apply-decisions",
        json={
            "application_id": application_id,
            "expected_analysis_id": outputs["job_analysis"],
            "expected_selection_plan_id": outputs["selection_plan"],
            "accept_incomplete_analysis": True,
        },
        headers=MUTATION_HEADERS,
    )
    assert accepted.status_code == 201, accepted.text
    body = accepted.json()
    return {
        "job_analysis": body["job_analysis_id"],
        "selection_plan": body["selection_plan_id"],
    }


@contextmanager
def api_with_worker(services: Services, *, fake_openai: FakeOpenAI | None = None):
    """Run the composed app and the composed worker together for one test.

    The worker is the one the composition root built, not a second wiring: a
    harness that assembled its own runner would prove the harness works rather
    than the product. `fake_openai` is the same instance `services` was built
    with, threaded through so `ApiHarness.analyze_offline` can script it.
    """
    stop = Event()
    thread = Thread(
        target=services.operation_worker.serve,
        args=(stop,),
        name="test-operation-worker",
        daemon=True,
    )
    with TestClient(create_app(build_api_services(services))) as client:
        thread.start()
        try:
            yield ApiHarness(client=client, services=services, fake_openai=fake_openai)
        finally:
            stop.set()
            thread.join(timeout=WORKER_STOP_TIMEOUT_SECONDS)
    assert not thread.is_alive(), "the Operation worker did not stop when asked"
