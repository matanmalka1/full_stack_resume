from __future__ import annotations

from typing import Any

from ...application.ports.transactions import ReadTransaction, WriteTransaction
from ...domain.contracts.records import DecisionRecord
from .artifacts_sql import (
    _decision_for_artifact_version,
    _decision_for_revision,
    _insert_decision,
    _latest_decision,
)
from .connection import SqlAlchemyTransactionManager


class SqlAlchemyDecisionRepository:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def insert_decision(self, tx: WriteTransaction, record: DecisionRecord) -> None:
        connection = self._transactions.connection_for(tx, access="write")
        return _insert_decision(connection, record)

    def latest_decision(self, tx: ReadTransaction, application_id: str) -> dict[str, Any]:
        connection = self._transactions.connection_for(tx)
        return _latest_decision(connection, application_id)

    def decision_for_artifact_version(
        self, tx: ReadTransaction, artifact_version_id: str
    ) -> dict[str, Any]:
        connection = self._transactions.connection_for(tx)
        return _decision_for_artifact_version(connection, artifact_version_id)

    def decision_for_revision(self, tx: ReadTransaction, revision_id: str) -> dict[str, Any]:
        connection = self._transactions.connection_for(tx)
        return _decision_for_revision(connection, revision_id)
