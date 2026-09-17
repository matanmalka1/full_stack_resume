from __future__ import annotations

from sqlalchemy import select

from ...application.errors import UnknownRecord
from ...application.ports.draft_history import DraftHistoryApplication
from ...application.ports.transactions import ReadTransaction
from .connection import SqlAlchemyTransactionManager
from .tables import applications


class SqlAlchemyDraftHistoryApplicationReader:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def history_application(
        self, tx: ReadTransaction, application_id: str
    ) -> DraftHistoryApplication:
        row = (
            self._transactions.connection_for(tx)
            .execute(
                select(
                    applications.c.company, applications.c.target_role, applications.c.deleted_at
                ).where(applications.c.id == application_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(application_id)
        return DraftHistoryApplication(row["company"], row["target_role"], row["deleted_at"])
