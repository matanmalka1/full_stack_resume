"""Stable refusals exposed by the application boundary.

Every refusal carries a `code`. The code is what a client switches on; the message
is for a human. The default is derived from the class name, so a new exception class
gets a stable code without anyone having to remember to register one, and the code
cannot silently disagree with the class that raised it.

An explicit `code=` is for the handful of refusals the specification names by code
(`state-and-use-cases.md` §22). Those are contracted strings: changing one is a
Class B change.

Mapping a refusal to an HTTP status is the API layer's job and belongs in one table
there. Nothing in this module knows about HTTP.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from .operations import ClaimReviewReason

_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


def _default_code(cls: type) -> str:
    return _CAMEL_BOUNDARY.sub("_", cls.__name__).upper()


class ApplicationError(RuntimeError):
    """Base class for every expected application-layer failure."""

    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message)
        self.code = code or _default_code(type(self))


class UnknownRecord(ApplicationError):
    """A named application, analysis, or artifact does not exist."""


class StateConflict(ApplicationError):
    """The command conflicts with current mutable state or concurrency."""


class PreconditionFailed(ApplicationError):
    """The named state exists but cannot legally satisfy the command."""


class ApplicationIntakeInvalid(PreconditionFailed):
    """One intake field failed deterministic application validation."""

    def __init__(
        self, field: Literal["company", "target_role", "job_text", "source_url"], message: str
    ):
        self.field = field
        super().__init__(message)


class MissingFactRendering(PreconditionFailed):
    """A selected canonical fact has no wording in the document language."""

    def __init__(self, fact_id: str, language: str):
        self.fact_id = fact_id
        self.language = language
        super().__init__(
            f"Fact {fact_id} has no {language!r} rendering.",
            code="MISSING_FACT_RENDERING",
        )


class DuplicateAcknowledgementRequired(PreconditionFailed):
    """Application creation found duplicates that were not acknowledged."""

    def __init__(self, message: str, matches: list[Any]):
        super().__init__(message, code=DUPLICATE_ACKNOWLEDGEMENT_REQUIRED)
        self.matches = matches


class ValidationBlocked(PreconditionFailed):
    """Approval/render/submission was attempted against failing validation."""

    def __init__(self, message: str, report: Any = None, *, code: str | None = None):
        super().__init__(message, code=code)
        self.report = report


class LineageBroken(PreconditionFailed):
    """A source does not belong to, or no longer supports, the target chain."""


class KnowledgeRejected(PreconditionFailed):
    """The fact lifecycle or knowledge policy refused a mutation."""


# The three ways a registered artifact can fail its own integrity verification.
# Separate classes rather than one, because only the store knows which check
# failed and a client switching on `code` needs to be able to tell "somebody
# moved the file" from "somebody changed it" from "the row points outside the
# root". `404` stays reserved for an ID that is registered nowhere; each of
# these names a record that exists and whose stored evidence does not check out.
# Their codes are derived from the class names, so none of them can arrive
# without one.


class ArtifactContainmentRefused(PreconditionFailed):
    """A registered artifact path resolves outside the artifact root."""


class ArtifactPayloadMissing(PreconditionFailed):
    """A registered artifact payload is no longer on disk."""


class DependencyUnavailable(ApplicationError):
    """A required collaborator was not configured."""


class ProviderNotConfigured(DependencyUnavailable):
    """An AI task was requested and no AI provider is configured to run it."""


class InfrastructureFailure(ApplicationError):
    """A configured persistence, provider, browser, or filesystem dependency failed."""


# How a provider call failed, as classes rather than as words in a message.
#
# The Operation runner has to decide two things from a provider failure: which
# `OperationFailureCode` to record, and whether one automatic retry is allowed.
# Until Stage G that decision was made by case-folding the exception message and
# looking for "429", "timeout", and "http 5" - so a reworded message silently
# reclassified a failure, and a provider refusal that happened to contain the
# digits 429 would have been retried. The class is what carries the meaning now,
# and the mapping lives in one table beside the codes.


class ProviderFailure(InfrastructureFailure):
    """Base class for a classified AI provider execution failure.

    Raised by the application after the failed attempt is already in the AI call
    log, so it carries no evidence of its own: the log is where the refused or
    unanswered call lives.
    """


class ProviderTimeout(ProviderFailure):
    """The provider did not answer within the configured timeout."""


class ProviderRateLimited(ProviderFailure):
    """The provider answered 429 for a rate limit: slow down and try later."""


class ProviderQuotaExhausted(ProviderFailure):
    """The provider refused for billing: no credit left, or a spend or usage limit hit."""


class ProviderUnavailable(ProviderFailure):
    """The provider answered 5xx, or the request never reached it."""


class ProviderRefused(ProviderFailure):
    """The provider declined to answer the task."""


class ProviderInvalidOutput(ProviderFailure):
    """The provider's output cannot be used: outside the requested schema, or in it but unusable."""


class ExecutionStopped(ApplicationError):
    """A retry was due, but the Operation was cancelled or is no longer this runner's.

    Not a provider failure: the attempt before it is already logged, and the
    Operation ends as its cancellation or lost lease says, not as a provider error.
    """


class ProposalRejected(PreconditionFailed):
    """A Proposal failed deterministic policy or semantic support validation.

    Not a transport failure: the provider answered, and the answer is refused.
    It is separate from `ProviderInvalidOutput` because the two mean different
    things to a reader of the Operation record - a malformed answer, versus an
    answer that claims support it does not have (invariant 12). Neither is ever
    retried, and neither is silently dropped.

    `unsupported` names the claims that failed semantic support, so the failure
    detail can say which lines were refused rather than only that something
    was. The wording itself is not echoed: it is provider text, and it is
    already in the AI call log's sanitized response.
    """

    def __init__(self, message: str, *, unsupported: list[str] | None = None):
        super().__init__(message)
        self.unsupported = list(unsupported or [])
        self.review_reason: ClaimReviewReason | None = None


class ClaimReviewUncertain(ProposalRejected):
    """The semantic reviewer could not establish support for a proposed claim."""


class ClaimReviewUnsupported(ProposalRejected):
    """The semantic reviewer found that a proposed claim exceeds its sources."""


# Codes the specification names directly (`state-and-use-cases.md` §22). They are
# contracted strings rather than derived ones, so they are declared in one place
# instead of being retyped at each raise site.
IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"
SOURCE_CHANGED = "SOURCE_CHANGED"
KNOWLEDGE_RECONCILIATION_REQUIRED = "KNOWLEDGE_RECONCILIATION_REQUIRED"
DUPLICATE_ACKNOWLEDGEMENT_REQUIRED = "DUPLICATE_ACKNOWLEDGEMENT_REQUIRED"
DOCUMENT_CHANGED = "DOCUMENT_CHANGED"
DOCUMENT_NOT_APPROVED = "DOCUMENT_NOT_APPROVED"
DOCUMENT_NOT_READY = "DOCUMENT_NOT_READY"


WorkflowError = ApplicationError
