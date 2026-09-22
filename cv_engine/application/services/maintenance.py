"""Whole-instance reconciliation and safe orphan reclaim.

Reconciliation spans two subjects that no product service owns together:
stored artifact evidence checked against the database, and the fact lifecycle
checked against its audit trail. Both must agree for an instance to be sound,
so they are reported as one result rather than two a caller has to combine.

Orphan reclaim (architecture.md §7.1) is the third: it removes a stored
payload only after the payload write lease that reserved it is fenced, and
only after re-checking - before deleting anything - that no database record
references it. That check is what makes deletion safe, not fencing alone.

The service holds the payload store and a token-explicit inspection port. That is why
this is a service and not a router helper: `ApiServices` deliberately carries
no repositories or stores, and reconciliation needs both.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ...util import utc_now
from ..commands import ReconciliationResult
from ..errors import InfrastructureFailure
from ..maintenance import OrphanInventory, ReclaimResult
from ..ports import RevisionPayloadStore
from ..ports.maintenance import MaintenanceInspection
from ..ports.payload_leases import RECLAIM_GRACE_SECONDS, PayloadWriteLeaseStore
from ..ports.transactions import TransactionManager
from .knowledge import KnowledgeQueryService

__all__ = ["MaintenanceService"]


def _reclaim_deadline(now: str) -> str:
    return (datetime.fromisoformat(now) + timedelta(seconds=RECLAIM_GRACE_SECONDS)).isoformat()


class MaintenanceService:
    """Reconcile stored evidence and the fact lifecycle; reclaim safe orphans."""

    def __init__(
        self,
        *,
        payloads: RevisionPayloadStore,
        transactions: TransactionManager,
        inspection: MaintenanceInspection,
        leases: PayloadWriteLeaseStore,
        knowledge: KnowledgeQueryService,
    ) -> None:
        self.payloads = payloads
        self.transactions = transactions
        self.inspection = inspection
        self.leases = leases
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
        """Observe unreferenced, unleased payloads without deleting anything."""
        with self.transactions.read() as tx:
            registered = self.inspection.registered_payload_references(tx)
            leased = self.leases.live_physical_keys(tx)
        stored = self.payloads.payload_inventory()
        return OrphanInventory(candidates=sorted(set(stored) - registered - leased))

    def reclaim_orphans(self) -> ReclaimResult:
        """Remove every candidate this call can safely prove is abandoned.

        Not a fixed point: a storage write behind an already-fenced lease is
        not itself prevented, so it can still land after this call finishes,
        producing a leaseless orphan only a later call observes and removes
        (architecture.md §7.1).
        """
        now = utc_now()
        removed: set[str] = set()

        with self.transactions.write() as tx:
            expired = self.leases.expired_pending(tx, now)
        for entry in expired:
            removed.update(self._fence_and_finish(entry, now))

        with self.transactions.read() as tx:
            stale = self.leases.stale_reclaiming(tx, now)
        for entry in stale:
            removed.update(
                self._finish_reclaim(entry["group_key"], entry["attempt_id"], entry["keys"])
            )

        with self.transactions.read() as tx:
            registered = self.inspection.registered_payload_references(tx)
            leased = self.leases.live_physical_keys(tx)
        stored = self.payloads.payload_inventory()
        for key in sorted(set(stored) - registered - leased):
            removed.update(self._reclaim_leaseless(key, registered))

        return ReclaimResult(removed=sorted(removed))

    def reclaim_group(self, group_key: str) -> ReclaimResult:
        """Resume an expired write for one logical group before a genuine retry."""
        now = utc_now()
        with self.transactions.read() as tx:
            expired = [
                entry
                for entry in self.leases.expired_pending(tx, now)
                if entry["group_key"] == group_key
            ]
            stale = [
                entry
                for entry in self.leases.stale_reclaiming(tx, now)
                if entry["group_key"] == group_key
            ]
        removed: set[str] = set()
        for entry in expired:
            removed.update(self._fence_and_finish(entry, now))
        for entry in stale:
            removed.update(
                self._finish_reclaim(entry["group_key"], entry["attempt_id"], entry["keys"])
            )
        return ReclaimResult(removed=sorted(removed))

    def _fence_and_finish(self, entry: dict[str, Any], now: str) -> list[str]:
        group_key, attempt_id, keys = entry["group_key"], entry["attempt_id"], entry["keys"]
        with self.transactions.write() as tx:
            fenced = self.leases.fence(
                tx, group_key, attempt_id, now=now, reclaim_deadline=_reclaim_deadline(now)
            )
        if not fenced:
            # Lost the race: committed, or already being reclaimed elsewhere.
            return []
        return self._finish_reclaim(group_key, attempt_id, keys)

    def _finish_reclaim(self, group_key: str, attempt_id: str, keys: list[str]) -> list[str]:
        with self.transactions.read() as tx:
            registered = self.inspection.registered_payload_references(tx)
        referenced = [key for key in keys if key in registered]
        if referenced:
            raise InfrastructureFailure(
                f"integrity failure: payload write lease {group_key} ({attempt_id}) was "
                f"fenced, but the database still references {referenced}; fencing should "
                "have made this impossible"
            )
        for key in keys:
            self.payloads.delete_payload(key)
        with self.transactions.write() as tx:
            self.leases.delete_row(tx, group_key, attempt_id)
        return list(keys)

    def _reclaim_leaseless(self, key: str, registered: set[str]) -> list[str]:
        if key in registered:
            raise InfrastructureFailure(
                f"integrity failure: {key} has no write lease but the database "
                "references it; a leaseless key must never be registered"
            )
        self.payloads.delete_payload(key)
        return [key]
