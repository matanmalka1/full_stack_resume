"""Reconciliation report schemas."""

from __future__ import annotations

from ...application.commands import ReconciliationResult
from ...application.maintenance import OrphanInventory
from .health import HttpSchema

__all__ = ["FactLifecycleReportResponse", "ReconciliationResponse", "OrphanInventoryResponse"]


class FactLifecycleReportResponse(HttpSchema):
    """The fact lifecycle checked against its audit trail."""

    passed: bool
    fact_counts: dict[str, int]
    tracked_facts: int
    facts_version: str
    lifecycle_version: str
    problems: list[str]
    journal_prepared: int
    journal_quarantined: int


class ReconciliationResponse(HttpSchema):
    """Whether stored evidence and the fact lifecycle agree.

    `problems` describes stored artifacts; the lifecycle keeps its own list, so
    a reader can tell which half is broken instead of seeing one merged list.
    """

    passed: bool
    artifact_versions_checked: int
    problems: list[str]
    fact_lifecycle: FactLifecycleReportResponse

    @classmethod
    def of(cls, result: ReconciliationResult) -> ReconciliationResponse:
        return cls(
            passed=result.passed,
            artifact_versions_checked=result.artifact_versions_checked,
            problems=list(result.problems),
            fact_lifecycle=FactLifecycleReportResponse(
                **result.fact_lifecycle.model_dump(mode="json")
            ),
        )


class OrphanInventoryResponse(HttpSchema):
    """Observed candidates may still be awaiting registration by active writers."""

    candidates: list[str]

    @classmethod
    def of(cls, result: OrphanInventory) -> OrphanInventoryResponse:
        return cls(candidates=list(result.candidates))
