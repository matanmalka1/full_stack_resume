from __future__ import annotations

from sqlalchemy import select

from ...application.errors import UnknownRecord
from ...application.ports.submission import SubmissionContext
from ...application.ports.transactions import ReadTransaction
from .analysis_sql import _selection_plan_record
from .connection import SqlAlchemyTransactionManager
from .drafts_sql import _approved_revision
from .tables import applications, job_analyses, job_snapshots, selection_plans


class SqlAlchemySubmissionContextReader:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def load(
        self, tx: ReadTransaction, application_id: str, revision_id: str | None
    ) -> SubmissionContext:
        connection = self._transactions.connection_for(tx)
        application = (
            connection.execute(select(applications).where(applications.c.id == application_id))
            .mappings()
            .one_or_none()
        )
        if application is None:
            raise UnknownRecord(application_id)
        revision = _approved_revision(connection, revision_id) if revision_id is not None else None
        snapshot_id = connection.execute(
            select(job_snapshots.c.id)
            .where(job_snapshots.c.application_id == application_id)
            .order_by(job_snapshots.c.version_number.desc())
            .limit(1)
        ).scalar_one_or_none()
        analysis_id = connection.execute(
            select(job_analyses.c.id)
            .where(job_analyses.c.application_id == application_id)
            .order_by(job_analyses.c.version_number.desc())
            .limit(1)
        ).scalar_one_or_none()
        plan_row = (
            connection.execute(
                select(selection_plans)
                .where(selection_plans.c.application_id == application_id)
                .order_by(selection_plans.c.version_number.desc())
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
        plan_id = _selection_plan_record(plan_row).id if plan_row is not None else None
        return SubmissionContext(dict(application), revision, snapshot_id, analysis_id, plan_id)
