"""The CV document surface (state-and-use-cases.md §14–§16, §21).

Contract first: these routes declare the HTTP shape the frontend builds against, and
answer `501` until Wave 3 of the single-document rewrite wires them to the application
services (docs/backlog/single-document-rewrite.md). Temporary: the `_not_wired` bodies
are removed in Wave 3.
"""

# Parameters declare the contract; the stub bodies do not read them yet.
# ruff: noqa: ARG001

from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, HTTPException, Response, status

from ..dependencies import Services
from ..etags import DocumentIfMatch
from ..headers import IdempotencyKey
from ..schemas.documents import (
    BuildFromAnalysisRequest,
    CreateDraftRequest,
    DecisionExportResponse,
    DocumentActionRequest,
    DocumentCheckResponse,
    DocumentMutationResponse,
    DocumentResponse,
    ProposeSelectionRequest,
    RegenerateDocumentClaimRequest,
    RegenerateDocumentSectionRequest,
    UpdateDocumentRequest,
    UpdateSelectionRequest,
)
from ..schemas.operations import OperationResponse

router = APIRouter(prefix="/applications/{application_id}/document", tags=["documents"])


def _not_wired() -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="the document surface is declared but not wired yet",
    )


@router.get("", response_model=DocumentResponse, summary="Read the Application's CV document")
def read_document(application_id: str, services: Services, response: Response) -> DocumentResponse:
    """`200` with the document and its `document_hash` as the ETag; `404` before analysis."""
    _not_wired()


@router.patch(
    "", response_model=DocumentMutationResponse, summary="Save a structured content patch"
)
def update_document(
    application_id: str,
    request: UpdateDocumentRequest,
    if_match: DocumentIfMatch,
    services: Services,
) -> DocumentMutationResponse:
    """`200` with the new hash; `409` when `If-Match` no longer describes the document."""
    _not_wired()


@router.post(
    "/selection",
    response_model=DocumentMutationResponse,
    summary="Change the document's fact selection deterministically",
)
def update_selection(
    application_id: str, request: UpdateSelectionRequest, services: Services
) -> DocumentMutationResponse:
    """`200`; `412` when the change needs wording judgment and a regeneration instead."""
    _not_wired()


@router.post(
    "/selection-proposals",
    response_model=OperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ask the provider to propose a selection",
)
def propose_selection(
    application_id: str,
    request: ProposeSelectionRequest,
    services: Services,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> OperationResponse:
    _not_wired()


@router.post(
    "/build-from-analysis",
    response_model=DocumentMutationResponse,
    summary="Re-pin the document to a newer analysis",
)
def build_from_analysis(
    application_id: str, request: BuildFromAnalysisRequest, services: Services
) -> DocumentMutationResponse:
    """`200` with a document that has a fresh selection and no content."""
    _not_wired()


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
    _not_wired()


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
    _not_wired()


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
    _not_wired()


@router.post(
    "/check", response_model=DocumentCheckResponse, summary="Check the content without approving"
)
def check_document(
    application_id: str, request: DocumentActionRequest, services: Services
) -> DocumentCheckResponse:
    """`200` whether or not the check passed; the report is data (§22)."""
    _not_wired()


@router.post("/approve", response_model=DocumentCheckResponse, summary="Check and approve")
def approve_document(
    application_id: str, request: DocumentActionRequest, services: Services
) -> DocumentCheckResponse:
    """`200` with the report; approved only when it passed. `412` names a blocker."""
    _not_wired()


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
    _not_wired()


@router.get(
    "/pdf",
    summary="Download the Ready document's PDF",
    response_class=Response,
    responses={
        200: {
            "description": "The rendered PDF, when the document is Ready at request time.",
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
def download_pdf(application_id: str, services: Services) -> Response:
    """`412` unless the document is Ready when the request is answered (§16)."""
    _not_wired()


@router.get(
    "/decision-markdown",
    response_model=DecisionExportResponse,
    summary="Export the document's provenance as Markdown",
)
def export_decision_markdown(application_id: str, services: Services) -> DecisionExportResponse:
    _not_wired()
