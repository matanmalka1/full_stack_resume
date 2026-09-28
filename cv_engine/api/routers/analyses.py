from __future__ import annotations

from fastapi import APIRouter, status

from ...application.commands import ApplyAnalysisDecisionsCommand
from ..dependencies import Services
from ..schemas.analyses import AnalysisDecisionsResponse, ApplyAnalysisDecisionsRequest
from ..schemas.applications import ApplicationStateResponse

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
    """`201`: a meaning change creates an immutable JobAnalysis; a selection-only
    change updates the document's selection in place (§13).

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
    state = services.queries.application_detail(request.application_id)
    state_document = state.model_dump(mode="json")
    projected = ApplicationStateResponse.model_validate(
        {name: state_document[name] for name in ApplicationStateResponse.model_fields}
    )
    return AnalysisDecisionsResponse.model_validate(
        {
            **result.model_dump(mode="json"),
            "state": projected,
        }
    )
