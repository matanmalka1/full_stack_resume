"""Transaction-token draft read/update for the selection-change boundary."""

from __future__ import annotations

from sqlalchemy import select

from ...application.ports.transactions import ReadTransaction, WriteTransaction
from ...domain.contracts.drafts import DraftDocument, WorkingDraft
from .connection import SqlAlchemyTransactionManager
from .draft_selection_sql import _record, _update_working_draft
from .tables import working_drafts


class SqlAlchemySelectionDraftStore:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def working_draft(self, tx: ReadTransaction, working_draft_id: str) -> WorkingDraft:
        row = (
            self._transactions.connection_for(tx)
            .execute(select(working_drafts).where(working_drafts.c.id == working_draft_id))
            .mappings()
            .one_or_none()
        )
        return _record(row)

    def update_selection(
        self,
        tx: WriteTransaction,
        working_draft_id: str,
        expected_version: int,
        source: DraftDocument,
        selection_plan_id: str,
    ) -> WorkingDraft:
        return _update_working_draft(
            self._transactions.connection_for(tx, access="write"),
            working_draft_id,
            expected_version,
            source,
            selection_plan_id=selection_plan_id,
        )
