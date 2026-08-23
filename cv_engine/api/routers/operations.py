from __future__ import annotations

from fastapi import APIRouter, Response, status

from ...util import new_id
from ..dependencies import Services
from ..headers import IdempotencyKey
from ..responses import accepted_operation, operation_response
from ..schemas.operations import OperationResponse

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get(
    "/{operation_id}",
    response_model=OperationResponse,
    summary="Read the progress of one durable Operation",
)
def operation(operation_id: str, services: Services) -> OperationResponse:
    return operation_response(services.operations.get(operation_id))


@router.post(
    "/{operation_id}/cancel",
    response_model=OperationResponse,
    summary="Cancel queued work, or ask running work to stop",
)
def cancel_operation(operation_id: str, services: Services) -> OperationResponse:
    """`200`, not `202`: cancellation is recorded synchronously.

    Queued work is cancelled outright. Running work has
    `cancellation_requested_at` recorded and stops at its next checkpoint, so the
    returned status is truthfully still `running` - the request is what
    completed, not the Operation.
    """
    return operation_response(services.operations.cancel(operation_id))


@router.post(
    "/{operation_id}/retry",
    response_model=OperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue a new Operation retrying a terminal one",
)
def retry_operation(
    operation_id: str,
    services: Services,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> OperationResponse:
    """`202` and a `Location` naming the *new* Operation.

    The original is immutable and is not touched. Only a terminal Operation can
    be retried; retrying a live one is a `409`.
    """
    queued = services.operations.retry(
        operation_id,
        idempotency_key=idempotency_key or new_id(),
    )
    return accepted_operation(response, queued)
