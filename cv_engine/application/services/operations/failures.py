"""How a raised failure becomes the failure code an Operation records."""

from __future__ import annotations

from ...errors import (
    ApplicationError,
    ClaimReviewUncertain,
    ClaimReviewUnsupported,
    DependencyUnavailable,
    ExecutionStopped,
    InfrastructureFailure,
    LineageBroken,
    MissingFactRendering,
    PreconditionFailed,
    ProposalRejected,
    ProviderInvalidOutput,
    ProviderNotConfigured,
    ProviderQuotaExhausted,
    ProviderRateLimited,
    ProviderRefused,
    ProviderSchemaViolation,
    ProviderTimeout,
    ProviderUnavailable,
    StateConflict,
)
from ...operations import FailureReason, MissingFactRenderingReason, OperationFailureCode

#: How a classified failure becomes an Operation failure code. Resolved through
#: the exception's MRO, so a subclass nobody registered inherits its parent's
#: classification rather than falling through to a generic execution failure.
#:
#: No code here is retried by the runner. A provider call is retried, at most once
#: and only where it is safe, by the application before the failure is raised
#: (`services/ai_calls.py`); a browser that fails to start is retried by the render
#: handler. What reaches this table is final.
FAILURE_CODE_BY_ERROR: dict[type[ApplicationError], OperationFailureCode] = {
    ProviderTimeout: OperationFailureCode.PROVIDER_TIMEOUT,
    ProviderRateLimited: OperationFailureCode.PROVIDER_RATE_LIMITED,
    ProviderQuotaExhausted: OperationFailureCode.PROVIDER_QUOTA_EXHAUSTED,
    ProviderUnavailable: OperationFailureCode.PROVIDER_UNAVAILABLE,
    ProviderRefused: OperationFailureCode.PROVIDER_REFUSED,
    ProviderSchemaViolation: OperationFailureCode.SCHEMA_VIOLATION,
    ProviderInvalidOutput: OperationFailureCode.INVALID_OUTPUT,
    ClaimReviewUncertain: OperationFailureCode.CLAIM_REVIEW_UNCERTAIN,
    ClaimReviewUnsupported: OperationFailureCode.CLAIM_REVIEW_UNSUPPORTED,
    ProposalRejected: OperationFailureCode.INVALID_OUTPUT,
    ProviderNotConfigured: OperationFailureCode.PROVIDER_NOT_CONFIGURED,
    ExecutionStopped: OperationFailureCode.CANCELLED_BEFORE_ACTIVATION,
    DependencyUnavailable: OperationFailureCode.PROVIDER_REFUSED,
    StateConflict: OperationFailureCode.SOURCE_CHANGED,
    LineageBroken: OperationFailureCode.SOURCE_CHANGED,
    MissingFactRendering: OperationFailureCode.MISSING_FACT_RENDERING,
    PreconditionFailed: OperationFailureCode.VALIDATION_EXECUTION_FAILED,
    InfrastructureFailure: OperationFailureCode.VALIDATION_EXECUTION_FAILED,
}

#: What a client is told about each classification. Deliberately free of the
#: provider's own words: a job description is untrusted input, and a message
#: echoing provider text back into a Problem Details body would carry it out.
_FAILURE_DETAIL: dict[OperationFailureCode, str] = {
    OperationFailureCode.PROVIDER_TIMEOUT: "The AI provider did not answer in time.",
    OperationFailureCode.PROVIDER_RATE_LIMITED: "The AI provider rate limited the request.",
    OperationFailureCode.PROVIDER_QUOTA_EXHAUSTED: (
        "The AI provider account has no remaining credit or reached a spend or usage limit."
    ),
    OperationFailureCode.PROVIDER_UNAVAILABLE: "The AI provider was unavailable.",
    OperationFailureCode.PROVIDER_REFUSED: "The AI provider refused the request.",
    OperationFailureCode.PROVIDER_NOT_CONFIGURED: "No AI provider is configured.",
    OperationFailureCode.SCHEMA_VIOLATION: "The AI provider returned an invalid schema.",
    OperationFailureCode.INVALID_OUTPUT: "The AI proposal was rejected.",
    OperationFailureCode.CLAIM_REVIEW_UNCERTAIN: (
        "Semantic review could not establish support for the proposed claim."
    ),
    OperationFailureCode.CLAIM_REVIEW_UNSUPPORTED: (
        "Semantic review found an unsupported proposed claim."
    ),
    OperationFailureCode.SOURCE_CHANGED: "Operation sources changed.",
    OperationFailureCode.MISSING_FACT_RENDERING: (
        "A selected fact has no rendering in the target language."
    ),
    OperationFailureCode.VALIDATION_EXECUTION_FAILED: "Operation execution failed.",
}


def failure_code_for(error: ApplicationError) -> OperationFailureCode:
    for cls in type(error).__mro__:
        if cls in FAILURE_CODE_BY_ERROR:
            return FAILURE_CODE_BY_ERROR[cls]
    return OperationFailureCode.VALIDATION_EXECUTION_FAILED


def safe_failure_detail_for(error: ApplicationError) -> str:
    """Return public detail, including only structured domain context known to be safe."""
    if isinstance(error, MissingFactRendering):
        return f"Fact {error.fact_id} has no {error.language!r} rendering."
    code = failure_code_for(error)
    return _FAILURE_DETAIL.get(code, "Operation failed.")


def failure_reason_for(error: ApplicationError) -> FailureReason | None:
    """The structured reason for a classified failure, when it has parameters.

    Built from the error's own fields, never from its message, so a client never
    has to parse `safe_failure_detail` back apart to explain the failure.
    """
    if isinstance(error, MissingFactRendering):
        return MissingFactRenderingReason(fact_id=error.fact_id, language=error.language)
    if isinstance(error, ProposalRejected):
        # Set only by semantic review: an unsupported or uncertain line, or one whose
        # supporting evidence failed the deterministic check. Other refusals carry none.
        return error.review_reason
    return None
