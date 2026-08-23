from __future__ import annotations

from fastapi import APIRouter, status

from ...application.commands import (
    ApplyAnalysisDecisionsCommand,
    CreateSelectionPlanCommand,
)
from ..dependencies import Services
from ..schemas.analyses import (
    AnalysisDecisionsResponse,
    ApplyAnalysisDecisionsRequest,
    CreateSelectionPlanRequest,
    CreateSelectionPlanResponse,
)

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post(
    "/{analysis_id}/decisions",
    response_model=AnalysisDecisionsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apply one review-form submission to an analysis",
)
def apply_analysis_decisions(
    analysis_id: str,
    request: ApplyAnalysisDecisionsRequest,
    services: Services,
) -> AnalysisDecisionsResponse:
    """`201`: both branches create an immutable record and neither mutates one.

    `application_id` is in the body rather than inferred from the analysis. The
    client states which Application it believes it is deciding for, and a
    mismatch is a `412` naming the broken lineage instead of a decision landing
    silently on another Application's analysis.
    """
    result = services.analysis.apply_analysis_decisions(
        ApplyAnalysisDecisionsCommand(
            job_analysis_id=analysis_id,
            **request.model_dump(mode="python"),
        )
    )
    return AnalysisDecisionsResponse.model_validate(result.model_dump(mode="json"))


@router.post(
    "/{analysis_id}/selection-plans",
    response_model=CreateSelectionPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a replacement SelectionPlan for an analysis",
)
def create_selection_plan(
    analysis_id: str,
    request: CreateSelectionPlanRequest,
    services: Services,
) -> CreateSelectionPlanResponse:
    """`201` and the plan itself: the deterministic form is synchronous (§13).

    The AI `propose_selection_plan` mode is the same route answering `202` with
    a `Location`, decided per request rather than per route, which is why the
    shared acceptance helper sets its own status.
    """
    result = services.analysis.create_selection_plan(
        CreateSelectionPlanCommand(
            job_analysis_id=analysis_id,
            **request.model_dump(mode="python"),
        )
    )
    return CreateSelectionPlanResponse.model_validate(result.model_dump(mode="json"))
