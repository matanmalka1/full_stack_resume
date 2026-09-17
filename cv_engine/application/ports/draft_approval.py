"""Approval's consistent source and recovery projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.contracts.drafts import WorkingDraft
from ...domain.contracts.records import ValidationRunLineage
from ...domain.contracts.selection import SelectionPlan
from ...domain.contracts.validation import ValidationReport
from ..chain import DraftChainSources
from ..commands import ApprovalResult
from .transactions import ReadTransaction


@dataclass(frozen=True)
class DraftApprovalContext:
    company: str
    target_role: str
    deleted_at: str | None
    quarantined_mutation_id: str | None
    chain: DraftChainSources
    plan: SelectionPlan | None
    validation_lineage: ValidationRunLineage | None
    validation_report: ValidationReport | None


@dataclass(frozen=True)
class ApprovalReplay:
    result: ApprovalResult | None
    provenance: dict[str, str] | None


class DraftApprovalSourceReader(Protocol):
    def approval_context(
        self, tx: ReadTransaction, working: WorkingDraft, validation_run_id: str
    ) -> DraftApprovalContext: ...

    def approval_replay(self, tx: ReadTransaction, revision_id: str) -> ApprovalReplay: ...
