from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update

from ...application.errors import StateConflict, UnknownRecord
from ...application.ports.transactions import ReadTransaction, WriteTransaction
from .connection import SqlAlchemyTransactionManager
from .tables import applications


class SqlAlchemyApplicationStore:
    """Application identity and mutable intake fields; no transaction ownership."""

    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def insert_application(
        self,
        tx: WriteTransaction,
        *,
        application_id: str,
        company: str,
        target_role: str,
        notes: str,
        created_at: str,
    ) -> None:
        self._transactions.connection_for(tx, access="write").execute(
            insert(applications).values(
                id=application_id,
                company=company.strip(),
                target_role=target_role.strip(),
                current_status="saved",
                notes=notes,
                created_at=created_at,
                updated_at=created_at,
            )
        )

    def get_application(self, tx: ReadTransaction, application_id: str) -> dict[str, Any]:
        row = (
            self._transactions.connection_for(tx)
            .execute(select(applications).where(applications.c.id == application_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(application_id)
        return dict(row)

    def update_application_notes(
        self,
        tx: WriteTransaction,
        application_id: str,
        notes: str,
        expected_notes: str,
        *,
        updated_at: str,
    ) -> dict[str, Any]:
        connection = self._transactions.connection_for(tx, access="write")
        result = connection.execute(
            update(applications)
            .where(
                applications.c.id == application_id,
                applications.c.notes == expected_notes,
            )
            .values(notes=notes, updated_at=updated_at)
        )
        if result.rowcount != 1:
            exists = connection.execute(
                select(applications.c.id).where(applications.c.id == application_id)
            ).scalar_one_or_none()
            if exists is None:
                raise UnknownRecord(application_id)
            raise StateConflict("application notes changed before commit")
        row = (
            connection.execute(select(applications).where(applications.c.id == application_id))
            .mappings()
            .one()
        )
        return dict(row)
