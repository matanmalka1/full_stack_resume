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
from ..schemas.maintenance import ReconciliationResponse

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


@router.post(
    "/reconciliations",
    response_model=ReconciliationResponse,
    summary="Reconcile stored evidence and the fact lifecycle",
)
def reconcile(services: Services) -> ReconciliationResponse:
    """Check database references, artifact hashes, and the fact lifecycle."""
    return ReconciliationResponse.of(services.maintenance.reconcile())
