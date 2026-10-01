"""Storage-neutral contracts and lifecycle rules for persisted Operations.

Operations coordinate application services; they are not domain aggregates.  This
module therefore owns the values shared by the persistence adapter, runner, and query
projection without importing any of those hosts.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..domain.claim_review import ReviewProblemCode
from ..util import canonical_json, sha256_text
from .ai_configuration import ReasoningEffort


class OperationContractError(ValueError):
    """An Operation request or lifecycle transition violates the shared contract."""


class OperationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class OperationAction(StrEnum):
    CANCEL = "cancel"
    RETRY = "retry"


TERMINAL_OPERATION_STATUSES = frozenset(
    {
        OperationStatus.SUCCEEDED,
        OperationStatus.FAILED,
        OperationStatus.CANCELLED,
        OperationStatus.INTERRUPTED,
    }
)


def available_operation_actions(
    status: OperationStatus,
    cancellation_requested_at: str | None,
    failure_code: OperationFailureCode | None = None,
) -> tuple[OperationAction, ...]:
    """Derive the commands the Operation API currently accepts.

    The client must not reproduce lifecycle policy from status strings. A queued
    or running Operation can be cancelled until cancellation has been requested.
    Terminal Operations can normally be retried as new immutable Operations;
    a permanent error in their frozen sources is excluded explicitly.
    """
    if status in {OperationStatus.QUEUED, OperationStatus.RUNNING}:
        return (OperationAction.CANCEL,) if cancellation_requested_at is None else ()
    if status is OperationStatus.FAILED and failure_code in {
        OperationFailureCode.MISSING_FACT_RENDERING,
        OperationFailureCode.SOURCE_CHANGED,
    }:
        return ()
    if status in TERMINAL_OPERATION_STATUSES:
        return (OperationAction.RETRY,)
    raise OperationContractError(f"operation action policy does not cover status {status}")


class OperationType(StrEnum):
    ANALYZE_JOB = "analyze_job"
    CREATE_DRAFT = "create_draft"
    REGENERATE_SECTION = "regenerate_section"
    REGENERATE_CLAIM = "regenerate_claim"
    RENDER_DOCUMENT = "render_document"


#: Operations whose successful activation replaces the analysis a
#: matching-configuration decision is taken against.  Kept beside the closed
#: OperationType vocabulary so both the action projection and the persistence
#: CAS use one definition of "competing with this context".
MATCHING_CONTEXT_OPERATION_TYPES = frozenset(
    {
        OperationType.ANALYZE_JOB,
    }
)


class OperationPhase(StrEnum):
    QUEUED = "queued"
    WAITING_FOR_APPLICATION = "waiting_for_application"
    WAITING_FOR_RENDER_SLOT = "waiting_for_render_slot"
    EXECUTING = "executing"
    COMPLETED = "completed"


#: What a row stores. The two waiting phases are never written: a queued Operation is
#: read as waiting while what it waits for is running, so the phase cannot go stale.
STORED_OPERATION_PHASES = (
    OperationPhase.QUEUED,
    OperationPhase.EXECUTING,
    OperationPhase.COMPLETED,
)


class OperationFailureCode(StrEnum):
    SOURCE_CHANGED = "SOURCE_CHANGED"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    #: The account has no credit or hit a spend or usage limit: fixed in billing, not
    #: by waiting. Never retried automatically; a manual retry stays available.
    PROVIDER_QUOTA_EXHAUSTED = "PROVIDER_QUOTA_EXHAUSTED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_REFUSED = "PROVIDER_REFUSED"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    CLAIM_REVIEW_UNCERTAIN = "CLAIM_REVIEW_UNCERTAIN"
    CLAIM_REVIEW_UNSUPPORTED = "CLAIM_REVIEW_UNSUPPORTED"
    SCHEMA_VIOLATION = "SCHEMA_VIOLATION"
    RENDER_FAILED = "RENDER_FAILED"
    BROWSER_START_FAILED = "BROWSER_START_FAILED"
    MISSING_FACT_RENDERING = "MISSING_FACT_RENDERING"
    VALIDATION_EXECUTION_FAILED = "VALIDATION_EXECUTION_FAILED"
    CANCELLED_BEFORE_ACTIVATION = "CANCELLED_BEFORE_ACTIVATION"
    #: No AI provider was configured for a run that needs one. Distinct from
    #: PROVIDER_REFUSED, which means a provider answered and refused: the fix for
    #: this one is configuration, and nothing was ever sent.
    PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"


class OperationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OperationSources(OperationModel):
    """Exact optimistic inputs frozen when an Operation is created.

    An Operation that mutates the document carries `expected_document_hash`; at
    activation it locks the document row and a mismatch discards the result
    (state-and-use-cases.md §11). Analysis is bound to its input JobSnapshot instead.
    """

    job_snapshot_id: str | None = None
    job_snapshot_hash: str | None = None
    job_analysis_id: str | None = None
    expected_document_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    knowledge_context_hash: str | None = None


_SECRET_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "access_token",
        "refresh_token",
        "password",
        "secret",
    }
)


def _secret_key_path(value: Any, path: str = "payload") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().casefold().replace("-", "_")
            child_path = f"{path}.{key}"
            if normalized in _SECRET_KEYS:
                return child_path
            found = _secret_key_path(child, child_path)
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found = _secret_key_path(child, f"{path}[{index}]")
            if found is not None:
                return found
    return None


class CreateOperation(OperationModel):
    application_id: str
    operation_type: OperationType
    payload: dict[str, Any]
    idempotency_key: str = Field(min_length=1)
    sources: OperationSources
    provider: str | None = None
    model: str | None = None
    reasoning_effort: ReasoningEffort | None = None
    retry_of_operation_id: str | None = None

    @model_validator(mode="after")
    def payload_is_secret_free(self) -> CreateOperation:
        secret_path = _secret_key_path(self.payload)
        if secret_path is not None:
            raise ValueError(f"Operation payload contains a secret field: {secret_path}")
        return self

    @property
    def payload_hash(self) -> str:
        return sha256_text(canonical_json(self.payload))


#: What an Operation can own as an output. Closed: analysis activates a JobAnalysis,
#: and document-mutating operations name the CVDocument they changed. Provider calls
#: are not outputs: they are in the AI call log, keyed by the Operation.
OperationOutputType = Literal["job_analysis", "cv_document"]


class OperationOutputReference(OperationModel):
    output_type: OperationOutputType
    output_id: str
    active: bool


class PdfPageLimitReason(OperationModel):
    """The rendered PDF ran past the profile's page limit."""

    code: Literal["pdf_page_limit"] = "pdf_page_limit"
    pages: int = Field(ge=1)
    maximum: int = Field(ge=1)


class MissingFactRenderingReason(OperationModel):
    """A selected canonical fact has no wording in the document language."""

    code: Literal["missing_fact_rendering"] = "missing_fact_rendering"
    fact_id: str
    language: str


RenderCheckCode = Literal[
    "pdf_text_coverage",
    "pdf_link_targets",
    "content_overflow",
    "document_direction",
    "direction_isolation",
    "pdf_filename",
    "html_missing",
    "pdf_missing",
    "pdf_corrupt",
    "render_validation",
]


class RenderCheckReason(OperationModel):
    """A render validation check that failed and carries no parameters."""

    code: RenderCheckCode


class ClaimReviewSource(OperationModel):
    """The canonical source as it was read for this failed review, not a live fact."""

    fact_id: str
    meaning: str
    rendering: str


class RejectedClaimReview(OperationModel):
    claim_id: str
    section: str
    heading: str | None = None
    text: str
    #: `unattested`: the reviewer answered `supported`, but its evidence failed the
    #: deterministic check (`problems` says which), so the line is not authorized.
    #: `refused`: the engine refused the writer's wording or links before any review -
    #: a fact outside the pool, no linked fact, or wording the edit path rejects.
    verdict: Literal["uncertain", "unsupported", "unattested", "refused"]
    sources: list[ClaimReviewSource]
    #: The deterministic checks an `unattested` line's evidence failed; empty otherwise.
    problems: list[ReviewProblemCode] = Field(default_factory=list)
    #: The reviewer's own explanation for this line, as it answered. An opinion that
    #: helps the user find what to fix, never evidence; failures recorded before it
    #: was kept carry none.
    rationale: str | None = None


class ClaimReviewReason(OperationModel):
    """Inactive proposed wording and exact sources; never approval evidence."""

    code: Literal["claim_review"] = "claim_review"
    claims: list[RejectedClaimReview]


#: Why a failed Operation failed, in a closed vocabulary with typed parameters.
#: `safe_failure_detail` is the safe English diagnostic for logs and generic
#: failures; this structured value lets a client explain supported failures in
#: its own words without parsing that sentence. Both are written with the failure.
FailureReason = Annotated[
    PdfPageLimitReason | MissingFactRenderingReason | RenderCheckReason | ClaimReviewReason,
    Field(discriminator="code"),
]


class OperationView(OperationModel):
    id: str
    application_id: str
    operation_type: OperationType
    status: OperationStatus
    phase: OperationPhase
    message: str = ""
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    cancellation_requested_at: str | None = None
    failure_code: OperationFailureCode | None = None
    safe_failure_detail: str | None = None
    failure_reason: FailureReason | None = None
    #: A succeeded writer Operation's proposed lines that were withheld: each kept the
    #: wording it had before the Operation, and the refused wording is listed here.
    withheld_claims: ClaimReviewReason | None = None
    retry_of_operation_id: str | None = None
    provider: str | None = None
    model: str | None = None
    reasoning_effort: ReasoningEffort | None = None
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    cache_write_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: str | None = None
    outputs: list[OperationOutputReference] = []


class PersistedOperation(OperationView):
    """Runner-facing record; query clients receive the narrower OperationView."""

    payload: dict[str, Any]
    payload_hash: str
    idempotency_key: str
    sources: OperationSources
    lease_owner: str | None = None
    attempts_completed: int = Field(ge=0)
    technical_log_reference: str | None = None


def as_operation_view(record: OperationView) -> OperationView:
    """Narrow a runner record to what a query client is allowed to see.

    `PersistedOperation` carries the payload, the frozen sources, the lease, and
    the idempotency key. None of that belongs to a client: the payload is the
    command the caller already sent, the lease is a runner concern, and the
    idempotency key is a credential for replaying a write. Narrowing happens in
    one function so a new runner-facing field cannot reach a client merely by
    being added to the subclass.

    The field set is read from `OperationView` rather than listed here, so the
    two cannot drift. Passing the record straight to `model_validate` does
    **not** narrow it: a `PersistedOperation` already is an `OperationView`, and
    pydantic returns the instance untouched instead of building a new one. That
    silent no-op is what shipped the whole runner record inside
    `active_operation`.
    """
    return OperationView.model_validate(
        {name: getattr(record, name) for name in OperationView.model_fields}
    )


_ALLOWED_TRANSITIONS: dict[OperationStatus, frozenset[OperationStatus]] = {
    OperationStatus.QUEUED: frozenset(
        {
            OperationStatus.RUNNING,
            OperationStatus.CANCELLED,
            OperationStatus.INTERRUPTED,
        }
    ),
    OperationStatus.RUNNING: frozenset(
        {
            OperationStatus.SUCCEEDED,
            OperationStatus.FAILED,
            OperationStatus.CANCELLED,
            OperationStatus.INTERRUPTED,
        }
    ),
    OperationStatus.SUCCEEDED: frozenset(),
    OperationStatus.FAILED: frozenset(),
    OperationStatus.CANCELLED: frozenset(),
    OperationStatus.INTERRUPTED: frozenset(),
}


def require_operation_transition(current: OperationStatus, target: OperationStatus) -> None:
    """Refuse lifecycle rewrites and transitions not approved by the specification."""
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise OperationContractError(
            f"invalid Operation transition: {current.value} -> {target.value}"
        )


def is_terminal_operation(status: OperationStatus) -> bool:
    return status in TERMINAL_OPERATION_STATUSES
