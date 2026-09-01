"""Storage-neutral contracts and lifecycle rules for persisted Operations.

Operations coordinate application services; they are not domain aggregates.  This
module therefore owns the values shared by the persistence adapter, runner, and query
projection without importing any of those hosts.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..util import canonical_json, sha256_text


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
    if (
        status is OperationStatus.FAILED
        and failure_code is OperationFailureCode.MISSING_FACT_RENDERING
    ):
        return ()
    if status in TERMINAL_OPERATION_STATUSES:
        return (OperationAction.RETRY,)
    raise OperationContractError(f"operation action policy does not cover status {status}")


class OperationType(StrEnum):
    ANALYZE_JOB = "analyze_job"
    PROPOSE_SELECTION_PLAN = "propose_selection_plan"
    CREATE_DRAFT = "create_draft"
    REGENERATE_SECTION = "regenerate_section"
    REGENERATE_CLAIM = "regenerate_claim"
    RENDER_REVISION = "render_revision"


class OperationPhase(StrEnum):
    QUEUED = "queued"
    WAITING_FOR_APPLICATION = "waiting_for_application"
    WAITING_FOR_RENDER_SLOT = "waiting_for_render_slot"
    WAITING_FOR_AI_SLOT = "waiting_for_ai_slot"
    PRE_EXECUTION_CHECK = "pre_execution_check"
    EXECUTING = "executing"
    RETRY_WAIT = "retry_wait"
    PRE_ACTIVATION_CHECK = "pre_activation_check"
    ACTIVATING = "activating"
    COMPLETED = "completed"


class OperationFailureCode(StrEnum):
    SOURCE_CHANGED = "SOURCE_CHANGED"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_REFUSED = "PROVIDER_REFUSED"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    SCHEMA_VIOLATION = "SCHEMA_VIOLATION"
    RENDER_FAILED = "RENDER_FAILED"
    BROWSER_START_FAILED = "BROWSER_START_FAILED"
    MISSING_FACT_RENDERING = "MISSING_FACT_RENDERING"
    VALIDATION_EXECUTION_FAILED = "VALIDATION_EXECUTION_FAILED"
    CANCELLED_BEFORE_ACTIVATION = "CANCELLED_BEFORE_ACTIVATION"


TRANSIENT_FAILURE_CODES = frozenset(
    {
        OperationFailureCode.PROVIDER_TIMEOUT,
        OperationFailureCode.PROVIDER_RATE_LIMITED,
        OperationFailureCode.PROVIDER_UNAVAILABLE,
        OperationFailureCode.BROWSER_START_FAILED,
    }
)


class OperationResourceKind(StrEnum):
    APPLICATION_MUTATION = "application_mutation"
    RENDER_BROWSER = "render_browser"
    AI = "ai"


class OperationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OperationResource(OperationModel):
    kind: OperationResourceKind
    key: str


class OperationSources(OperationModel):
    """Exact optimistic inputs frozen when an Operation is created."""

    job_snapshot_id: str | None = None
    job_snapshot_hash: str | None = None
    job_analysis_id: str | None = None
    selection_plan_id: str | None = None
    working_draft_id: str | None = None
    working_draft_edit_version: int | None = Field(default=None, ge=1)
    working_draft_content_hash: str | None = None
    approved_revision_id: str | None = None
    knowledge_context_hash: str | None = None
    dependency_hashes: dict[str, str] = {}

    @model_validator(mode="after")
    def complete_working_draft_identity(self) -> OperationSources:
        values = (
            self.working_draft_id,
            self.working_draft_edit_version,
            self.working_draft_content_hash,
        )
        if any(value is not None for value in values) and not all(
            value is not None for value in values
        ):
            raise ValueError(
                "working draft optimistic identity requires id, edit version, and content hash"
            )
        return self


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


class OperationOutputReference(OperationModel):
    output_type: str
    output_id: str
    active: bool


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
    retry_of_operation_id: str | None = None
    outputs: list[OperationOutputReference] = []


class PersistedOperation(OperationView):
    """Runner-facing record; query clients receive the narrower OperationView."""

    payload: dict[str, Any]
    payload_hash: str
    idempotency_key: str
    sources: OperationSources
    resources: tuple[OperationResource, ...]
    provider: str | None = None
    model: str | None = None
    lease_owner: str | None = None
    lease_expires_at: str | None = None
    heartbeat_at: str | None = None
    attempts_completed: int = Field(ge=0)
    next_attempt_at: str | None = None
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


def required_operation_resources(request: CreateOperation) -> tuple[OperationResource, ...]:
    """Derive lock requirements so callers cannot weaken concurrency policy."""
    resources = [
        OperationResource(
            kind=OperationResourceKind.APPLICATION_MUTATION,
            key=request.application_id,
        )
    ]
    if request.operation_type is OperationType.RENDER_REVISION:
        resources.append(OperationResource(kind=OperationResourceKind.RENDER_BROWSER, key="global"))
    always_ai = {
        OperationType.PROPOSE_SELECTION_PLAN,
        OperationType.REGENERATE_SECTION,
        OperationType.REGENERATE_CLAIM,
    }
    if request.operation_type in always_ai or request.provider not in (None, "deterministic"):
        resources.append(OperationResource(kind=OperationResourceKind.AI, key="global"))
    return tuple(resources)


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


def allows_automatic_retry(code: OperationFailureCode, attempts_completed: int) -> bool:
    """Exactly one automatic retry is available for classified transient failures."""
    if attempts_completed < 1:
        raise OperationContractError("attempts_completed must include the failed attempt")
    return code in TRANSIENT_FAILURE_CODES and attempts_completed == 1
