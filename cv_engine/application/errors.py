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
from typing import Any

_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


def _default_code(cls: type) -> str:
    return _CAMEL_BOUNDARY.sub("_", cls.__name__).upper()


class ApplicationError(RuntimeError):
    """Base class for every expected application-layer failure."""

    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message)
        self.code = code or _default_code(type(self))


class UnknownRecord(ApplicationError):
    """A named application, analysis, snapshot, or artifact does not exist."""


class StateConflict(ApplicationError):
    """The command conflicts with current mutable state or concurrency."""


class PreconditionFailed(ApplicationError):
    """The named state exists but cannot legally satisfy the command."""


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


class ArtifactHashMismatch(PreconditionFailed):
    """A registered artifact payload no longer matches its registered hash."""


class DependencyUnavailable(ApplicationError):
    """A required collaborator was not configured."""


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

    `provenance` is present when the provider answered and the answer was
    refused - a schema violation above all. Product specification §6 invariant
    15 lets a refused output exist as inactive immutable evidence, so the
    sanitized bytes travel with the refusal rather than being dropped at the
    raise site, which is the only place they still exist.

    It carries the whole `ProviderTaskResult`, not just the bytes, because a
    refusal is exactly when the question "which model, under which contract,
    refused this" has to be answerable. The parsed output is empty; everything
    else is as real as it is on a successful call.

    Typed loosely for the same reason `ProposalRejected.evidence` is: the value
    is a domain type, and the taxonomy is what the layers that own those types
    depend on.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        provenance: Any = None,
    ):
        super().__init__(message, code=code)
        self.provenance = provenance


class ProviderTimeout(ProviderFailure):
    """The provider did not answer within the configured timeout."""


class ProviderRateLimited(ProviderFailure):
    """The provider answered 429."""


class ProviderUnavailable(ProviderFailure):
    """The provider answered 5xx, or the request never reached it."""


class ProviderRefused(ProviderFailure):
    """The provider declined to answer the task."""


class ProviderSchemaViolation(ProviderFailure):
    """The provider returned output that is not the requested schema."""


class ProviderInvalidOutput(ProviderFailure):
    """The provider returned a well-formed schema whose content cannot be used."""


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
    already preserved in the sanitized response artifact.
    """

    def __init__(self, message: str, *, unsupported: list[str] | None = None):
        super().__init__(message)
        self.unsupported = list(unsupported or [])
        # Set by the service that already preserved the response this refusal is
        # about, so the handler can register it as inactive evidence instead of
        # leaving an orphaned payload behind. Typed loosely because the value is
        # an application-services type and nothing in the taxonomy may import
        # one - the taxonomy is what those services depend on.
        self.evidence: Any = None


# Codes the specification names directly (`state-and-use-cases.md` §22). They are
# contracted strings rather than derived ones, so they are declared in one place
# instead of being retyped at each raise site.
IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"
VALIDATION_STALE = "VALIDATION_STALE"
VALIDATION_REQUIRED = "VALIDATION_REQUIRED"
UNLINKED_CLAIM = "UNLINKED_CLAIM"
SOURCE_CHANGED = "SOURCE_CHANGED"
KNOWLEDGE_RECONCILIATION_REQUIRED = "KNOWLEDGE_RECONCILIATION_REQUIRED"
DUPLICATE_ACKNOWLEDGEMENT_REQUIRED = "DUPLICATE_ACKNOWLEDGEMENT_REQUIRED"
WORKING_PROJECTION_DIVERGED = "WORKING_PROJECTION_DIVERGED"


WorkflowError = ApplicationError
