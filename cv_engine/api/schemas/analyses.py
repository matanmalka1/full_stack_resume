"""Analysis, review decisions, and selection plans over HTTP.

`analysis` and `plan` are carried as objects rather than restated field by
field, the same way `JobAnalysisResponse` already carries one. They are domain
documents with their own versioned schema; a second hand-written copy of that
schema in the HTTP layer could only drift from it, and a router that named the
domain types directly would be a router doing domain work.

The classification *overrides* are the opposite case and are typed. A closed
vocabulary of four string sets is not a versioned document being restated: it
is the constraint the request is already subject to, enforced today only after
the value has left this layer. Flattened to `str` it cost twice - the generated
TypeScript was `string`, so a client had to keep its own copy of the sets, and
a value outside them reached `ProfileName(...)` as a bare `ValueError` and
surfaced to the user as a 500. Naming the enums here refuses it as a 422 before
a command is built. The architecture rule allows `domain` inside `api` and
forbids it inside `routers/`, which is where a domain type would mean a router
doing domain work; these are schemas.
"""

from __future__ import annotations

from typing import Any, Literal

from ...domain.contracts.analysis import Language
from ...domain.contracts.selection import OmissionReason, SelectionOutcome
from ...domain.contracts.taxonomy import (
    Emphasis,
    ProfileName,
    Track,
)
from .applications import ApplicationStateResponse
from .health import HttpSchema


class ClassificationOverrides(HttpSchema):
    """The four explicit matching decisions accepted by analysis forms.

    Shared because both requests that accept them accept exactly the same four,
    and a second declaration is a second place to forget one.

    Every field is optional and withholding one is not a retraction. Track,
    Profile and language are analysis-level decisions; Emphasis is committed
    on SelectionPlan when it is the only change.
    """

    track_override: Track | None = None
    profile_override: ProfileName | None = None
    emphasis_override: Emphasis | None = None
    language_override: Language | None = None


class CreateAnalysisRequest(ClassificationOverrides):
    """What `POST /applications/{id}/analyses` accepts.

    `job_snapshot_id` is explicit: an analyze command that picked its own source
    could classify something other than what the user was looking at.
    """

    job_snapshot_id: str
    provider: Literal["openai"] = "openai"


class SelectionOverlayRequest(HttpSchema):
    """The user's explicit fact decisions.

    Two lists, not three: `selected_fact_ids` is what the resulting plan
    reports, so it is a response field rather than a request one. Explicit
    inclusion is a pin.
    """

    pinned_fact_ids: list[str] = []
    excluded_fact_ids: list[str] = []
    #: The plan the client had in front of it when the user decided. A decision
    #: made against a plan that has since moved is refused rather than applied
    #: to one the user never saw.
    expected_selection_plan_id: str | None = None


class CreateSelectionPlanRequest(SelectionOverlayRequest):
    """What `POST /analyses/{id}/selection-plans` accepts, in both modes.

    `mode` is what makes the route answer `201` or `202`. It is explicit and has
    no `auto` value (§12): the deterministic form commits a plan inside the
    request, the AI form queues an Operation, and a client is never left
    guessing which of the two it got.

    The overlay lists are the user's own decisions and belong to the
    deterministic form. In AI mode the provider proposes the overlay, so
    sending both would be two answers to the same question - which is why the
    router refuses that combination rather than silently preferring one.
    """

    application_id: str
    mode: Literal["deterministic", "ai"] = "deterministic"
    #: An explicit Emphasis decision. Deterministic-mode only (§13): AI mode
    #: proposes the plan under the analysis's own Emphasis, so this is
    #: refused there the same way the fact overlay is.
    emphasis_override: Emphasis | None = None
    expected_candidate_context_hash: str | None = None
    expected_facts_version: str | None = None
    expected_profile_version: str | None = None
    expected_selection_policy_version: str | None = None


class ApplyAnalysisDecisionsRequest(SelectionOverlayRequest, ClassificationOverrides):
    """One review-form submission (§13).

    Carries analysis and selection-policy decisions because one form may submit
    both. Which immutable records are created is decided by what changed.
    """

    application_id: str
    #: The active analysis shown by the form. Required separately from the path
    #: identity so the write can compare the observation as well as resolve the
    #: immutable source being addressed.
    expected_analysis_id: str


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


class SelectionPlanCandidateResponse(HttpSchema):
    fact_id: str
    text: str | None = None
    section: str
    outcome: SelectionOutcome
    reason: OmissionReason | None = None
    user_selectable: bool


class SelectionPlanDetailResponse(SelectionPlanResponse):
    language: str
    facts_version: str
    pinned_fact_ids: list[str]
    excluded_fact_ids: list[str]
    candidates: list[SelectionPlanCandidateResponse]


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
    #: Fresh authoritative projection after the immutable replacements were
    #: activated. Clients choose the next step from this rather than predicting
    #: whether the new context is reviewable, draftable, stale, or historical.
    state: ApplicationStateResponse
