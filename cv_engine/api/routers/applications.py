from __future__ import annotations

from fastapi import APIRouter, Response, status

from ...application.commands import (
    AnalyzeCommand,
    CloseApplicationCommand,
    CreateJobSnapshotCommand,
    DuplicateCheckCommand,
    IngestCommand,
)
from ...util import new_id
from ..dependencies import Services
from ..headers import IdempotencyKey
from ..responses import accepted_operation
from ..schemas.analyses import CreateAnalysisRequest
from ..schemas.applications import (
    ApplicationDetailResponse,
    ApplicationListResponse,
    ArtifactVersionsResponse,
    CloseApplicationResponse,
    CreateApplicationRequest,
    CreateApplicationResponse,
    CreateJobSnapshotRequest,
    CreateJobSnapshotResponse,
    DecisionRecordResponse,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
)
from ..schemas.operations import OperationResponse

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post(
    "/duplicate-check",
    response_model=DuplicateCheckResponse,
    summary="Check for possible duplicate applications",
)
def duplicate_check(request: DuplicateCheckRequest, services: Services) -> DuplicateCheckResponse:
    result = services.applications.duplicate_check(
        DuplicateCheckCommand(**request.model_dump(mode="python"))
    )
    return DuplicateCheckResponse.model_validate(result.model_dump(mode="json"))


@router.post(
    "",
    response_model=CreateApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an application and its first immutable job snapshot",
)
def create_application(
    request: CreateApplicationRequest, services: Services
) -> CreateApplicationResponse:
    result = services.applications.ingest(
        IngestCommand(
            **request.model_dump(mode="python"),
            actor_type="user",
            client="web",
        )
    )
    return CreateApplicationResponse.model_validate(result.model_dump(mode="json"))


@router.get("", response_model=ApplicationListResponse, summary="List applications")
def list_applications(services: Services) -> ApplicationListResponse:
    result = services.queries.list_applications()
    return ApplicationListResponse.model_validate(result.model_dump(mode="json"))


@router.get(
    "/{application_id}",
    response_model=ApplicationDetailResponse,
    summary="Read an application and its active preparation state",
)
def application_detail(application_id: str, services: Services) -> ApplicationDetailResponse:
    result = services.queries.application_detail(application_id)
    return ApplicationDetailResponse.model_validate(result.model_dump(mode="json"))


@router.get(
    "/{application_id}/artifacts",
    response_model=ArtifactVersionsResponse,
    summary="List registered artifact metadata for an application",
)
def artifact_versions(application_id: str, services: Services) -> ArtifactVersionsResponse:
    result = services.queries.artifact_versions(application_id)
    return ArtifactVersionsResponse.model_validate(result.model_dump(mode="json"))


@router.get(
    "/{application_id}/decision",
    response_model=DecisionRecordResponse,
    summary="Read the latest decision record for an application",
)
def latest_decision(application_id: str, services: Services) -> DecisionRecordResponse:
    result = services.queries.latest_decision(application_id)
    return DecisionRecordResponse.model_validate(result.model_dump(mode="json"))


@router.post(
    "/{application_id}/job-snapshots",
    response_model=CreateJobSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new immutable job snapshot",
)
def create_job_snapshot(
    application_id: str,
    request: CreateJobSnapshotRequest,
    services: Services,
) -> CreateJobSnapshotResponse:
    result = services.applications.create_job_snapshot(
        CreateJobSnapshotCommand(
            application_id=application_id,
            **request.model_dump(mode="python"),
            actor_type="user",
            client="web",
        )
    )
    return CreateJobSnapshotResponse.model_validate(result.model_dump(mode="json"))


@router.post(
    "/{application_id}/analyses",
    response_model=OperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Analyze one exact job snapshot",
)
def create_analysis(
    application_id: str,
    request: CreateAnalysisRequest,
    services: Services,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> OperationResponse:
    """`202` and a `Location`: analysis is a durable Operation (§13).

    NeedsReview is not an error here or anywhere else. An analysis that needs a
    decision is a *successful* Operation whose JobAnalysis and initial
    SelectionPlan were both committed; what needs deciding is reported by the
    Application's review reasons, and is resolved through
    `POST /analyses/{id}/decisions`.
    """
    queued = services.operations.submit_analysis(
        AnalyzeCommand(
            application_id=application_id,
            **request.model_dump(mode="python"),
        ),
        idempotency_key=idempotency_key or new_id(),
        analysis_service=services.analysis,
    )
    return accepted_operation(response, queued)


@router.post(
    "/{application_id}/close",
    response_model=CloseApplicationResponse,
    summary="Close an application without deleting its history",
)
def close_application(application_id: str, services: Services) -> CloseApplicationResponse:
    result = services.tracking.close_application(
        CloseApplicationCommand(
            application_id=application_id,
            actor_type="user",
            client="web",
        )
    )
    return CloseApplicationResponse.model_validate(result.model_dump(mode="json"))
