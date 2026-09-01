from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from ...application.queries import PreparationState, WorkingDraftState
from .health import HttpSchema
from .operations import OperationResponse
from .tracking import RecruitmentTimelineItemResponse, TransitionableStatus


class ApplicationIntake(HttpSchema):
    company: str = Field(min_length=1, max_length=500)
    target_role: str = Field(min_length=1, max_length=500)
    job_text: str = Field(min_length=1)
    source_url: str | None = Field(default=None, max_length=2048)


class DuplicateCheckRequest(ApplicationIntake):
    pass


class CreateApplicationRequest(ApplicationIntake):
    acknowledged_duplicates: bool = False


class DuplicateMatchResponse(HttpSchema):
    application_id: str
    company: str
    target_role: str
    matched_on: list[Literal["source_url", "normalized_text", "company_title"]]


class DuplicateCheckResponse(HttpSchema):
    matches: list[DuplicateMatchResponse]


class CreateApplicationResponse(HttpSchema):
    application_id: str
    job_snapshot_id: str
    warnings: list[str]
    duplicate_matches: list[DuplicateMatchResponse]


class CreateJobSnapshotRequest(HttpSchema):
    job_text: str = Field(min_length=1)
    source_url: str | None = Field(default=None, max_length=2048)
    source_metadata: dict[str, Any] = {}


class CreateJobSnapshotResponse(HttpSchema):
    application_id: str
    job_snapshot_id: str


class UpdateApplicationNotesRequest(HttpSchema):
    notes: str
    expected_notes: str


class UpdateApplicationNotesResponse(HttpSchema):
    application_id: str
    notes: str
    updated_at: str


class ApplicationResponse(HttpSchema):
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
    notes: str
    source: str
    created_at: str
    updated_at: str


class ReasonResponse(HttpSchema):
    code: str
    message: str
    entity_references: dict[str, str]
    allowed_resolution_actions: list[str]


class WarningResponse(HttpSchema):
    code: str
    message: str
    entity_references: dict[str, str]


class BlockedActionResponse(HttpSchema):
    action: str
    reasons: list[str]


class ApplicationStateResponse(HttpSchema):
    """The §9 action policy projection, and nothing wider.

    The two lifecycle states are typed as the application enums rather than
    flattened to `str`, the same way `OperationResponse` spells its closed sets.
    `preparation_state` drives the workflow landmark and the Hebrew label a user
    reads; flattened to `string` the generated TypeScript cannot key a label map
    by it, so a state added to the projection would reach a screen untranslated
    instead of failing the frontend build.

    The action fields stay `str` deliberately. They are not a closed set at this
    boundary the way the states are - `available_actions` mixes preparation
    commands with review-reason resolution actions - and a client that meets an
    action it has no screen for reports exactly that, which is a correct
    presentation rather than a failure.
    """

    recruitment_status: str
    terminal_outcome: str | None = None
    preparation_state: PreparationState
    working_draft_state: WorkingDraftState
    review_reasons: list[ReasonResponse]
    stale_reasons: list[ReasonResponse]
    primary_stale_reason: str | None = None
    warnings: list[WarningResponse]
    active_operation: OperationResponse | None = None
    latest_operation: OperationResponse | None = None
    active_job_snapshot_id: str
    active_analysis_id: str | None = None
    active_selection_plan_id: str | None = None
    active_working_draft_id: str | None = None
    latest_approved_revision_id: str | None = None
    latest_ready_revision_id: str | None = None
    newer_draft_in_progress: bool
    available_actions: list[str]
    blocked_actions: list[BlockedActionResponse]
    recommended_action: str | None = None


class JobSnapshotResponse(HttpSchema):
    id: str
    application_id: str
    version_number: int
    job_text: str
    source_url: str | None = None
    captured_at: str
    source_metadata: dict[str, Any]
    content_hash: str
    prior_snapshot_id: str | None = None


class JobAnalysisResponse(HttpSchema):
    id: str
    application_id: str
    job_snapshot_id: str
    version_number: int
    analysis: dict[str, Any]
    provider: str
    model: str
    created_at: str


class ApplicationDetailResponse(ApplicationStateResponse):
    application: ApplicationResponse
    latest_snapshot: JobSnapshotResponse
    latest_analysis: JobAnalysisResponse | None = None
    allowed_recruitment_transitions: list[TransitionableStatus]
    recruitment_timeline: list[RecruitmentTimelineItemResponse]


class ApplicationListItemResponse(ApplicationResponse, ApplicationStateResponse):
    pass


class ApplicationListResponse(HttpSchema):
    """One page of the list, and the counts that place it.

    `matched` is how many rows the query selected, `total` how many exist before
    it narrowed anything. Neither is `len(items)`, which is only what this page
    holds: a client showing "10 of 43 matched, 61 in all" cannot derive either
    count from the page, and reading the list again to count it would compute the
    whole projection a second time. `limit` and `offset` are echoed so a client
    can tell which page it is holding without keeping its own request.
    """

    items: list[ApplicationListItemResponse]
    matched: int
    total: int
    limit: int | None = None
    offset: int = 0
    """How many Applications stand at each preparation state, across all of them.

    A client offering a stage filter cannot learn this from a narrowed page - the
    stage it filtered by is the only one that page holds - and a state with no
    Applications is absent rather than zero.
    """

    stage_counts: dict[PreparationState, int] = {}


class ArtifactVersionResponse(HttpSchema):
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


class ArtifactVersionsResponse(HttpSchema):
    items: list[ArtifactVersionResponse]


class DecisionRecordResponse(HttpSchema):
    id: str
    application_id: str
    artifact_version_id: str | None = None
    job_snapshot_id: str
    job_analysis_id: str
    structured: dict[str, Any]
    summary: str
    created_at: str


class CloseApplicationResponse(HttpSchema):
    application_id: str
    current_status: str
    terminal_outcome: str | None = None
    next_action: str | None = None
    next_action_date: str | None = None
    event_id: str | None = None
