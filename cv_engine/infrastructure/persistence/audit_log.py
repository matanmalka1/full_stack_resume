from __future__ import annotations

from sqlalchemy import insert

from ...application.ports.transactions import WriteTransaction
from ...domain.contracts.records import AuditRecord
from .connection import SqlAlchemyTransactionManager
from .tables import audit_records


class SqlAlchemyAuditLog:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def insert_audit(self, tx: WriteTransaction, record: AuditRecord) -> None:
        self._transactions.connection_for(tx, access="write").execute(
            insert(audit_records).values(
                id=record.id,
                application_id=record.application_id,
                action=record.action,
                entity_type=record.entity_type,
                entity_id=record.entity_id,
                actor_type=record.actor_type,
                client=record.client,
                occurred_at=record.occurred_at,
                details_json=record.details,
            )
        )
