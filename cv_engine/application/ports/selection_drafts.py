"""The draft persistence consumed by atomic selection changes only."""

from __future__ import annotations

from typing import Protocol

from ...domain.contracts.drafts import DraftDocument, WorkingDraft
from .transactions import ReadTransaction, WriteTransaction


class SelectionDraftStore(Protocol):
    def working_draft(self, tx: ReadTransaction, working_draft_id: str) -> WorkingDraft: ...

    def update_selection(
        self,
        tx: WriteTransaction,
        working_draft_id: str,
        expected_version: int,
        source: DraftDocument,
        selection_plan_id: str,
    ) -> WorkingDraft: ...
