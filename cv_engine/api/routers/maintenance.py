"""Whole-instance reconciliation.

Reconciliation reports; it never repairs. A mismatch between stored evidence
and the database is something to be told about, not something a route may
silently fix, because the records it checks are the immutable ones.

`200` carries the report whether or not it passed: a failed reconciliation is a
successful answer to the question asked, and `passed` is the field to read.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..dependencies import Services
from ..schemas.maintenance import (
    OrphanInventoryResponse,
    ReclaimResultResponse,
    ReconciliationResponse,
)

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


@router.post(
    "/reconciliations",
    response_model=ReconciliationResponse,
    summary="Reconcile stored evidence and the fact lifecycle",
)
def reconcile(services: Services) -> ReconciliationResponse:
    """Check database references, artifact hashes, and the fact lifecycle."""
    return ReconciliationResponse.of(services.maintenance.reconcile())


@router.get(
    "/orphans",
    response_model=OrphanInventoryResponse,
    summary="Inspect unreferenced immutable payload candidates",
)
def inspect_orphans(services: Services) -> OrphanInventoryResponse:
    """Read-only observation; a candidate holds no database reference and no live lease.

    This endpoint neither repairs nor deletes payloads.
    """
    return OrphanInventoryResponse.of(services.maintenance.inspect_orphans())


@router.post(
    "/orphans/reclaim",
    response_model=ReclaimResultResponse,
    summary="Remove orphan payloads whose write lease is fenced and unreferenced",
)
def reclaim_orphans(services: Services) -> ReclaimResultResponse:
    """Remove exactly the candidates this call can prove are safe (architecture.md §7.1).

    Never removes a payload a database record references, and never lets a
    reclaimed attempt's registration succeed afterward. Not exhaustive: an
    object-store write behind an already-fenced lease can still land after
    this call finishes, so `reclaim_orphans` is meant to be called on a
    schedule, not once. Idempotent and safe to call concurrently with itself.
    """
    return ReclaimResultResponse.of(services.maintenance.reclaim_orphans())
