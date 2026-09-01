"""How a raised failure becomes the failure code an Operation records."""

from __future__ import annotations

from ...errors import (
    ApplicationError,
    DependencyUnavailable,
    InfrastructureFailure,
    LineageBroken,
    MissingFactRendering,
    PreconditionFailed,
    ProposalRejected,
    ProviderInvalidOutput,
    ProviderRateLimited,
    ProviderRefused,
    ProviderSchemaViolation,
    ProviderTimeout,
    ProviderUnavailable,
    StateConflict,
)
from ...operations import OperationFailureCode

#: How a classified failure becomes an Operation failure code, and therefore
#: whether it is retried. Resolved through the exception's MRO, so a subclass
#: nobody registered inherits its parent's classification rather than falling
#: through to a generic execution failure.
#:
#: Exactly four of these are transient (`TRANSIENT_FAILURE_CODES`), and
#: `allows_automatic_retry` gives each of them one attempt. Everything else -
#: refusal, schema violation, business validation, an unsupported claim, a
#: conflict, a stale source - is terminal on the first failure, which is what
#: test-plan §6 requires. That policy is not restated here; it follows from the
#: code this table chooses.
FAILURE_CODE_BY_ERROR: dict[type[ApplicationError], OperationFailureCode] = {
    ProviderTimeout: OperationFailureCode.PROVIDER_TIMEOUT,
    ProviderRateLimited: OperationFailureCode.PROVIDER_RATE_LIMITED,
    ProviderUnavailable: OperationFailureCode.PROVIDER_UNAVAILABLE,
    ProviderRefused: OperationFailureCode.PROVIDER_REFUSED,
    ProviderSchemaViolation: OperationFailureCode.SCHEMA_VIOLATION,
    ProviderInvalidOutput: OperationFailureCode.INVALID_OUTPUT,
    # A Proposal the engine refused is an invalid output, not a transport
    # failure, and there is no separate code for it: the baseline schema's
    # `failure_code` CHECK is the specification's list, and inventing another
    # value would be a schema change for a distinction the safe failure detail
    # already carries.
    ProposalRejected: OperationFailureCode.INVALID_OUTPUT,
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
    OperationFailureCode.PROVIDER_UNAVAILABLE: "The AI provider was unavailable.",
    OperationFailureCode.PROVIDER_REFUSED: "The AI provider refused the request.",
    OperationFailureCode.SCHEMA_VIOLATION: "The AI provider returned an invalid schema.",
    OperationFailureCode.INVALID_OUTPUT: "The AI proposal was rejected.",
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
