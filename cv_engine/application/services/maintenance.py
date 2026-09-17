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
from ..ports import RevisionPayloadStore
from ..ports.maintenance import MaintenanceInspection
from ..ports.transactions import TransactionManager
from .knowledge import KnowledgeService

__all__ = ["MaintenanceService"]


class MaintenanceService:
    """Reconcile stored evidence and the fact lifecycle in one report."""

    def __init__(
        self,
        *,
        payloads: RevisionPayloadStore,
        transactions: TransactionManager,
        inspection: MaintenanceInspection,
        knowledge: KnowledgeService,
    ) -> None:
        self.payloads = payloads
        self.transactions = transactions
        self.inspection = inspection
        self.knowledge = knowledge

    def reconcile(self) -> ReconciliationResult:
        """Report whether stored evidence and the fact lifecycle both agree.

        Neither half is short-circuited: a failing artifact check must not
        hide a broken lifecycle, because the report exists to say what is
        actually wrong rather than to stop at the first problem.
        """
        with self.transactions.read() as tx:
            problems = self.inspection.integrity_problems(tx)
            inventory = self.inspection.artifact_inventory(tx)
        checked = 0
        for row in inventory:
            checked += 1
            verification = self.payloads.verify_payload(row["path"], row["content_hash"])
            if verification == "missing":
                problems.append(f"missing artifact: {row['path']}")
            elif verification == "tampered":
                problems.append(f"artifact hash mismatch: {row['path']}")
            elif verification == "unresolvable":
                problems.append(f"unresolvable artifact reference: {row['path']}")
        fact_lifecycle = self.knowledge.reconcile_facts()
        return ReconciliationResult(
            passed=not problems and fact_lifecycle.passed,
            artifact_versions_checked=checked,
            problems=problems,
            fact_lifecycle=fact_lifecycle,
        )
