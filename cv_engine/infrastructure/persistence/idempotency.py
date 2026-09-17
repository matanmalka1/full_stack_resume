from __future__ import annotations

from typing import Any

from ...application.ports.transactions import ReadTransaction, WriteTransaction
from .connection import SqlAlchemyTransactionManager
from .idempotency_sql import (
    _claim_idempotency_receipt,
    _complete_idempotency_receipt,
    _idempotency_receipt,
)


class SqlAlchemyIdempotencyRepository:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def claim_idempotency_receipt(
        self,
        tx: WriteTransaction,
        command_type: str,
        idempotency_key: str,
        payload: dict[str, Any],
        *,
        reserved_entity_id: str,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        connection = self._transactions.connection_for(tx, access="write")
        return _claim_idempotency_receipt(
            connection,
            command_type,
            idempotency_key,
            payload,
            reserved_entity_id=reserved_entity_id,
            created_at=created_at,
        )

    def idempotency_receipt(
        self, tx: ReadTransaction, command_type: str, idempotency_key: str
    ) -> dict[str, Any] | None:
        connection = self._transactions.connection_for(tx)
        return _idempotency_receipt(connection, command_type, idempotency_key)

    def complete_idempotency_receipt(
        self,
        tx: WriteTransaction,
        receipt_id: str,
        result: dict[str, Any],
        *,
        completed_at: str | None = None,
    ) -> None:
        connection = self._transactions.connection_for(tx, access="write")
        return _complete_idempotency_receipt(
            connection, receipt_id, result, completed_at=completed_at
        )
