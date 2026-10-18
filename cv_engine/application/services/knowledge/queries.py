"""The reads over the fact lifecycle: fact projections and reconciliation of the
persisted statuses against their event trail. Nothing here writes.
"""

from __future__ import annotations

from ....domain.contracts.knowledge import FactStatus
from ....domain.emphasis import EmphasisPolicyStore
from ....domain.facts import FactStore, FactStoreError
from ....domain.knowledge import Knowledge
from ....domain.profiles import ProfileStore
from ...actor import Actor
from ...commands import (
    FactAttachmentProfileTarget,
    FactAttachmentSectionTarget,
    FactAttachmentTargetsResult,
    FactDetailResult,
    FactHistoryResult,
    FactListItem,
    FactListResult,
    FactReconciliationResult,
    KnowledgeVersionsResult,
    fact_event_view,
)
from ...errors import KnowledgeRejected, UnknownRecord
from ...ports.knowledge_lifecycle import KnowledgeLifecycleStore
from ...ports.transactions import TransactionManager
from ...ports.user_knowledge import UserKnowledgeSource
from ..documents import load_knowledge

__all__ = ["KnowledgeQueryService"]


class KnowledgeQueryService:
    """Read-only fact projections and lifecycle reconciliation."""

    def __init__(
        self,
        *,
        transactions: TransactionManager,
        store: KnowledgeLifecycleStore,
        knowledge: UserKnowledgeSource,
    ):
        self.transactions = transactions
        self.store = store
        self._knowledge = knowledge

    def load_knowledge(self, actor: Actor) -> Knowledge:
        return load_knowledge(self._knowledge, actor)

    def knowledge(self, actor: Actor) -> tuple[FactStore, ProfileStore, EmphasisPolicyStore]:
        loaded = self.load_knowledge(actor)
        return loaded.facts, loaded.profiles, loaded.policies

    def fact_store(self, actor: Actor) -> FactStore:
        try:
            return self._knowledge.facts(actor.user_id)
        except ValueError as exc:
            raise KnowledgeRejected(str(exc)) from exc

    def knowledge_versions(self, actor: Actor) -> KnowledgeVersionsResult:
        """One hash surface per knowledge dependency an artifact can depend on."""
        return KnowledgeVersionsResult.model_validate(self.load_knowledge(actor).versions())

    def list_facts(self, actor: Actor, status: str | None = None) -> FactListResult:
        facts = self.fact_store(actor)
        with self.transactions.read() as tx:
            recorded = self.store.latest_fact_statuses(tx, actor.user_id)
        items = facts.by_status(status)
        if status is None:
            # No explicit filter excludes deleted facts by default (state-and-
            # use-cases.md §17); `status=deleted` still reaches them.
            items = [fact for fact in items if fact.status is not FactStatus.DELETED]
        return FactListResult(
            items=[
                FactListItem(fact=fact, recorded_status=recorded.get(fact.fact_id))
                for fact in items
            ]
        )

    def show_fact(self, actor: Actor, fact_id: str) -> FactDetailResult:
        facts = self.fact_store(actor)
        try:
            fact = facts.get(fact_id)
        except FactStoreError as exc:
            raise UnknownRecord(str(exc)) from exc
        with self.transactions.read() as tx:
            events = self.store.fact_events(tx, actor.user_id, fact_id)
        return FactDetailResult(fact=fact, events=[fact_event_view(row) for row in events])

    def fact_attachment_targets(
        self, actor: Actor, fact_id: str | None = None
    ) -> FactAttachmentTargetsResult:
        """Read existing Profile sections without exposing mutable Profile documents."""
        facts, profiles, _policies = self.knowledge(actor)
        if fact_id is not None:
            try:
                target = facts.get(fact_id)
            except FactStoreError as exc:
                raise UnknownRecord(str(exc)) from exc
            if target.status is FactStatus.DELETED:
                # Excluded from attachment-targets results, the same as it is
                # excluded from `list_facts` by default (state-and-use-cases.md §17).
                raise UnknownRecord(f"fact is deleted: {fact_id}")
        return FactAttachmentTargetsResult(
            profiles=[
                FactAttachmentProfileTarget(
                    profile=profile.profile,
                    label=profile.normalized_role,
                    sections=[
                        FactAttachmentSectionTarget(
                            section=section.name_en,
                            label=section.name_he,
                            attached=fact_id in section.fact_ids if fact_id is not None else False,
                            pinned=fact_id in section.pinned_fact_ids
                            if fact_id is not None
                            else False,
                        )
                        for section in profile.sections
                    ],
                )
                for profile in sorted(
                    profiles.profiles.values(), key=lambda item: item.profile.value
                )
            ]
        )

    def fact_history(self, actor: Actor, fact_id: str | None = None) -> FactHistoryResult:
        if fact_id is not None:
            try:
                self.fact_store(actor).get(fact_id)
            except FactStoreError as exc:
                raise UnknownRecord(str(exc)) from exc
        with self.transactions.read() as tx:
            events = self.store.fact_events(tx, actor.user_id, fact_id)
        return FactHistoryResult(events=[fact_event_view(row) for row in events])

    def reconcile_facts(self, actor: Actor) -> FactReconciliationResult:
        """Check the persisted lifecycle against its audit trail.

        Three disagreements matter: a trail entry for a fact that no longer
        exists, a live status that the trail never recorded, and a live status
        that contradicts the last recorded one. Each means a status was changed
        outside the lifecycle, which is exactly what the trail exists to catch.
        """
        facts = self.fact_store(actor)
        with self.transactions.read() as tx:
            recorded = self.store.latest_fact_statuses(tx, actor.user_id)
        problems: list[str] = []
        for fact_id, status in recorded.items():
            if fact_id not in facts.facts:
                problems.append(f"fact event references a fact that no longer exists: {fact_id}")
            elif facts.facts[fact_id].status.value != status:
                problems.append(
                    f"fact {fact_id} is {facts.facts[fact_id].status.value} in Knowledge but the "
                    f"lifecycle trail last recorded {status}"
                )
        untracked = [
            fact.fact_id
            for fact in facts.by_status()
            if fact.status is not FactStatus.CANONICAL and fact.fact_id not in recorded
        ]
        problems.extend(
            f"non-canonical fact has no lifecycle event: {fact_id}" for fact_id in untracked
        )
        counts = {status.value: len(facts.by_status(status)) for status in FactStatus}
        return FactReconciliationResult(
            passed=not problems,
            fact_counts=counts,
            tracked_facts=len(recorded),
            facts_version=facts.version,
            lifecycle_version=facts.lifecycle_version,
            problems=problems,
        )
