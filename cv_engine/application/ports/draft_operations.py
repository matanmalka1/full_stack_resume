"""Frozen sources for generation and optimistic regeneration activation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.contracts.drafts import WorkingDraft
from ...domain.contracts.selection import SelectionPlan
from ..operations import PersistedOperation
from .transactions import ReadTransaction


@dataclass(frozen=True)
class DraftGenerationSources:
    snapshot: dict
    analysis: dict
    plan: SelectionPlan
    active_snapshot_id: str
    active_analysis_id: str
    active_plan_id: str
    replaced: WorkingDraft | None


class DraftOperationSourceReader(Protocol):
    def generation_sources(
        self, tx: ReadTransaction, operation: PersistedOperation
    ) -> DraftGenerationSources: ...

    def regeneration_source(self, tx: ReadTransaction, working_draft_id: str) -> WorkingDraft: ...

    def knowledge_is_prepared(self, tx: ReadTransaction) -> bool: ...
