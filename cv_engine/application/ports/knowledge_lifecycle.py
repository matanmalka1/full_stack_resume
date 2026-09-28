"""Persistence boundary for fact events and the durable Knowledge journal."""

from __future__ import annotations

from typing import Any, Protocol

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
