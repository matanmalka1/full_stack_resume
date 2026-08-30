"""Whole-instance reconciliation.

Reconciliation spans two subjects that no product service owns together:
stored artifact evidence checked against the database, and the fact lifecycle
checked against its audit trail. Both must agree for an instance to be sound,
so they are reported as one result rather than two a caller has to combine.

The service holds the payload store and the repository directly. That is why
this is a service and not a router helper: `ApiServices` deliberately carries
no repositories or stores, and reconciliation needs both.
"""

from __future__ import annotations

from ..commands import ReconciliationResult
from ..maintenance import reconcile_artifacts
from ..ports import ReadinessRepository, RevisionPayloadStore
from .knowledge import KnowledgeService

__all__ = ["MaintenanceService"]


class MaintenanceService:
    """Reconcile stored evidence and the fact lifecycle in one report."""

    def __init__(
        self,
        *,
        payloads: RevisionPayloadStore,
        repository: ReadinessRepository,
        knowledge: KnowledgeService,
    ) -> None:
        self.payloads = payloads
        self.repository = repository
        self.knowledge = knowledge

    def reconcile(self) -> ReconciliationResult:
        """Report whether stored evidence and the fact lifecycle both agree.

        Neither half is short-circuited: a failing artifact check must not
        hide a broken lifecycle, because the report exists to say what is
        actually wrong rather than to stop at the first problem.
        """
        report = reconcile_artifacts(self.payloads, self.repository)
        fact_lifecycle = self.knowledge.reconcile_facts()
        return ReconciliationResult(
            passed=report["passed"] and fact_lifecycle.passed,
            artifact_versions_checked=report["artifact_versions_checked"],
            problems=report["problems"],
            fact_lifecycle=fact_lifecycle,
        )
