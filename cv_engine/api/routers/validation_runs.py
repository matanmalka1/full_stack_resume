from __future__ import annotations

from fastapi import APIRouter

from ..dependencies import Services
from ..schemas.drafts import ValidationRunResponse

router = APIRouter(prefix="/validation-runs", tags=["validation-runs"])


@router.get(
    "/{validation_run_id}",
    response_model=ValidationRunResponse,
    summary="Read one immutable ValidationRun, including stale historical evidence",
)
def validation_run(validation_run_id: str, services: Services) -> ValidationRunResponse:
    result = services.queries.validation_run(validation_run_id)
    return ValidationRunResponse.model_validate(result.model_dump(mode="json"))
