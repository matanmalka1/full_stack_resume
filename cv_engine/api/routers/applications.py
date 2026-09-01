from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from ...application.commands import (
    AnalyzeCommand,
    CloseApplicationCommand,
    CreateJobSnapshotCommand,
    DraftCommand,
    DuplicateCheckCommand,
    IngestCommand,
    ReplaceWorkingDraftCommand,
    UpdateApplicationNotesCommand,
)
from ...application.queries import (
    ActivityFilter,
    ApplicationListQuery,
    ApplicationPreset,
    ApplicationSort,
    PreparationState,
    RecruitmentStatus,
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
    UpdateApplicationNotesRequest,
    UpdateApplicationNotesResponse,
)
from ..schemas.drafts import GenerateWorkingDraftRequest, ReplaceWorkingDraftRequest
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
def list_applications(
    services: Services,
    activity: ActivityFilter = ActivityFilter.ALL,
    stage: Annotated[list[PreparationState] | None, Query()] = None,
    recruitment_status: Annotated[list[RecruitmentStatus] | None, Query()] = None,
    preset: ApplicationPreset | None = None,
    search: str = "",
    sort: ApplicationSort = ApplicationSort.UPDATED,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApplicationListResponse:
    """One page of the list, narrowed by the query the application layer answers.

    The router maps HTTP to that query and back and decides nothing about it:
    the closed sets arrive as their application-layer enums, so an unknown value
    is a 422 from the boundary rather than a filter that silently matches
    nothing. `stage` repeats for more than one stage. The paging bounds are
    restated here so an out-of-range page is refused at the boundary with a 422
    naming the parameter, rather than reaching the query and failing as a
    validation error the client cannot attribute.

    `stage` and `recruitment_status` are the two independent axes and repeat for
    more than one value; `preset` is one named question the application layer
    answers, and it narrows alongside them rather than replacing them.
    """
    result = services.queries.list_applications(
        ApplicationListQuery(
            activity=activity,
            stages=frozenset(stage or ()),
            recruitment_statuses=frozenset(recruitment_status or ()),
            preset=preset,
            search=search,
            sort=sort,
            limit=limit,
            offset=offset,
        )
    )
    return ApplicationListResponse.model_validate(result.model_dump(mode="json"))


@router.get(
    "/{application_id}",
    response_model=ApplicationDetailResponse,
    summary="Read an application and its active preparation state",
)
def application_detail(application_id: str, services: Services) -> ApplicationDetailResponse:
    result = services.queries.application_detail(application_id)
    return ApplicationDetailResponse.model_validate(result.model_dump(mode="json"))


@router.patch(
    "/{application_id}/notes",
    response_model=UpdateApplicationNotesResponse,
    summary="Update safe mutable notes for an application",
)
def update_application_notes(
    application_id: str,
    request: UpdateApplicationNotesRequest,
    services: Services,
) -> UpdateApplicationNotesResponse:
    result = services.applications.update_notes(
        UpdateApplicationNotesCommand(
            application_id=application_id,
            **request.model_dump(mode="python"),
            actor_type="user",
            client="web",
        )
    )
    return UpdateApplicationNotesResponse.model_validate(result.model_dump(mode="json"))


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
    `POST /analyses/{id}/apply-decisions`.

    Dumped as JSON, not Python: the override fields are `StrEnum` members on the
    schema, and this command is persisted as the Operation's request payload. A
    payload holding enum members rather than plain strings would depend on how
    Pydantic coerces a `str` subclass to survive the round trip.
    """
    queued = services.operations.submit_analysis(
        AnalyzeCommand(
            application_id=application_id,
            **request.model_dump(mode="json"),
        ),
        idempotency_key=idempotency_key or new_id(),
        analysis_service=services.analysis,
    )
    return accepted_operation(response, queued)


@router.post(
    "/{application_id}/working-draft/generate",
    response_model=OperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate the active working draft from an exact analysis and plan",
)
def generate_working_draft(
    application_id: str,
    request: GenerateWorkingDraftRequest,
    services: Services,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> OperationResponse:
    """`202` and a `Location`: generation is a durable Operation (§14).

    Both sources are named by the client. The Operation freezes them, so an
    analysis or plan that moves before activation fails the source check as
    `SOURCE_CHANGED` instead of silently drafting from something else.
    """
    queued = services.operations.submit_draft(
        DraftCommand(
            application_id=application_id,
            **request.model_dump(mode="python"),
        ),
        idempotency_key=idempotency_key or new_id(),
        draft_service=services.drafts,
    )
    return accepted_operation(response, queued)


@router.post(
    "/{application_id}/working-draft/replace",
    response_model=OperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Replace the active working draft from an explicit analysis and plan",
)
def replace_working_draft(
    application_id: str,
    request: ReplaceWorkingDraftRequest,
    services: Services,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> OperationResponse:
    """`202` and a `Location`: replacement is the draft Operation (§14).

    Addressed to the Application, beside `generate`, because the Application is
    what owns the one active draft. The body still names the exact draft and the
    exact version being replaced, and a draft belonging to another Application
    is a `412` naming the broken lineage rather than a replacement landing
    somewhere nobody asked for.

    Nothing is deleted first. The Operation commits the new document over the
    same active record, so a failure leaves the existing draft untouched, and
    `keep_previous` materializes the historical snapshot before any of it
    starts.
    """
    queued = services.operations.submit_replacement_draft(
        ReplaceWorkingDraftCommand(
            application_id=application_id,
            **request.model_dump(mode="python"),
            actor_type="user",
            client="web",
        ),
        idempotency_key=idempotency_key or new_id(),
        draft_service=services.drafts,
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
