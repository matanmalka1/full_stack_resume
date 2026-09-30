"""The CV document surface (state-and-use-cases.md §14–§16, §21).

Every route is one application command or one application query, addressed to the
Application because it owns exactly one document. The router parses the transport -
the ETag, the idempotency key, the path ID - and hands the application layer explicit
arguments; it holds no rule about when a save is allowed, what a check means, or what
approval or Ready requires.

`If-Match` is required on `PATCH` and nowhere else. Every action carries
`expected_document_hash` in the body instead: an action on a resource is not a
conditional replacement of it, and one that accepted `If-Match: *` would be exactly the
lost update the token exists to prevent.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status
from fastapi.responses import HTMLResponse, StreamingResponse

from ...application.commands import (
    ApproveDocumentCommand,
    BuildFromAnalysisCommand,
    CheckDocumentCommand,
    ClaimAddition,
    ClaimPatch,
    DraftCommand,
    RegenerateClaimCommand,
    RegenerateSectionCommand,
    RenderCommand,
    UpdateDocumentCommand,
)
from ...util import new_id
from ..dependencies import Services
from ..etags import DocumentIfMatch, document_etag, parse_document_etag
from ..headers import IdempotencyKey
from ..responses import accepted_operation, content_disposition
from ..schemas.documents import (
    BuildFromAnalysisRequest,
    CreateDraftRequest,
    DecisionExportResponse,
    DocumentActionRequest,
    DocumentCheckResponse,
    DocumentMutationResponse,
    DocumentResponse,
    RegenerateDocumentClaimRequest,
    RegenerateDocumentSectionRequest,
    UpdateDocumentRequest,
)
from ..schemas.operations import OperationResponse

router = APIRouter(prefix="/applications/{application_id}/document", tags=["documents"])

#: A preview is built to be framed and nothing else: the one inline stylesheet every CV
#: template carries is allowed, every other source refused, so it cannot run a script or
#: fetch anything. The client frames it sandboxed without `allow-same-origin`, but the
#: response does not depend on the client remembering to.
_PREVIEW_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; form-action 'none'; base-uri 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
}


def _mutation(response: Response, result) -> DocumentMutationResponse:
    response.headers["ETag"] = document_etag(result.document_hash)
    return DocumentMutationResponse.model_validate(result.model_dump(mode="json"))


def _check(response: Response, result) -> DocumentCheckResponse:
    response.headers["ETag"] = document_etag(result.document_hash)
    return DocumentCheckResponse.model_validate(result.model_dump(mode="json"))


@router.get("", response_model=DocumentResponse, summary="Read the Application's CV document")
def read_document(application_id: str, services: Services, response: Response) -> DocumentResponse:
    """`200` with the document and its `document_hash` as the ETag; `404` before analysis."""
    result = services.queries.document(application_id)
    response.headers["ETag"] = document_etag(result.document_hash)
    return DocumentResponse.model_validate(result.model_dump(mode="json"))


@router.patch(
    "", response_model=DocumentMutationResponse, summary="Save a structured content patch"
)
def update_document(
    application_id: str,
    request: UpdateDocumentRequest,
    if_match: DocumentIfMatch,
    services: Services,
    response: Response,
) -> DocumentMutationResponse:
    """`200` with the new hash; `409` when `If-Match` no longer describes the document.

    Free text no fact authorizes is saved as a pending claim rather than refused (§14);
    it blocks approval, not the save.
    """
    result = services.drafts.update_document(
        UpdateDocumentCommand(
            application_id=application_id,
            expected_document_hash=parse_document_etag(if_match),
            claim_edits=[
                ClaimPatch(**edit.model_dump(mode="python")) for edit in request.claim_edits
            ],
            claim_removals=list(request.claim_removals),
            claim_additions=[
                ClaimAddition(**addition.model_dump(mode="python"))
                for addition in request.claim_additions
            ],
            claim_orders={
                name: list(claim_ids) for name, claim_ids in request.claim_orders.items()
            },
        )
    )
    return _mutation(response, result)


@router.get(
    "/preview",
    summary="Render the document's current content to HTML for an isolated preview",
    response_class=HTMLResponse,
    responses={
        200: {
            "description": "The content through the same composition the render uses.",
            "content": {"text/html": {"schema": {"type": "string"}}},
        }
    },
)
def preview_document(application_id: str, services: Services) -> HTMLResponse:
    """`200` and the document itself; `412` before content exists. Nothing is stored."""
    result = services.rendering.preview_document(application_id)
    return HTMLResponse(
        content=result.html,
        headers={**_PREVIEW_HEADERS, "ETag": document_etag(result.document_hash)},
    )


@router.get(
    "/preview.pdf",
    summary="Render the document's current content to a stamped preview PDF",
    response_class=Response,
    responses={
        200: {
            "description": (
                "The content through the same composition and browser the render uses, "
                "stamped as unapproved on every page. Nothing is stored."
            ),
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
def preview_document_pdf(application_id: str, services: Services) -> Response:
    """`200` and the PDF inline; needs no approval and touches no approval stamp."""
    result = services.rendering.preview_document_pdf(application_id)
    return Response(
        content=result.pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="draft-preview.pdf"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
            "ETag": document_etag(result.document_hash),
        },
    )


@router.post(
    "/build-from-analysis",
    response_model=DocumentMutationResponse,
    summary="Re-pin the document to a newer analysis",
)
def build_from_analysis(
    application_id: str,
    request: BuildFromAnalysisRequest,
    services: Services,
    response: Response,
) -> DocumentMutationResponse:
    """`200` with a document pinned to the named analysis and no content."""
    result = services.repin.build_from_analysis(
        BuildFromAnalysisCommand(
            application_id=application_id,
            **request.model_dump(mode="python"),
            actor_type="user",
            client="web",
        )
    )
    return _mutation(response, result)


@router.post(
    "/draft",
    response_model=OperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate the document's content",
)
def create_draft(
    application_id: str,
    request: CreateDraftRequest,
    services: Services,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> OperationResponse:
    """`202` and a `Location`; activation writes content only while the hash still holds."""
    queued = services.operation_submissions.submit_draft(
        DraftCommand(application_id=application_id, **request.model_dump(mode="python")),
        idempotency_key=idempotency_key or new_id(),
        draft_service=services.drafts,
    )
    return accepted_operation(response, queued)


@router.post(
    "/regenerate-section",
    response_model=OperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Regenerate one section",
)
def regenerate_section(
    application_id: str,
    request: RegenerateDocumentSectionRequest,
    services: Services,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> OperationResponse:
    """`202`. A provider failure never falls back to a deterministic rebuild."""
    queued = services.operation_submissions.submit_regeneration(
        RegenerateSectionCommand(
            application_id=application_id, **request.model_dump(mode="python")
        ),
        idempotency_key=idempotency_key or new_id(),
        draft_service=services.drafts,
    )
    return accepted_operation(response, queued)


@router.post(
    "/regenerate-claim",
    response_model=OperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Regenerate or review one claim",
)
def regenerate_claim(
    application_id: str,
    request: RegenerateDocumentClaimRequest,
    services: Services,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> OperationResponse:
    """`202`. The provider is given the claim's own supporting facts and nothing else."""
    queued = services.operation_submissions.submit_regeneration(
        RegenerateClaimCommand(application_id=application_id, **request.model_dump(mode="python")),
        idempotency_key=idempotency_key or new_id(),
        draft_service=services.drafts,
    )
    return accepted_operation(response, queued)


@router.post(
    "/check", response_model=DocumentCheckResponse, summary="Check the content without approving"
)
def check_document(
    application_id: str, request: DocumentActionRequest, services: Services, response: Response
) -> DocumentCheckResponse:
    """`200` whether or not the check passed; the report is data (§22)."""
    result = services.draft_validation.check_document(
        CheckDocumentCommand(application_id=application_id, **request.model_dump(mode="python"))
    )
    return _check(response, result)


@router.post("/approve", response_model=DocumentCheckResponse, summary="Check and approve")
def approve_document(
    application_id: str, request: DocumentActionRequest, services: Services, response: Response
) -> DocumentCheckResponse:
    """`200` with the report; approved only when it passed. `412` names a blocker."""
    result = services.draft_approval.approve_document(
        ApproveDocumentCommand(
            application_id=application_id,
            **request.model_dump(mode="python"),
            actor_type="user",
            client="web",
        )
    )
    return _check(response, result)


@router.post(
    "/render",
    response_model=OperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Render the approved document",
)
def render_document(
    application_id: str,
    request: DocumentActionRequest,
    services: Services,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> OperationResponse:
    """`202`; admission refuses with `412` unless the document is approved."""
    queued = services.operation_submissions.submit_render(
        RenderCommand(application_id=application_id, **request.model_dump(mode="python")),
        idempotency_key=idempotency_key or new_id(),
        rendering_service=services.rendering,
    )
    return accepted_operation(response, queued)


@router.get(
    "/pdf",
    summary="Download the Ready document's PDF",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "The rendered PDF, when the document is Ready at request time.",
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
def download_pdf(application_id: str, services: Services) -> StreamingResponse:
    """`412` unless the document is Ready when the request is answered (§16).

    The rendered files are mutable working outputs, so the ETag is the document's hash
    and caching is refused: the same URL answers for whatever is Ready now.
    """
    delivery = services.rendering.export_recruiter_pdf(application_id)
    return StreamingResponse(
        delivery.stream.chunks(),
        media_type=delivery.media_type,
        headers={
            "Content-Disposition": content_disposition(delivery.filename),
            "Content-Length": str(delivery.size),
            "ETag": document_etag(delivery.document_hash),
            "Cache-Control": "no-store",
        },
    )


@router.get(
    "/decision-markdown",
    response_model=DecisionExportResponse,
    summary="Export the document's provenance as Markdown",
)
def export_decision_markdown(application_id: str, services: Services) -> DecisionExportResponse:
    result = services.draft_history.export_decision_markdown(application_id)
    return DecisionExportResponse(
        application_id=result.application_id,
        document_id=result.document_id,
        markdown=result.content,
    )
