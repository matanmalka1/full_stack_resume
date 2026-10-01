"""Whole-instance reconciliation and read-only orphan inspection.

Reconciliation spans subjects that no product service owns together: stored
payloads checked against the hashes they were registered with, each logged AI
call's sanitized response checked against its hash, and the fact lifecycle
checked against its audit trail. All must agree for an instance to be sound, so
they are reported as one result rather than several a caller has to combine.

Orphan inspection (architecture.md §7.1) is the third. It lists stored payloads
that nothing references, and deletes nothing: no path in the system deletes an
immutable payload, so no race can remove one a registration is about to reference.

The service holds the payload store and a token-explicit inspection port. That is why
this is a service and not a router helper: `ApiServices` deliberately carries
no repositories or stores, and reconciliation needs both.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ...util import canonical_json, sha256_text
from ..commands import ReconciliationResult
from ..maintenance import ORPHAN_MIN_AGE, OrphanInventory
from ..ports import RevisionPayloadStore
from ..ports.maintenance import MaintenanceInspection
from ..ports.transactions import TransactionManager
from .knowledge import KnowledgeQueryService

__all__ = ["MaintenanceService"]


class MaintenanceService:
    """Reconcile stored evidence and the fact lifecycle; inspect orphans."""

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
            inventory = self.inspection.registered_payloads(tx)
            calls = self.inspection.ai_call_evidence(tx)
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
        for call in calls:
            # The hash is of the canonical form, so it is recomputed from the stored
            # value itself: any change to the logged response shows up here.
            if (
                sha256_text(canonical_json(call["sanitized_response"]))
                != call["sanitized_response_hash"]
            ):
                problems.append(f"AI call response hash mismatch: {call['id']}")
        fact_lifecycle = self.knowledge.reconcile_facts()
        return ReconciliationResult(
            passed=not problems and fact_lifecycle.passed,
            payloads_checked=checked,
            ai_calls_checked=len(calls),
            problems=problems,
            fact_lifecycle=fact_lifecycle,
        )

    def inspect_orphans(self) -> OrphanInventory:
        """Observe unregistered payloads older than `ORPHAN_MIN_AGE`; delete nothing."""
        return OrphanInventory(candidates=self._orphans())

    def _orphans(self) -> list[str]:
        cutoff = datetime.now(UTC) - ORPHAN_MIN_AGE
        stored = self.payloads.payload_inventory(modified_before=cutoff)
        with self.transactions.read() as tx:
            registered = self.inspection.registered_payload_references(tx)
        return sorted(set(stored) - registered)
