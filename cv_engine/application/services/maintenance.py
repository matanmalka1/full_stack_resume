"""Whole-instance reconciliation and safe orphan reclaim.

Reconciliation spans two subjects that no product service owns together:
stored artifact evidence checked against the database, and the fact lifecycle
checked against its audit trail. Both must agree for an instance to be sound,
so they are reported as one result rather than two a caller has to combine.

Orphan reclaim (architecture.md §7.1) is the third: it removes a stored
payload only when no database record references it and it has been stored
longer than `ORPHAN_MIN_AGE`, so a write still on its way to registration is
left alone. The reference check runs again immediately before deleting.

The service holds the payload store and a token-explicit inspection port. That is why
this is a service and not a router helper: `ApiServices` deliberately carries
no repositories or stores, and reconciliation needs both.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..commands import ReconciliationResult
from ..errors import InfrastructureFailure
from ..maintenance import ORPHAN_MIN_AGE, OrphanInventory, ReclaimResult
from ..ports import RevisionPayloadStore
from ..ports.maintenance import MaintenanceInspection
from ..ports.transactions import TransactionManager
from .knowledge import KnowledgeQueryService

__all__ = ["MaintenanceService"]


class MaintenanceService:
    """Reconcile stored evidence and the fact lifecycle; reclaim safe orphans."""

    def __init__(
        self,
        *,
        payloads: RevisionPayloadStore,
        transactions: TransactionManager,
        inspection: MaintenanceInspection,
        knowledge: KnowledgeQueryService,
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

    def inspect_orphans(self) -> OrphanInventory:
        """Observe unregistered payloads older than `ORPHAN_MIN_AGE`; delete nothing."""
        return OrphanInventory(candidates=self._orphans())

    def reclaim_orphans(self) -> ReclaimResult:
        """Remove every payload that is unregistered and older than `ORPHAN_MIN_AGE`.

        The registered set is read again after listing and before any deletion.
        A candidate that turned out to be referenced is an integrity failure:
        nothing registers a payload that old, so reclaim stops rather than
        delete evidence.
        """
        candidates = self._orphans()
        if not candidates:
            return ReclaimResult(removed=[])
        with self.transactions.read() as tx:
            registered = self.inspection.registered_payload_references(tx)
        referenced = sorted(set(candidates) & registered)
        if referenced:
            raise InfrastructureFailure(
                f"integrity failure: {referenced} became registered after being stored "
                f"more than {ORPHAN_MIN_AGE} earlier; nothing was removed"
            )
        for key in candidates:
            self.payloads.delete_payload(key)
        return ReclaimResult(removed=candidates)

    def _orphans(self) -> list[str]:
        cutoff = datetime.now(UTC) - ORPHAN_MIN_AGE
        stored = self.payloads.payload_inventory(modified_before=cutoff)
        with self.transactions.read() as tx:
            registered = self.inspection.registered_payload_references(tx)
        return sorted(set(stored) - registered)
