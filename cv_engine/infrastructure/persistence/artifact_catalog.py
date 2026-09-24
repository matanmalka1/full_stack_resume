from __future__ import annotations

from typing import Any

from ...application.ports.transactions import ReadTransaction, WriteTransaction
from .artifacts_sql import (
    _artifact_version,
    _artifact_version_for_revision,
    _artifact_versions,
    _latest_artifact_version,
    _register_artifact_version,
)
from .connection import SqlAlchemyTransactionManager


class SqlAlchemyArtifactCatalog:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def register_artifact_version(
        self,
        tx: WriteTransaction,
        application_id: str,
        artifact_type: str,
        logical_name: str,
        path: str,
        content_hash: str,
        lifecycle_status: str,
        *,
        revision_id: str | None = None,
        job_snapshot_id: str | None = None,
        track: str | None = None,
        profile: str | None = None,
        emphasis: str | None = None,
        facts_version: str | None = None,
        metadata: dict[str, Any] | None = None,
        artifact_version_id: str | None = None,
    ) -> str:
        connection = self._transactions.connection_for(tx, access="write")
        return _register_artifact_version(
            connection,
            application_id,
            artifact_type,
            logical_name,
            path,
            content_hash,
            lifecycle_status,
            revision_id=revision_id,
            job_snapshot_id=job_snapshot_id,
            track=track,
            profile=profile,
            emphasis=emphasis,
            facts_version=facts_version,
            metadata=metadata,
            artifact_version_id=artifact_version_id,
        )

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

    def artifact_version_for_revision(
        self,
        tx: ReadTransaction,
        revision_id: str,
        artifact_type: str,
        lifecycle_status: str | None = None,
    ) -> dict[str, Any]:
        connection = self._transactions.connection_for(tx)
        return _artifact_version_for_revision(
            connection, revision_id, artifact_type, lifecycle_status
        )
