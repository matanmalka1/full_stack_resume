"""Reads over the provider-response artifact catalog."""

from __future__ import annotations

from typing import Any

from ...application.ports.transactions import ReadTransaction
from .artifacts_sql import _artifact_version, _artifact_versions, _latest_artifact_version
from .connection import SqlAlchemyTransactionManager


class SqlAlchemyArtifactCatalog:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def latest_artifact_version(
        self,
        tx: ReadTransaction,
        application_id: str,
        artifact_type: str,
        lifecycle_status: str | None = None,
    ) -> dict[str, Any]:
        connection = self._transactions.connection_for(tx)
        return _latest_artifact_version(connection, application_id, artifact_type, lifecycle_status)

    def artifact_versions(self, tx: ReadTransaction, application_id: str) -> list[dict[str, Any]]:
        connection = self._transactions.connection_for(tx)
        return _artifact_versions(connection, application_id)

    def artifact_version(self, tx: ReadTransaction, artifact_version_id: str) -> dict[str, Any]:
        connection = self._transactions.connection_for(tx)
        return _artifact_version(connection, artifact_version_id)
