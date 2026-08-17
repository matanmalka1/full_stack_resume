"""What the application layer can refuse, as stable types.

A caller that only ever sees one error class has to read messages to decide
what happened, and every message change becomes a breaking change. These types
name the kinds of refusal instead, so an HTTP layer, the CLI, and a test can
each map them without parsing prose.
"""

from __future__ import annotations

from typing import Any


class ApplicationError(RuntimeError):
    """Base class for every refusal the application layer issues."""


class UnknownRecord(ApplicationError):
    """A named application, analysis, snapshot, or artifact does not exist."""


class StateConflict(ApplicationError):
    """The command is legal, but not against the state that is actually there.

    An application that is not ready, an approved version that already exists,
    a snapshot newer than the analysis in hand.
    """


class ValidationBlocked(ApplicationError):
    """A validation report refuses the command.

    Carries the report, so a caller does not have to re-run validation to find
    out what failed.
    """

    def __init__(self, message: str, report: Any = None):
        super().__init__(message)
        self.report = report


class LineageBroken(ApplicationError):
    """The draft no longer descends from the records it claims to."""


class KnowledgeRejected(ApplicationError):
    """The fact lifecycle refused the change."""


class DependencyUnavailable(ApplicationError):
    """A collaborator this command needs was not configured, such as a renderer."""


# The v1 CLI and compatibility façade catch a single workflow error. Keeping the
# name bound to the base class means every refusal above is still caught there,
# so the taxonomy adds precision without changing what the existing surface
# handles.
WorkflowError = ApplicationError
