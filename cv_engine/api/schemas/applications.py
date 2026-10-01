from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from ...application.commands.prep import SOURCE_URL_MAX_CHARACTERS
from ...domain.document import ContentCheck, PreparationState
from .health import HttpSchema
from .operations import OperationResponse
from .tracking import CorrectableStatus, RecruitmentTimelineItemResponse, TransitionableStatus


class ApplicationIntake(HttpSchema):
    company: str = Field(min_length=1, max_length=500)
    target_role: str = Field(min_length=1, max_length=500)
    job_text: str = Field(min_length=1)
    source_url: str | None = Field(default=None, max_length=SOURCE_URL_MAX_CHARACTERS)


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
    source_url: str | None = Field(default=None, max_length=SOURCE_URL_MAX_CHARACTERS)
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
    fit_level: str | None = None
    fit_score: float | None = None
    current_status: str
    terminal_outcome: str | None = None
    next_action: str | None = None
    next_action_date: str | None = None
    notes: str
    created_at: str
    updated_at: str
    deleted_at: str | None = None


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

    The lifecycle states are typed as the domain enums rather than
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
    content_check: ContentCheck
    review_reasons: list[ReasonResponse]
    warnings: list[WarningResponse]
    active_operation: OperationResponse | None = None
    latest_operation: OperationResponse | None = None
    active_job_snapshot_id: str
    latest_analysis_id: str | None = None
    document_id: str | None = None
    document_hash: str | None = None
    document_analysis_id: str | None = None
    approved_at: str | None = None
    last_render_error: dict[str, Any] | None = None
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
    source_hash: str


class GapResponse(HttpSchema):
    requirement_id: str
    requirement: str
    severity: Literal["hard", "warning"]
    reason: str
    substitute_fact_ids: list[str] = []


class JobAnalysisResponse(HttpSchema):
    """The stored analysis and its read-time projection.

    Fit and gaps are shown to the user and gate nothing. They are computed from
    `analysis.requirements` when the response is built, so they appear here
    beside the document rather than inside it.
    """

    id: str
    application_id: str
    job_snapshot_id: str
    version_number: int
    analysis: dict[str, Any]
    fit_level: str
    fit_score: float | None = None
    gaps: list[GapResponse] = []
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
    is_closed: bool


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
    preset_counts: dict[str, int] = {}
    recruitment_status_counts: dict[CorrectableStatus, int] = {}


class CloseApplicationResponse(HttpSchema):
    application_id: str
    current_status: str
    terminal_outcome: str | None = None
    next_action: str | None = None
    next_action_date: str | None = None
    event_id: str | None = None


class DeleteApplicationResponse(HttpSchema):
    """`current_status`/`terminal_outcome` are unchanged by deletion; they are
    carried here only because they are part of the same mutation-result shape
    every other tracking command returns.
    """

    application_id: str
    current_status: str
    terminal_outcome: str | None = None
    next_action: str | None = None
    next_action_date: str | None = None
    event_id: str | None = None


class JobSnapshotHistoryItemResponse(HttpSchema):
    id: str
    version_number: int
    captured_at: str
    source_url: str | None
    job_text: str | None


class JobSnapshotHistoryResponse(HttpSchema):
    active_job_snapshot_id: str
    items: list[JobSnapshotHistoryItemResponse]
