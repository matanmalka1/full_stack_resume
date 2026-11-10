"""Whole-instance reconciliation.

Reconciliation spans subjects that no product service owns together: database
integrity, each logged AI call's sanitized response checked against its hash, and
the fact lifecycle checked against its audit trail. All must agree for an instance
to be sound, so they are reported as one result rather than several a caller has
to combine.

The operator CLI invokes it through full runtime composition; `ApiServices`
deliberately does not carry maintenance access, repositories, or stores.
"""

from __future__ import annotations

from ...domain.contracts.knowledge import FactStatus
from ...util import canonical_json, sha256_text
from ..actor import Actor
from ..commands import FactReconciliationResult, ReconciliationResult
from ..ports.maintenance import MaintenanceInspection
from ..ports.transactions import TransactionManager
from .knowledge import KnowledgeQueryService

__all__ = ["MaintenanceService"]


class MaintenanceService:
    """Reconcile stored evidence and the fact lifecycle."""

    def __init__(
        self,
        *,
        transactions: TransactionManager,
        inspection: MaintenanceInspection,
        knowledge: KnowledgeQueryService,
    ) -> None:
        self.transactions = transactions
        self.inspection = inspection
        self.knowledge = knowledge

    def reconcile(self) -> ReconciliationResult:
        """Report whether stored evidence and every user's fact lifecycle agree.

        This is an operator-only whole-instance command. It is deliberately not exposed
        through the user API once multiple users can exist.

        Neither half is short-circuited: a failing artifact check must not
        hide a broken lifecycle, because the report exists to say what is
        actually wrong rather than to stop at the first problem.
        """
        with self.transactions.read() as tx:
            problems = self.inspection.integrity_problems(tx)
            calls = self.inspection.ai_call_evidence(tx)
            user_ids = self.inspection.user_ids(tx)
        for call in calls:
            # The hash is of the canonical form, so it is recomputed from the stored
            # value itself: any change to the logged response shows up here.
            if (
                sha256_text(canonical_json(call["sanitized_response"]))
                != call["sanitized_response_hash"]
            ):
                problems.append(f"AI call response hash mismatch: {call['id']}")
        fact_reports = [
            (user_id, self.knowledge.reconcile_facts(Actor(user_id=user_id)))
            for user_id in user_ids
        ]
        lifecycle_problems = [
            f"user {user_id}: {problem}"
            for user_id, report in fact_reports
            for problem in report.problems
        ]
        fact_lifecycle = FactReconciliationResult(
            passed=not lifecycle_problems,
            fact_counts={
                status.value: sum(report.fact_counts[status.value] for _, report in fact_reports)
                for status in FactStatus
            },
            tracked_facts=sum(report.tracked_facts for _, report in fact_reports),
            facts_version=sha256_text(
                canonical_json({user_id: report.facts_version for user_id, report in fact_reports})
            ),
            lifecycle_version=sha256_text(
                canonical_json(
                    {user_id: report.lifecycle_version for user_id, report in fact_reports}
                )
            ),
            problems=lifecycle_problems,
        )
        return ReconciliationResult(
            passed=not problems and fact_lifecycle.passed,
            ai_calls_checked=len(calls),
            problems=problems,
            fact_lifecycle=fact_lifecycle,
        )
