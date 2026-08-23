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


class DependencyUnavailable(ApplicationError):
    """A required collaborator was not configured."""


class InfrastructureFailure(ApplicationError):
    """A configured persistence, provider, browser, or filesystem dependency failed."""


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


WorkflowError = ApplicationError
