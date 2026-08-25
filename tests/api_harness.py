"""The app and an `OperationWorker`, side by side, as `cv web` will host them.

`create_app` starts no worker: FastAPI is a server, not a process manager, and a
worker bound to an app lifespan would start a second one for every `TestClient`.
So the arrangement the M6 supervisor will make is made here instead, in a
harness the API tests share.

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

from fastapi.testclient import TestClient

from cv_engine.api.app import API_PREFIX, DEFAULT_PORT, create_app
from cv_engine.api.schemas.operations import OperationResponse
from cv_engine.application.operations import TERMINAL_OPERATION_STATUSES
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


@dataclass(frozen=True)
class ApiHarness:
    """One HTTP client and the application services the worker shares with it."""

    client: TestClient
    services: Services

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


@contextmanager
def api_with_worker(services: Services):
    """Run the composed app and the composed worker together for one test.

    The worker is the one the composition root built, not a second wiring: a
    harness that assembled its own runner would prove the harness works rather
    than the product.
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
            yield ApiHarness(client=client, services=services)
        finally:
            stop.set()
            thread.join(timeout=WORKER_STOP_TIMEOUT_SECONDS)
    assert not thread.is_alive(), "the Operation worker did not stop when asked"
