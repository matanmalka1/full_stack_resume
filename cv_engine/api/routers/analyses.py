from __future__ import annotations

from fastapi import APIRouter, Response, status

from ...application.commands import (
    ApplyAnalysisDecisionsCommand,
    CreateSelectionPlanCommand,
    ProposeSelectionPlanCommand,
)
from ...application.errors import PreconditionFailed
from ...util import new_id
from ..dependencies import Services
from ..headers import IdempotencyKey
from ..responses import accepted_operation
from ..schemas.analyses import (
    AnalysisDecisionsResponse,
    ApplyAnalysisDecisionsRequest,
    CreateSelectionPlanRequest,
    CreateSelectionPlanResponse,
)
from ..schemas.operations import OperationResponse

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post(
    "/{analysis_id}/apply-decisions",
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

    Dumped as JSON, not Python: the override fields are `StrEnum` members on the
    schema, and the command, the recorded `user_override`, and the stored
    analysis all hold plain strings. Handing the member across would make the
    stored value's exact type depend on how Pydantic coerces a `str` subclass.
    """
    result = services.analysis.apply_analysis_decisions(
        ApplyAnalysisDecisionsCommand(
            job_analysis_id=analysis_id,
            **request.model_dump(mode="json"),
        )
    )
    return AnalysisDecisionsResponse.model_validate(result.model_dump(mode="json"))


@router.post(
    "/{analysis_id}/selection-plans",
    response_model=CreateSelectionPlanResponse | OperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a replacement SelectionPlan for an analysis",
)
def create_selection_plan(
    analysis_id: str,
    request: CreateSelectionPlanRequest,
    services: Services,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> CreateSelectionPlanResponse | OperationResponse:
    """`201` and the plan itself in deterministic mode; `202` in AI mode (§13).

    One route, two statuses, decided per request rather than per route - which
    is why the acceptance helper sets its own status instead of the decorator
    doing it. `201` means the immutable plan exists and is in the body; `202`
    means a provider will be asked and the `Location` is what to poll.

    No provider call happens inside this request in either branch. That is the
    §13 rule, and it is why the AI branch queues an Operation rather than
    awaiting an answer.
    """
    body = request.model_dump(mode="python")
    mode = body.pop("mode")
    overlay = {
        "pinned_fact_ids": body.pop("pinned_fact_ids"),
        "excluded_fact_ids": body.pop("excluded_fact_ids"),
        "accepted_requirement_ids": body.pop("accepted_requirement_ids"),
        "acceptance_reason": body.pop("acceptance_reason"),
        "expected_selection_plan_id": body.pop("expected_selection_plan_id"),
    }
    if mode == "ai":
        if overlay["pinned_fact_ids"] or overlay["excluded_fact_ids"]:
            raise PreconditionFailed(
                "AI mode proposes the fact overlay; submit pins and exclusions "
                "through the deterministic mode instead"
            )
        if overlay["accepted_requirement_ids"]:
            # Proceeding despite a known deficiency is the user's judgement,
            # and a provider must not be able to express it at all.
            raise PreconditionFailed(
                "accepting a gap is a user decision; submit it through the "
                "deterministic mode instead"
            )
        queued = services.operations.submit_selection_plan_proposal(
            ProposeSelectionPlanCommand(job_analysis_id=analysis_id, **body),
            idempotency_key=idempotency_key or new_id(),
            analysis_service=services.analysis,
        )
        return accepted_operation(response, queued)
    result = services.analysis.create_selection_plan(
        CreateSelectionPlanCommand(job_analysis_id=analysis_id, **overlay, **body)
    )
    return CreateSelectionPlanResponse.model_validate(result.model_dump(mode="json"))
