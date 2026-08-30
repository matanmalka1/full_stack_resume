"""The contextual fact lifecycle: inspect, capture, confirm, promote, attach.

The Web flow this serves is contextual rather than a general Knowledge
Manager (product-spec.md 561-567): facts are reached from the claim that needs
them, created as `pending`, promoted only on explicit confirmation, and
attached to a Profile section before a plan can select them.

Two capabilities deliberately have no route. Creating a fact with a
caller-chosen ID stays out because identity is generated, and canonical
corrections - a new fact carrying `replaces` - remain a CLI concern in v2.0.
Both are refusals the specification makes, not gaps.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from ..dependencies import Services
from ..schemas.facts import (
    AttachFactRequest,
    CaptureClaimFactRequest,
    ConfirmAndUseFactRequest,
    ConfirmAndUseFactResponse,
    FactAttachmentResponse,
    FactContentRequest,
    FactDetailResponse,
    FactHistoryResponse,
    FactListItemResponse,
    FactListResponse,
    FactMutationResponse,
    FactResponse,
    FactStatusFilter,
    FactTransitionRequest,
    fact_event_response,
)

router = APIRouter(prefix="/facts", tags=["facts"])


@router.get("", response_model=FactListResponse, summary="List facts and their lifecycle status")
def list_facts(
    services: Services,
    fact_status: Annotated[FactStatusFilter | None, Query(alias="status")] = None,
) -> FactListResponse:
    result = services.knowledge.list_facts(fact_status.value if fact_status else None)
    return FactListResponse(
        items=[
            FactListItemResponse(
                fact=FactResponse.of(item.fact),
                recorded_status=item.recorded_status,
            )
            for item in result.items
        ]
    )


@router.get(
    "/history",
    response_model=FactHistoryResponse,
    summary="Read the immutable fact lifecycle trail",
)
def read_fact_history(services: Services) -> FactHistoryResponse:
    """Declared before `/{fact_id}`, so `history` is not read as a fact ID."""
    result = services.knowledge.fact_history(None)
    return FactHistoryResponse(events=[fact_event_response(event) for event in result.events])


@router.get(
    "/{fact_id}",
    response_model=FactDetailResponse,
    summary="Read one fact and its lifecycle events",
)
def read_fact(fact_id: str, services: Services) -> FactDetailResponse:
    result = services.knowledge.show_fact(fact_id)
    return FactDetailResponse(
        fact=FactResponse.of(result.fact),
        events=[fact_event_response(event) for event in result.events],
    )


@router.get(
    "/{fact_id}/history",
    response_model=FactHistoryResponse,
    summary="Read one fact's lifecycle trail",
)
def read_one_fact_history(fact_id: str, services: Services) -> FactHistoryResponse:
    result = services.knowledge.fact_history(fact_id)
    return FactHistoryResponse(events=[fact_event_response(event) for event in result.events])


@router.post(
    "",
    response_model=FactMutationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a pending fact",
)
def create_fact(request: FactContentRequest, services: Services) -> FactMutationResponse:
    """`201`: a new fact always enters at `pending`, whoever asked for it.

    The application layer generates the identity and refuses a supplied one, so
    the payload carries content only.
    """
    payload = request.model_dump(mode="json", exclude={"source", "reason"})
    result = services.knowledge.create_pending_fact(
        request.source,
        payload,
        reason=request.reason,
    )
    return FactMutationResponse(
        fact=FactResponse.of(result.fact),
        event_id=result.event_id,
        facts_version=result.facts_version,
        lifecycle_version=result.lifecycle_version,
    )


@router.post(
    "/from-claim",
    response_model=FactMutationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a pending fact from an unsupported manual claim",
)
def create_fact_from_claim(
    request: CaptureClaimFactRequest,
    services: Services,
) -> FactMutationResponse:
    """The claim's exact text becomes the fact's rendering, unrewritten."""
    result = services.knowledge.create_fact_from_claim(
        request.application_id,
        request.claim_id,
        source=request.source,
        meaning=request.meaning,
        tags=request.tags,
        english=request.english,
        hebrew=request.hebrew,
        provenance=request.provenance,
        effective_dates=request.effective_dates,
        replaces=request.replaces,
        reason=request.reason,
    )
    return FactMutationResponse(
        fact=FactResponse.of(result.fact),
        event_id=result.event_id,
        facts_version=result.facts_version,
        lifecycle_version=result.lifecycle_version,
    )


@router.post(
    "/{fact_id}/confirm",
    response_model=FactMutationResponse,
    summary="Promote a pending fact to confirmed",
)
def confirm_fact(
    fact_id: str,
    request: FactTransitionRequest,
    services: Services,
) -> FactMutationResponse:
    """`confirm: false` is refused, not interpreted: see `FactTransitionRequest`."""
    result = services.knowledge.transition_fact(
        fact_id,
        "confirm",
        explicitly_confirmed=request.confirm,
        reason=request.reason,
    )
    return FactMutationResponse(
        fact=FactResponse.of(result.fact),
        event_id=result.event_id,
        facts_version=result.facts_version,
        lifecycle_version=result.lifecycle_version,
    )


@router.post(
    "/{fact_id}/promote",
    response_model=FactMutationResponse,
    summary="Promote a confirmed fact to canonical",
)
def promote_fact(
    fact_id: str,
    request: FactTransitionRequest,
    services: Services,
) -> FactMutationResponse:
    result = services.knowledge.transition_fact(
        fact_id,
        "promote",
        explicitly_confirmed=request.confirm,
        reason=request.reason,
    )
    return FactMutationResponse(
        fact=FactResponse.of(result.fact),
        event_id=result.event_id,
        facts_version=result.facts_version,
        lifecycle_version=result.lifecycle_version,
    )


@router.post(
    "/{fact_id}/attachments",
    response_model=FactAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Offer a canonical fact to a Profile section",
)
def attach_fact(
    fact_id: str,
    request: AttachFactRequest,
    services: Services,
) -> FactAttachmentResponse:
    """Attachment offers the fact to a pool; it does not select it."""
    result = services.knowledge.attach_fact(
        fact_id,
        request.profile,
        request.section,
        pin=request.pin,
    )
    return FactAttachmentResponse(
        fact=FactResponse.of(result.fact),
        event_id=result.event_id,
        facts_version=result.facts_version,
        lifecycle_version=result.lifecycle_version,
        profile=result.profile,
        section=result.section,
        pinned=result.pinned,
        profile_store_version=result.profile_store_version,
    )


@router.post(
    "/{fact_id}/confirm-and-use",
    response_model=ConfirmAndUseFactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Promote, attach, and select one fact as one command",
)
def confirm_and_use_fact(
    fact_id: str,
    request: ConfirmAndUseFactRequest,
    services: Services,
) -> ConfirmAndUseFactResponse:
    """One logical command: it promotes, attaches, and creates the replacement
    plan, or it reports a complete failure. There is no partial outcome to
    report, so there is no partial success status.
    """
    result = services.knowledge.confirm_and_use_fact(
        fact_id,
        application_id=request.application_id,
        job_analysis_id=request.job_analysis_id,
        profile=request.profile,
        section=request.section,
        reason=request.reason,
    )
    return ConfirmAndUseFactResponse(
        fact=FactResponse.of(result.fact),
        event_ids=result.event_ids,
        selection_plan=result.selection_plan,
        facts_version=result.facts_version,
        lifecycle_version=result.lifecycle_version,
        profile_store_version=result.profile_store_version,
    )
