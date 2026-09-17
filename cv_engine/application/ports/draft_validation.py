"""Consistent sources consumed by an explicit draft ValidationRun."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.contracts.drafts import WorkingDraft
from ...domain.contracts.selection import SelectionPlan
from ..chain import DraftChainSources
from .transactions import ReadTransaction


@dataclass(frozen=True)
class DraftValidationContext:
    deleted_at: str | None
    chain: DraftChainSources
    plan: SelectionPlan


class DraftValidationSourceReader(Protocol):
    """Atomic read of the application disposition, lineage and named plan."""

    def validation_context(
        self, tx: ReadTransaction, working: WorkingDraft
    ) -> DraftValidationContext: ...
