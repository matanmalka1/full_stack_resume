"""Immutable audit records."""

from __future__ import annotations

from typing import Any, Literal

from .base import StrictModel


class AuditRecord(StrictModel):
    """One immutable local actor record for an application-layer decision."""

    id: str
    application_id: str
    action: str
    entity_type: str
    entity_id: str
    actor_type: Literal["user", "system"]
    client: Literal["web", "worker"]
    occurred_at: str
    details: dict[str, Any] = {}
