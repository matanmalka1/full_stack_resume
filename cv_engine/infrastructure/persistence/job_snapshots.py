from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select

from ...application.errors import UnknownRecord
from ...application.ports.transactions import ReadTransaction, WriteTransaction
from .connection import SqlAlchemyTransactionManager
from .tables import applications, job_snapshots


class SqlAlchemyJobSnapshotStore:
    """Immutable source snapshots and the intake projections derived from them."""

    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def duplicate_application_inputs(self, tx: ReadTransaction) -> list[dict[str, Any]]:
        rows = (
            self._transactions.connection_for(tx)
            .execute(
                select(
                    applications.c.id.label("application_id"),
                    applications.c.company,
                    applications.c.target_role,
                    job_snapshots.c.source_url,
                    job_snapshots.c.normalized_hash,
                )
                .select_from(
                    applications.join(
                        job_snapshots,
                        job_snapshots.c.application_id == applications.c.id,
                    )
                )
                .where(applications.c.deleted_at.is_(None))
                .order_by(
                    applications.c.created_at,
                    applications.c.id,
                    job_snapshots.c.version_number,
                )
            )
            .mappings()
            .all()
        )
        return [dict(row) for row in rows]

    def snapshot_for_source_hash(
        self, tx: ReadTransaction, application_id: str, source_hash: str
    ) -> dict[str, Any] | None:
        row = (
            self._transactions.connection_for(tx)
            .execute(
                select(job_snapshots).where(
                    job_snapshots.c.application_id == application_id,
                    job_snapshots.c.source_hash == source_hash,
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else dict(row)

    def insert_initial_snapshot(
        self,
        tx: WriteTransaction,
        *,
        snapshot_id: str,
        application_id: str,
        payload_path: str,
        source_hash: str,
        normalized_hash: str,
        source_url: str | None,
        source_metadata: dict[str, Any],
        captured_at: str,
    ) -> None:
        self._insert(
            tx,
            snapshot_id=snapshot_id,
            application_id=application_id,
            version_number=1,
            payload_path=payload_path,
            source_hash=source_hash,
            normalized_hash=normalized_hash,
            source_url=source_url,
            source_metadata=source_metadata,
            captured_at=captured_at,
        )

    def insert_next_snapshot(
        self,
        tx: WriteTransaction,
        *,
        snapshot_id: str,
        application_id: str,
        payload_path: str,
        source_hash: str,
        normalized_hash: str,
        source_url: str | None,
        source_metadata: dict[str, Any],
        captured_at: str,
    ) -> None:
        connection = self._transactions.connection_for(tx, access="write")
        prior = (
            connection.execute(
                select(job_snapshots.c.id, job_snapshots.c.version_number)
                .where(job_snapshots.c.application_id == application_id)
                .order_by(job_snapshots.c.version_number.desc())
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
        if prior is None:
            raise UnknownRecord(application_id)
        self._insert(
            tx,
            snapshot_id=snapshot_id,
            application_id=application_id,
            version_number=prior["version_number"] + 1,
            payload_path=payload_path,
            source_hash=source_hash,
            normalized_hash=normalized_hash,
            source_url=source_url,
            source_metadata=source_metadata,
            captured_at=captured_at,
        )

    def _insert(
        self,
        tx: WriteTransaction,
        *,
        snapshot_id: str,
        application_id: str,
        version_number: int,
        payload_path: str,
        source_hash: str,
        normalized_hash: str,
        source_url: str | None,
        source_metadata: dict[str, Any],
        captured_at: str,
    ) -> None:
        self._transactions.connection_for(tx, access="write").execute(
            insert(job_snapshots).values(
                id=snapshot_id,
                application_id=application_id,
                version_number=version_number,
                payload_path=payload_path,
                normalized_hash=normalized_hash,
                source_url=source_url,
                captured_at=captured_at,
                source_metadata_json=source_metadata,
                source_hash=source_hash,
            )
        )
