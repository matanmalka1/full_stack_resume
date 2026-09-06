"""Immutable SelectionPlan detail and candidate accounting."""

from __future__ import annotations

from fastapi import APIRouter

from ..dependencies import Services
from ..schemas.analyses import SelectionPlanDetailResponse

router = APIRouter(prefix="/selection-plans", tags=["selection-plans"])


@router.get(
    "/{selection_plan_id}",
    response_model=SelectionPlanDetailResponse,
    summary="Read one SelectionPlan and its candidate accounting",
)
def selection_plan_detail(
    selection_plan_id: str,
    services: Services,
) -> SelectionPlanDetailResponse:
    result = services.queries.selection_plan(selection_plan_id)
    return SelectionPlanDetailResponse.model_validate(result.model_dump(mode="json"))
