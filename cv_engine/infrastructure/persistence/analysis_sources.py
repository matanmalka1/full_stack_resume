"""Only the persisted sources consumed by analysis preparation and document checks."""

from __future__ import annotations

from sqlalchemy import select

from ...application.errors import UnknownRecord
from ...application.ports.analysis_plans import AnalysisContextSource, AnalysisJobTextSource
from ...application.ports.transactions import ReadTransaction
from .analysis_sql import _analysis_record
from .connection import SqlAlchemyTransactionManager
from .tables import (
    applications,
    job_analyses,
    knowledge_mutation_journal,
)


class SqlAlchemyAnalysisContextSourceReader:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def knowledge_is_prepared(self, tx: ReadTransaction) -> bool:
        return (
            self._transactions.connection_for(tx)
            .execute(
                select(knowledge_mutation_journal.c.id)
                .where(knowledge_mutation_journal.c.state == "PREPARED")
                .limit(1)
            )
            .scalar_one_or_none()
            is not None
        )

    def job_text_source(self, tx: ReadTransaction, application_id: str) -> AnalysisJobTextSource:
        row = (
            self._transactions.connection_for(tx)
            .execute(
                select(
                    applications.c.id,
                    applications.c.job_text,
                    applications.c.job_text_hash,
                    applications.c.job_normalized_hash,
                    applications.c.deleted_at,
                ).where(applications.c.id == application_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(f"unknown application: {application_id}")
        return AnalysisJobTextSource(
            application_id=row["id"],
            job_text=row["job_text"],
            job_text_hash=row["job_text_hash"],
            normalized_hash=row["job_normalized_hash"],
            deleted_at=row["deleted_at"],
        )

    def analysis_context_source(
        self, tx: ReadTransaction, job_analysis_id: str
    ) -> AnalysisContextSource:
        connection = self._transactions.connection_for(tx)
        row = (
            connection.execute(
                select(
                    job_analyses.c.id,
                    job_analyses.c.application_id,
                    job_analyses.c.job_text_hash,
                    job_analyses.c.structured_json,
                    applications.c.job_text_hash.label("current_job_text_hash"),
                    applications.c.deleted_at,
                )
                .join(applications)
                .where(job_analyses.c.id == job_analysis_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(f"unknown job analysis: {job_analysis_id}")
        active_analysis = connection.execute(
            select(job_analyses.c.id)
            .where(job_analyses.c.application_id == row["application_id"])
            .order_by(job_analyses.c.version_number.desc())
            .limit(1)
        ).scalar_one_or_none()
        return AnalysisContextSource(
            application_id=row["application_id"],
            job_analysis_id=job_analysis_id,
            job_text_hash=row["job_text_hash"],
            analysis=_analysis_record(row)["analysis"],
            active_analysis_id=active_analysis,
            current_job_text_hash=row["current_job_text_hash"],
            deleted_at=row["deleted_at"],
        )
