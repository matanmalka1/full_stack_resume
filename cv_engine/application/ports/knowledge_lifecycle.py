"""Persistence boundary for fact events and the durable Knowledge journal."""

from __future__ import annotations

from typing import Any, Protocol

from ...domain.contracts.drafts import WorkingDraft
from ...domain.contracts.selection import SelectionManifest, SelectionPlan
from ..knowledge_mutations import KnowledgeMutation, PrepareKnowledgeMutation
from .transactions import ReadTransaction, WriteTransaction


class KnowledgeLifecycleStore(Protocol):
    """The atomic database half of the cross-store Knowledge lifecycle."""

    def prepare_mutation(
        self,
        tx: WriteTransaction,
        request: PrepareKnowledgeMutation,
        *,
        prepared_at: str | None = ...,
    ) -> KnowledgeMutation: ...

    def mutation(self, tx: ReadTransaction, mutation_id: str) -> KnowledgeMutation: ...

    def prepared_mutations(self, tx: ReadTransaction) -> list[KnowledgeMutation]: ...

    def quarantined_mutations(self, tx: ReadTransaction) -> list[KnowledgeMutation]: ...

    def commit_mutation(
        self,
        tx: WriteTransaction,
        mutation_id: str,
        *,
        committed_at: str | None = ...,
    ) -> KnowledgeMutation: ...

    def quarantine_mutation(
        self,
        tx: WriteTransaction,
        mutation_id: str,
        reason: str,
        *,
        quarantined_at: str | None = ...,
    ) -> KnowledgeMutation: ...

    def record_fact_event(self, tx: WriteTransaction, **event: Any) -> str: ...

    def fact_event(self, tx: ReadTransaction, event_id: str) -> dict[str, Any] | None: ...

    def fact_events(
        self, tx: ReadTransaction, fact_id: str | None = ...
    ) -> list[dict[str, Any]]: ...

    def latest_fact_statuses(self, tx: ReadTransaction) -> dict[str, str]: ...

    def get_analysis(self, tx: ReadTransaction, analysis_id: str) -> dict[str, Any]: ...

    def active_working_draft(self, tx: ReadTransaction, application_id: str) -> WorkingDraft: ...

    def create_selection_plan(
        self,
        tx: WriteTransaction,
        application_id: str,
        job_analysis_id: str,
        plan: SelectionManifest,
        *,
        candidate_context_version: str,
        candidate_context_hash: str,
        profile_version: str,
        selection_policy_version: str,
        track_emphasis_dependencies: dict[str, str],
        plan_id: str | None = ...,
        created_at: str | None = ...,
    ) -> SelectionPlan: ...

    def selection_plan(self, tx: ReadTransaction, selection_plan_id: str) -> SelectionPlan: ...
