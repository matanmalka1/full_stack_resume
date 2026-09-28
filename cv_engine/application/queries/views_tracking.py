"""Recruitment-pipeline read projections."""

from __future__ import annotations

from typing import Any

from ...domain.contracts.drafts import DraftDocument
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
    document_hash: str | None = None
    metadata: dict[str, Any] = {}


class SubmissionView(BoundaryDTO):
    """One immutable Submission: what was sent, and the checksum of each file (§20).

    File metadata is the SHA-256 of each copy; the stored paths never leave the
    application.
    """

    id: str
    application_id: str
    submission_type: str
    submitted_at: str
    job_snapshot_id: str | None = None
    document_hash: str | None = None
    content: DraftDocument | None = None
    html_sha256: str | None = None
    pdf_sha256: str | None = None
    metadata: dict[str, Any] = {}


class SubmissionsView(BoundaryDTO):
    items: list[SubmissionView]
