"""Analysis, review decisions, and selection plans over HTTP.

`analysis` and `plan` are carried as objects rather than restated field by
field, the same way `JobAnalysisResponse` already carries one. They are domain
documents with their own versioned schema; a second hand-written copy of that
schema in the HTTP layer could only drift from it, and a router that named the
domain types directly would be a router doing domain work.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .health import HttpSchema


class CreateAnalysisRequest(HttpSchema):
    """What `POST /applications/{id}/analyses` accepts.

    `job_snapshot_id` is explicit: an analyze command that picked its own source
    could classify something other than what the user was looking at.
    """

    job_snapshot_id: str
    track_override: str | None = Field(default=None, max_length=100)
    profile_override: str | None = Field(default=None, max_length=100)
    emphasis_override: str | None = Field(default=None, max_length=100)
    language_override: str | None = Field(default=None, max_length=10)
    accept_low_fit: bool = False
    provider: str = Field(default="deterministic", max_length=50)
    model: str = Field(default="rules-v1", max_length=100)


class SelectionOverlayRequest(HttpSchema):
    """The user's explicit fact decisions.

    Two lists, not three: `selected_fact_ids` is what the resulting plan
    reports, so it is a response field rather than a request one. Explicit
    inclusion is a pin.
    """

    pinned_fact_ids: list[str] = []
    excluded_fact_ids: list[str] = []


class CreateSelectionPlanRequest(SelectionOverlayRequest):
    application_id: str
    expected_candidate_context_hash: str | None = None
    expected_profile_version: str | None = None
    expected_selection_policy_version: str | None = None


class ApplyAnalysisDecisionsRequest(SelectionOverlayRequest):
    application_id: str
    track_override: str | None = Field(default=None, max_length=100)
    profile_override: str | None = Field(default=None, max_length=100)
    emphasis_override: str | None = Field(default=None, max_length=100)
    language_override: str | None = Field(default=None, max_length=10)
    accept_low_fit: bool = False


class SelectionPlanResponse(HttpSchema):
    id: str
    application_id: str
    job_analysis_id: str
    version_number: int
    plan: dict[str, Any]
    candidate_context_version: str
    candidate_context_hash: str
    profile_version: str
    selection_policy_version: str
    track_emphasis_dependencies: dict[str, str]
    created_at: str


class CreateSelectionPlanResponse(HttpSchema):
    application_id: str
    job_analysis_id: str
    selection_plan_id: str
    plan: SelectionPlanResponse


class AnalysisDecisionsResponse(HttpSchema):
    """Which analysis is in force after the decision, and whether it is a new one.

    `job_analysis_id` names the analysis the client should work from now: the
    new one when the decision changed meaning, the original when only the fact
    overlay moved. `created_analysis` is what tells the two apart.
    """

    application_id: str
    job_analysis_id: str
    selection_plan_id: str
    created_analysis: bool
    analysis: dict[str, Any]
    plan: SelectionPlanResponse
