"""Root-entity and combined prep+tracking read projections.

`ApplicationStateView`/`ApplicationDetailView` stay combined on purpose (spec
§9): every read of an Application's status needs prep and tracking fields
together, so splitting them would only force every caller to re-join what one
query already computed. This module necessarily depends on both
`views_prep` and `views_tracking` because it is where their projections meet.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from ...domain.contracts.recruitment import ApplicationStatus
from ..commands import BoundaryDTO
from ..operations import OperationView
from .views_prep import JobAnalysisView, JobSnapshotView, PreparationState, WorkingDraftState
from .views_tracking import RecruitmentTimelineItemView


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
    latest_operation: OperationView | None = None
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
    allowed_recruitment_transitions: list[ApplicationStatus] = []
    recruitment_timeline: list[RecruitmentTimelineItemView] = []


class ApplicationListItemView(ApplicationView, ApplicationStateView):
    """The shared state/action projection plus list-display Application fields."""

    is_closed: bool


class ApplicationListView(BoundaryDTO):
    """One page of the list, and the two counts that place it.

    `matched` is how many rows the query selected and `total` how many exist
    before it narrowed anything, so a client can say both "3 of 12 shown" and
    "12 applications" without asking for the list again to count it. Neither is
    `len(items)`, which is only what this page holds.
    """

    items: list[ApplicationListItemView]
    matched: int = 0
    total: int = 0
    limit: int | None = None
    offset: int = 0

    """How many Applications stand at each preparation state, before this query
    narrowed anything.

    A client offering a stage filter has to know which stages exist, and it cannot
    derive that from one narrowed page: the stage it is filtering by is the only
    one that page contains. Counted here from the projection that was computed
    anyway, so no second read answers it. States with no Applications are absent
    rather than present as zero - the map says what is there.
    """

    stage_counts: dict[PreparationState, int] = {}

    """Dashboard facets computed from the same projected rows as this page.

    Each facet ignores its own selected value while respecting the other query
    fields, so selecting an option does not erase the alternatives beside it.
    `preset_counts["all"]` is the count before the preset predicate.
    """

    preset_counts: dict[str, int] = {}
    recruitment_status_counts: dict[ApplicationStatus, int] = {}


class ActivityFilter(StrEnum):
    """Which side of the recruitment axis the caller is asking about.

    OPEN is the default the list screen uses: a finished process stays stored and
    reachable, but it is not what a board of live work is asking about.
    """

    OPEN = "open"
    CLOSED = "closed"
    ALL = "all"


class ApplicationSort(StrEnum):
    UPDATED = "updated"
    CREATED = "created"
    COMPANY = "company"
    STAGE = "stage"


class ApplicationPreset(StrEnum):
    """The board's named questions, as filters the application layer answers.

    Each one is a predicate over the §9 projection, which is why it lives here
    rather than in a client: `preparation_state` and the reason lists are computed
    by that projection and are not stored columns, so a client deriving these would
    be forming a second opinion about where an Application stands.

    They are shorthands, not a second vocabulary. Every preset is expressible in
    the fields this layer already projects, and each narrows the same list the
    other filters narrow rather than replacing it.
    """

    NEEDS_ATTENTION = "needs_attention"
    """Waiting on the user: a review decision to make, a source no longer current,
    or a warning raised against the Application."""

    READY_TO_SEND = "ready_to_send"
    """A rendered CV exists and can be collected and submitted."""

    ACTIVE_INTERVIEWS = "active_interviews"
    """Live conversations with the employer, from first recruiter contact through
    to an offer. Closed Applications are excluded by the statuses themselves."""


class ApplicationListQuery(BoundaryDTO):
    """How a caller narrows and orders the Application list.

    It is a query the application layer answers rather than a view the client
    assembles, because `preparation_state` - the axis this list is mostly read
    by - is computed by the §9 projection and is not a stored column. A client
    that filtered on it would be re-deriving state the projection already owns,
    and a repository that filtered on it would have to compute the projection
    inside SQL. The one layer that holds both the records and the projection is
    this one, so the narrowing lives here.

    Every field has a default, so `list_applications()` with no query is the
    whole list, most recently updated first.
    """

    activity: ActivityFilter = ActivityFilter.ALL
    """An empty set means every stage, not no stage."""

    stages: frozenset[PreparationState] = frozenset()

    """Which recruitment stages the caller is asking about, on the axis beside
    `stages`. The two are independent - where the CV has got to and where the
    Application stands with the employer - so they narrow independently and an
    empty set here means every recruitment stage.

    `ApplicationStatus` rather than `str`: the status is a closed set the domain
    owns, so a value outside it is refused at the boundary rather than becoming a
    filter that silently matches nothing."""

    recruitment_statuses: frozenset[ApplicationStatus] = frozenset()

    """One named question the board asks often, answered here rather than assembled
    by a client. Each preset is a predicate over fields this layer already projects;
    `None` is no preset and every other narrowing still applies on top of it."""

    preset: ApplicationPreset | None = None

    search: str = ""
    sort: ApplicationSort = ApplicationSort.UPDATED

    """A page is a window on an ordering, so it means nothing until `sort` has fixed
    one; `None` is the whole matched list. The ceiling is here rather than at the
    HTTP boundary because it is a property of what this query will answer, not of
    one way of asking it."""

    limit: int | None = Field(default=None, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
