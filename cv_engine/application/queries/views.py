"""Boundary DTOs for purpose-built application-layer read projections."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from ...domain.contracts.analysis import JobAnalysis
from ...domain.contracts.drafts import (
    ClaimStyle,
    ClaimType,
    DraftDocument,
)
from ...domain.contracts.recruitment import ApplicationStatus
from ...domain.contracts.selection import (
    OmissionReason,
    SelectionOutcome,
)
from ...domain.contracts.validation import ValidationReport
from ..commands import BoundaryDTO
from ..operations import OperationView

# Public application-boundary type for recruitment-status query filters.  HTTP
# adapters depend on this query vocabulary rather than reaching through the
# application layer to the domain model that implements it.
RecruitmentStatus = ApplicationStatus


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


class DraftClaimView(BoundaryDTO):
    """One editable line, as the editor needs to see it.

    Exactly the fields a claim edit addresses, plus the two that say what the
    claim currently is. `claim_type` and `style` are the domain's own closed
    sets rather than `str`, so a client's status labels stay exhaustive over
    them.
    """

    claim_id: str
    style: ClaimStyle
    text: str
    claim_type: ClaimType
    fact_ids: list[str]
    pending_reason: str | None = None


class DraftSectionView(BoundaryDTO):
    name: str
    claims: list[DraftClaimView]


class DraftOutlineView(BoundaryDTO):
    """The document's editable structure, derived per read.

    Not a second copy of `DraftDocument`: it is computed from the same object on
    each read, it stores nothing, and it deliberately carries only what an edit
    can address. The document itself stays available as `source`, versioned and
    whole, for anything that needs more than this.

    Headline and contacts are here because `draft_claims` includes them and the
    editor has to show them - marked as the structural claims they are, not as
    lines a user may remove.
    """

    headline: DraftClaimView
    contacts: list[DraftClaimView]
    sections: list[DraftSectionView]


class DraftFactView(BoundaryDTO):
    """One fact this draft either uses or considered.

    `text` is nullable because a fact the store can no longer resolve is a state
    the projection already reports as a stale reason; a read that raised instead
    would turn an explainable staleness into a 500.

    `outcome` is null for a fact that is not a SelectionPlan candidate - a
    contact, or a fact a manual relink attached. That null is what says no
    include/exclude decision applies to it, so nothing needs a second flag.
    """

    fact_id: str
    text: str | None = None
    linked_claim_ids: list[str] = []
    section: str | None = None
    outcome: SelectionOutcome | None = None
    reason: OmissionReason | None = None


class WorkingDraftFactsView(BoundaryDTO):
    """§20 candidate accounting: every fact the draft links, and every candidate.

    The union of the two, because neither covers the other. Contacts come from
    the candidate context and never appear in a SelectionPlan, while an omitted
    candidate appears in no claim - and the editor needs both to show what backs
    a line and what could be added to one.
    """

    working_draft_id: str
    application_id: str
    selection_plan_id: str
    language: str
    facts: list[DraftFactView]


class DraftPreviewView(BoundaryDTO):
    """The HTML for one exact draft version.

    The version travels with the document so a caller can tell which edit it is
    looking at, rather than inferring it from when the request was made.
    """

    working_draft_id: str
    edit_version: int
    content_hash: str
    language: str
    html: str


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
    outline: DraftOutlineView
    edit_version: int
    content_hash: str
    active: bool
    created_at: str
    updated_at: str
    latest_validation_run_id: str | None = None
    latest_validation_passed: bool | None = None


class ValidationRunView(BoundaryDTO):
    application_id: str
    working_draft_id: str
    validation_run_id: str
    edit_version: int
    content_hash: str
    passed: bool
    report: ValidationReport
    created_at: str


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


class ArtifactVersionDetailView(ArtifactVersionView):
    """One artifact's registered metadata plus whether it would download (§20).

    `downloadable` is verified rather than assumed. §20 lists "artifact
    metadata/download eligibility" as one query, and a client told a payload is
    available which is then refused at download learned nothing from the first
    call - so this runs the same containment/presence/hash verification the
    download runs. `unavailable_reason` is the refusal's stable code, never its
    message: the message is where a path would be if one ever appeared.
    """

    downloadable: bool
    size: int | None = None
    unavailable_reason: str | None = None


class ApprovedRevisionView(BoundaryDTO):
    """One immutable ApprovedRevision and its Ready qualification (§20).

    The two are one query because they are one question. A revision's
    qualification is re-derived from its own stored evidence every time it is
    asked for - `ready_qualified` is never a stored flag - so returning the
    revision without it would hand a client a record it then has to interpret.

    Nothing here says whether the revision is the *active* Ready one. That is
    the Application's `preparation_state`, which is a fact about the active
    JobSnapshot and JobAnalysis rather than about this record.

    `ApprovedRevision` carries `resume_json_reference` and
    `resume_markdown_reference`, which are stored paths. They are absent here
    deliberately and `approved_revision_view` names its fields one by one
    rather than validating the record from attributes - which is how the same
    field set stayed a superset three times in M3 already. A client reaches
    those two payloads the way it reaches every other one: by artifact-version
    ID.
    """

    id: str
    application_id: str
    version_number: int
    working_draft_id: str
    job_snapshot_id: str
    job_analysis_id: str
    selection_plan_id: str
    validation_run_id: str
    draft_edit_version: int
    draft_content_hash: str
    facts_version: str
    approved_at: str
    decision_provenance: dict[str, Any]
    ready_qualified: bool
    pdf_artifact_version_id: str | None = None
    html_artifact_version_id: str | None = None
    ready_validation: ValidationReport


class DecisionRecordView(BoundaryDTO):
    id: str
    application_id: str
    artifact_version_id: str | None = None
    job_snapshot_id: str
    job_analysis_id: str
    structured: dict[str, Any]
    summary: str
    created_at: str
