"""Base DTO type and the cross-domain whole-instance reconciliation report."""

from __future__ import annotations

from ._base import BoundaryDTO, DuplicateMatchReason, WriteClient
from .knowledge import FactReconciliationResult

__all__ = [
    "BoundaryDTO",
    "WriteClient",
    "DuplicateMatchReason",
    "ReconciliationResult",
]


class ReconciliationResult(BoundaryDTO):
    """The whole-instance reconciliation report.

    `passed` is the conjunction of both halves: stored evidence agreeing with
    the database, and the fact lifecycle agreeing with its audit trail. A
    caller that reads only one half would report a healthy instance while the
    other half is broken.
    """

    passed: bool
    artifact_versions_checked: int
    problems: list[str]
    fact_lifecycle: FactReconciliationResult
