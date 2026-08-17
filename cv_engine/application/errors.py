"""Stable refusals exposed by the application boundary."""

from __future__ import annotations

from typing import Any


class ApplicationError(RuntimeError):
    """Base class for every expected application-layer failure."""


class UnknownRecord(ApplicationError):
    """A named application, analysis, snapshot, or artifact does not exist."""


class StateConflict(ApplicationError):
    """The command conflicts with current mutable state or concurrency."""


class PreconditionFailed(ApplicationError):
    """The named state exists but cannot legally satisfy the command."""


class ValidationBlocked(PreconditionFailed):
    """Approval/render/submission was attempted against failing validation."""

    def __init__(self, message: str, report: Any = None):
        super().__init__(message)
        self.report = report


class LineageBroken(PreconditionFailed):
    """A source does not belong to, or no longer supports, the target chain."""


class KnowledgeRejected(PreconditionFailed):
    """The fact lifecycle or knowledge policy refused a mutation."""


class DependencyUnavailable(ApplicationError):
    """A required collaborator was not configured."""


class InfrastructureFailure(ApplicationError):
    """A configured persistence, provider, browser, or filesystem dependency failed."""


WorkflowError = ApplicationError
