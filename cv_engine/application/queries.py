"""Purpose-built read projections returned by the application layer."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from ..domain.models import DraftDocument, JobAnalysis
from .commands import BoundaryDTO
from .operations import OperationView


class ApplicationView(BoundaryDTO):
    id: str
    company: str
    target_role: str
    normalized_role: str | None = None
    source_url: str | None = None
    language: str | None = None
    track: str | None = None
    profile: str | None = None
    emphasis: str | None = None
    classification_confidence: float | None = None
    fit_level: str | None = None
    current_status: str
    terminal_outcome: str | None = None
    last_contact_date: str | None = None
    next_action: str | None = None
    next_action_date: str | None = None
    notes: str = ""
    source: str = "manual"
    created_at: str
    updated_at: str


class JobSnapshotView(BoundaryDTO):
    id: str
    application_id: str
    version_number: int
    job_text: str
    source_url: str | None = None
    captured_at: str
    source_metadata: dict[str, Any]
    content_hash: str
    prior_snapshot_id: str | None = None


class JobAnalysisView(BoundaryDTO):
    id: str
    application_id: str
    job_snapshot_id: str
    version_number: int
    analysis: JobAnalysis
    provider: str
    model: str
    created_at: str


class PreparationState(StrEnum):
    NEEDS_ANALYSIS = "needs_analysis"
    NEEDS_REVIEW = "needs_review"
    READY_TO_DRAFT = "ready_to_draft"
    DRAFT_IN_PROGRESS = "draft_in_progress"
    READY_FOR_APPROVAL = "ready_for_approval"
    APPROVED = "approved"
    READY = "ready"


class WorkingDraftState(StrEnum):
    NONE = "none"
    EDITING = "editing"
    VALIDATION_FAILED = "validation_failed"
    VALIDATED = "validated"
    STALE = "stale"


class ReasonView(BoundaryDTO):
    code: str
    message: str
    entity_references: dict[str, str] = {}
    allowed_resolution_actions: list[str] = []


class WarningView(BoundaryDTO):
    code: str
    message: str
    entity_references: dict[str, str] = {}


class BlockedActionView(BoundaryDTO):
    action: str
    reasons: list[str]


class ApplicationStateView(BoundaryDTO):
    recruitment_status: str
    terminal_outcome: str | None = None
    preparation_state: PreparationState
    working_draft_state: WorkingDraftState
    review_reasons: list[ReasonView] = []
    stale_reasons: list[ReasonView] = []
    primary_stale_reason: str | None = None
    warnings: list[WarningView] = []
    active_operation: OperationView | None = None
    active_job_snapshot_id: str
    active_analysis_id: str | None = None
    active_selection_plan_id: str | None = None
    active_working_draft_id: str | None = None
    latest_approved_revision_id: str | None = None
    latest_ready_revision_id: str | None = None
    newer_draft_in_progress: bool = False
    available_actions: list[str] = []
    blocked_actions: list[BlockedActionView] = []
    recommended_action: str | None = None


class ApplicationDetailView(ApplicationStateView):
    application: ApplicationView
    latest_snapshot: JobSnapshotView
    latest_analysis: JobAnalysisView | None = None


class ApplicationListItemView(ApplicationView, ApplicationStateView):
    """The shared state/action projection plus list-display Application fields."""


class ApplicationListView(BoundaryDTO):
    items: list[ApplicationListItemView]


class WorkingDraftView(BoundaryDTO):
    """§20: the WorkingDraft a client edits, plus its optimistic token.

    `edit_version` and `content_hash` are the two halves of the ETag. They are
    carried as query fields rather than as a formatted token because the format
    is HTTP's business: the application layer states what the version is, and
    the transport decides how to spell it in a header.

    `latest_validation_run_id` is what makes an approve reachable from a read.
    Without it a client that has just seen `working_draft_state: validated`
    would have to validate again to obtain the run ID approval requires.
    """

    id: str
    application_id: str
    job_analysis_id: str
    selection_plan_id: str
    parent_revision_id: str | None = None
    source: DraftDocument
    edit_version: int
    content_hash: str
    active: bool
    created_at: str
    updated_at: str
    latest_validation_run_id: str | None = None
    latest_validation_passed: bool | None = None


class ArtifactVersionView(BoundaryDTO):
    id: str
    artifact_id: str
    revision_id: str | None = None
    artifact_type: str
    logical_name: str
    version_number: int
    lifecycle_status: str
    content_hash: str
    created_at: str
    approved_at: str | None = None
    submitted_at: str | None = None
    track: str | None = None
    profile: str | None = None
    emphasis: str | None = None
    facts_version: str | None = None
    job_snapshot_id: str | None = None
    metadata: dict[str, Any]


class ArtifactVersionsView(BoundaryDTO):
    items: list[ArtifactVersionView]


class DecisionRecordView(BoundaryDTO):
    id: str
    application_id: str
    artifact_version_id: str | None = None
    job_snapshot_id: str
    job_analysis_id: str
    structured: dict[str, Any]
    summary: str
    created_at: str


def application_view(record: dict[str, Any]) -> ApplicationView:
    return ApplicationView.model_validate(record)


def application_list_item_view(
    record: dict[str, Any], state: ApplicationStateView
) -> ApplicationListItemView:
    return ApplicationListItemView.model_validate({**record, **state.model_dump(mode="python")})


def snapshot_view(record: dict[str, Any], job_text: str) -> JobSnapshotView:
    return JobSnapshotView.model_validate(
        {
            **{
                key: record.get(key)
                for key in JobSnapshotView.model_fields
                if key not in {"source_metadata", "job_text"}
            },
            "job_text": job_text,
            "source_metadata": json.loads(record.get("source_metadata_json") or "{}"),
        }
    )


def analysis_view(record: dict[str, Any]) -> JobAnalysisView:
    return JobAnalysisView.model_validate(
        {
            **{key: record.get(key) for key in JobAnalysisView.model_fields if key != "analysis"},
            "analysis": record["analysis"],
        }
    )


def artifact_version_view(record: dict[str, Any]) -> ArtifactVersionView:
    return ArtifactVersionView.model_validate(
        {
            **{
                key: record.get(key)
                for key in ArtifactVersionView.model_fields
                if key != "metadata"
            },
            "metadata": json.loads(record.get("metadata_json") or "{}"),
        }
    )


def decision_view(record: dict[str, Any]) -> DecisionRecordView:
    return DecisionRecordView.model_validate(
        {
            **{
                key: record.get(key)
                for key in DecisionRecordView.model_fields
                if key != "structured"
            },
            "structured": json.loads(record.get("structured_json") or "{}"),
        }
    )
