from __future__ import annotations

from sqlalchemy import select

from ...application.chain import DraftChainSources
from ...application.errors import UnknownRecord
from ...application.ports.transactions import ReadTransaction
from ...domain.contracts.drafts import DraftDocument
from .analysis_sql import _analysis_record
from .connection import SqlAlchemyTransactionManager
from .draft_validation_sources import _draft_chain_sources
from .tables import applications, job_analyses, job_snapshots


class SqlAlchemyDraftAuthoringSourceReader:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def analysis_source(self, tx: ReadTransaction, analysis_id: str) -> dict:
        row = (
            self._transactions.connection_for(tx)
            .execute(
                select(
                    job_analyses.c.id,
                    job_analyses.c.application_id,
                    job_analyses.c.job_snapshot_id,
                    job_analyses.c.version_number,
                    job_analyses.c.structured_json,
                ).where(job_analyses.c.id == analysis_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(f"no job analysis {analysis_id}")
        return _analysis_record(row)

    def active_snapshot_id(self, tx: ReadTransaction, application_id: str) -> str:
        result = (
            self._transactions.connection_for(tx)
            .execute(
                select(job_snapshots.c.id)
                .where(job_snapshots.c.application_id == application_id)
                .order_by(job_snapshots.c.version_number.desc())
                .limit(1)
            )
            .scalar_one_or_none()
        )
        if result is None:
            raise UnknownRecord(f"no snapshot for application {application_id}")
        return result

    def snapshot_source(self, tx: ReadTransaction, snapshot_id: str) -> dict:
        row = (
            self._transactions.connection_for(tx)
            .execute(
                select(
                    job_snapshots.c.id,
                    job_snapshots.c.application_id,
                    job_snapshots.c.source_hash,
                    job_snapshots.c.payload_path,
                ).where(job_snapshots.c.id == snapshot_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(f"no snapshot {snapshot_id}")
        return dict(row)

    def deleted_at(self, tx: ReadTransaction, application_id: str) -> str | None:
        row = (
            self._transactions.connection_for(tx)
            .execute(select(applications.c.deleted_at).where(applications.c.id == application_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(application_id)
        return row["deleted_at"]

    def chain_source(
        self, tx: ReadTransaction, application_id: str, draft: DraftDocument
    ) -> DraftChainSources:
        return _draft_chain_sources(self._transactions.connection_for(tx), application_id, draft)
