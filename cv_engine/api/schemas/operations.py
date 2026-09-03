from __future__ import annotations

from pydantic import computed_field

from ...application.ai_configuration import ReasoningEffort
from ...application.operations import (
    OperationAction,
    OperationFailureCode,
    OperationPhase,
    OperationStatus,
    OperationType,
    available_operation_actions,
    is_terminal_operation,
)
from .health import HttpSchema


class OperationOutputResponse(HttpSchema):
    """One immutable output an Operation produced.

    Existence and activation are separate (§11): a failed or cancelled Operation
    may own an output that was registered as inactive evidence, so `active` is
    reported rather than inferred from the status.
    """

    output_type: str
    output_id: str
    active: bool


class OperationResponse(HttpSchema):
    """The §11 Operation query fields, and nothing wider.

    This mirrors `OperationView`, not `PersistedOperation`. The payload, the
    frozen sources, the lease, and the idempotency key stay inside the runner.

    `message` is a safe progress line and `safe_failure_detail` a safe failure
    line; neither carries a path, a provider response, or a key. There is no
    percentage field, because the specification forbids fabricating one.

    The closed sets are typed as the application enums rather than flattened to
    `str`, so the generated TypeScript is a real union instead of `string`, and
    `is_terminal` is reported rather than left to the client. Which statuses end
    an Operation is a lifecycle rule this layer already owns; a client that
    re-derives it keeps a second copy of that rule, and the copy is what goes
    stale when the lifecycle gains a status.

    `is_terminal` and `available_actions` are computed from lifecycle state rather
    than accepted as fields.
    This representation is built from two places - `operation_response` and the
    `active_operation` of an application projection - and a field would have to
    be supplied correctly at both. A computed value has no second place to
    forget.
    """

    id: str
    application_id: str
    operation_type: OperationType
    status: OperationStatus
    phase: OperationPhase
    message: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    cancellation_requested_at: str | None = None
    failure_code: OperationFailureCode | None = None
    safe_failure_detail: str | None = None
    retry_of_operation_id: str | None = None
    provider: str | None = None
    model: str | None = None
    reasoning_effort: ReasoningEffort | None = None
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: str | None = None
    outputs: list[OperationOutputResponse]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_terminal(self) -> bool:
        """Derived from the same predicate the runner uses."""
        return is_terminal_operation(self.status)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def available_actions(self) -> list[OperationAction]:
        """Commands currently accepted, derived by the application layer."""
        return list(
            available_operation_actions(
                self.status,
                self.cancellation_requested_at,
                self.failure_code,
            )
        )
