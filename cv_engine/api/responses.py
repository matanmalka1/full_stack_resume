"""The one place an accepted Operation becomes a `202` with a `Location`.

Every asynchronous command in the slice - analyze, draft generation, section and
claim regeneration, AI plan proposal, render - returns the same thing: the
Operation the client is now to poll. Writing that in each router is how one of
them ends up returning `200`, or `202` with no `Location`, and a client that
polls one endpoint successfully then cannot poll another.

The helper sets the status itself rather than relying on the route's
`status_code`, because `POST /analyses/{id}/selection-plans` is specified as
`201` for deterministic mode and `202` for AI proposal mode: one route, two
statuses, decided per request.
"""

from __future__ import annotations

from fastapi import Response, status

from ..application.operations import OperationView
from .schemas.operations import OperationResponse
from .versioning import API_PREFIX


def operation_location(operation_id: str) -> str:
    """Where an accepted Operation is polled. One spelling, one route."""
    return f"{API_PREFIX}/operations/{operation_id}"


def operation_response(operation: OperationView) -> OperationResponse:
    """The one mapping from the application view to the HTTP representation."""
    return OperationResponse.model_validate(operation.model_dump(mode="json"))


def accepted_operation(response: Response, operation: OperationView) -> OperationResponse:
    """`202 Accepted` plus the `Location` of the Operation to poll (§21, §22).

    The body is the same representation `GET /operations/{id}` returns, so a
    client can render progress from the acceptance response without a second
    request, and the `Location` is what it polls from then on.
    """
    response.status_code = status.HTTP_202_ACCEPTED
    response.headers["Location"] = operation_location(operation.id)
    return operation_response(operation)
