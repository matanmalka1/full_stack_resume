"""The ApprovedRevision surface: render it, read its Ready qualification, export its PDF.

Render is the last asynchronous command in the deterministic slice and it goes
through the same `accepted_operation` helper as analyze and generate, so a
client polls all three the same way. It carries no special-case status.

Ready is **not recomputed here**. `ready_qualified` is re-derived from the
revision's own stored evidence by `qualify_ready_revision`, and the active
`PreparationState` is derived by the projection - a router that decided either
would be a second authority on the question, and the two would eventually
disagree. This router asks and reports.

The recruiter export names both IDs because §16's use case takes both. It is
the one artifact route that requires `ready_qualified`; the plain
`/artifacts/{id}/download` deliberately does not, and the difference is stated
on the application methods rather than encoded in a route's shape.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Response, status
from fastapi.responses import StreamingResponse

from ...application.commands import RenderCommand
from ...util import new_id
from ..dependencies import Services
from ..headers import IdempotencyKey
from ..responses import accepted_operation, artifact_response
from ..schemas.artifacts import ApprovedRevisionResponse, RenderRevisionRequest
from ..schemas.operations import OperationResponse

router = APIRouter(prefix="/approved-revisions", tags=["approved-revisions"])


@router.get(
    "/{approved_revision_id}",
    response_model=ApprovedRevisionResponse,
    summary="Read one approved revision and its Ready qualification",
)
def approved_revision_detail(
    approved_revision_id: str, services: Services
) -> ApprovedRevisionResponse:
    """`200` with the immutable record and a freshly re-derived qualification (§20).

    A revision superseded by a newer JobSnapshot still answers here, still
    reports `ready_qualified`, and is still exportable. What it stops being is
    the Application's active `preparation_state`, which is a different question
    asked at a different resource.
    """
    result = services.queries.approved_revision(approved_revision_id)
    return ApprovedRevisionResponse.model_validate(result.model_dump(mode="json"))


@router.post(
    "/{approved_revision_id}/render",
    response_model=OperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Render one exact approved revision",
)
def render_revision(
    approved_revision_id: str,
    request: RenderRevisionRequest,
    services: Services,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> OperationResponse:
    """`202` and a `Location`: rendering is a durable Operation (§16).

    A failed render leaves the ApprovedRevision approved. Nothing in the render
    path writes to the revision - it is immutable - so the failure is recorded
    on the Operation and in a `rendered-invalid` artifact lifecycle, and the
    revision is exactly as approvable-from as it was. Retrying is
    `POST /operations/{id}/retry`, which creates a *new* Operation rather than
    reopening the failed one.

    The same `Idempotency-Key` with the same payload returns the Operation it
    already created instead of queueing a second render.
    """
    queued = services.operations.submit_render(
        RenderCommand(
            application_id=request.application_id,
            approved_revision_id=approved_revision_id,
        ),
        idempotency_key=idempotency_key or new_id(),
        rendering_service=services.rendering,
    )
    return accepted_operation(response, queued)


@router.get(
    "/{approved_revision_id}/recruiter-pdf",
    summary="Export the exact Ready PDF under its recruiter-facing filename",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "The rendered PDF, named as a recruiter should see it.",
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
def export_recruiter_pdf(
    approved_revision_id: str,
    services: Services,
    pdf_artifact_version_id: str = Query(
        description=(
            "The exact rendered PDF to export. Required and explicit: an export "
            "that resolved the latest PDF for itself could hand over a different "
            "document than the one the caller verified."
        ),
    ),
) -> StreamingResponse:
    """`200` and the PDF; `412` when this exact pair is not Ready-qualified.

    Both IDs are checked against each other before qualification is computed,
    so a PDF belonging to another revision is `412 LINEAGE_BROKEN` rather than
    a qualification run against a mismatched pair.
    """
    delivery = services.rendering.export_recruiter_pdf(
        approved_revision_id, pdf_artifact_version_id
    )
    return artifact_response(delivery)
