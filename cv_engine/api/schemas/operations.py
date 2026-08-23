from __future__ import annotations

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
    """

    id: str
    application_id: str
    operation_type: str
    status: str
    phase: str
    message: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    cancellation_requested_at: str | None = None
    failure_code: str | None = None
    safe_failure_detail: str | None = None
    retry_of_operation_id: str | None = None
    outputs: list[OperationOutputResponse]
