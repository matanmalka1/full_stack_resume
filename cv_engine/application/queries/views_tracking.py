"""Recruitment-pipeline read projections."""

from __future__ import annotations

from typing import Any

from ...domain.contracts.recruitment import ApplicationStatus
from ..commands import BoundaryDTO

# Public application-boundary type for recruitment-status query filters. HTTP
# adapters depend on this query vocabulary rather than reaching through the
# application layer to the domain model that implements it.
RecruitmentStatus = ApplicationStatus


class RecruitmentTimelineItemView(BoundaryDTO):
    """One visible item in the Application's unified recruitment history."""

    id: str
    item_type: str
    occurred_at: str
    actor_type: str | None = None
    client: str | None = None
    from_status: str | None = None
    to_status: str | None = None
    corrects_event_id: str | None = None
    reason: str = ""
    next_action: str | None = None
    next_action_date: str | None = None
    submission_type: str | None = None
    approved_revision_id: str | None = None
    artifact_version_id: str | None = None
    metadata: dict[str, Any] = {}
