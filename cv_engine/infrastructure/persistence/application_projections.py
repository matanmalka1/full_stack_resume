from __future__ import annotations

from typing import Any

from sqlalchemy import case, select

from ...application.errors import UnknownRecord
from ...application.operations import (
    MATCHING_CONTEXT_OPERATION_TYPES,
    OperationView,
    as_operation_view,
)
from ...application.ports.transactions import ReadTransaction
from .analysis_sql import _analysis_record
from .base import json_text_record
from .connection import SqlAlchemyTransactionManager
from .operation_sql import _operation_record
from .tables import (
    applications,
    audit_records,
    job_analyses,
    job_snapshots,
    operations,
    recruitment_events,
    submissions,
)


class SqlAlchemyApplicationProjectionReader:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def _connection(self, tx: ReadTransaction):
        return self._transactions.connection_for(tx)

    @staticmethod
    def _application_projection():
        source_url = (
            select(job_snapshots.c.source_url)
            .where(job_snapshots.c.application_id == applications.c.id)
            .order_by(job_snapshots.c.version_number.desc())
            .limit(1)
            .scalar_subquery()
        )
        return select(*applications.c, source_url.label("source_url"))

    def application(self, tx: ReadTransaction, application_id: str) -> dict[str, Any]:
        row = (
            self._connection(tx)
            .execute(self._application_projection().where(applications.c.id == application_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(application_id)
        return dict(row)

    def applications(self, tx: ReadTransaction) -> list[dict[str, Any]]:
        rows = (
            self._connection(tx)
            .execute(
                self._application_projection()
                .where(applications.c.deleted_at.is_(None))
                .order_by(applications.c.created_at, applications.c.id)
            )
            .mappings()
            .all()
        )
        return [dict(row) for row in rows]

    def latest_snapshot(self, tx: ReadTransaction, application_id: str) -> dict[str, Any]:
        rows = self.snapshots(tx, application_id)
        if not rows:
            raise UnknownRecord(f"no job snapshot for application {application_id}")
        return rows[-1]

    def snapshots(self, tx: ReadTransaction, application_id: str) -> list[dict[str, Any]]:
        rows = (
            self._connection(tx)
            .execute(
                select(job_snapshots)
                .where(job_snapshots.c.application_id == application_id)
                .order_by(job_snapshots.c.version_number)
            )
            .mappings()
            .all()
        )
        return [json_text_record(row, "source_metadata_json") for row in rows]

    def analyses(self, tx: ReadTransaction, application_id: str) -> list[dict[str, Any]]:
        rows = (
            self._connection(tx)
            .execute(
                select(job_analyses)
                .where(job_analyses.c.application_id == application_id)
                .order_by(job_analyses.c.version_number)
            )
            .mappings()
            .all()
        )
        return [_analysis_record(row) for row in rows]

    def analysis(self, tx: ReadTransaction, analysis_id: str) -> dict[str, Any]:
        row = (
            self._connection(tx)
            .execute(select(job_analyses).where(job_analyses.c.id == analysis_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(f"no job analysis {analysis_id}")
        return _analysis_record(row)

    def recruitment_events(self, tx: ReadTransaction, application_id: str):
        cols = tuple(c for c in recruitment_events.c if c.name != "seq")
        rows = (
            self._connection(tx)
            .execute(
                select(*cols)
                .where(recruitment_events.c.application_id == application_id)
                .order_by(recruitment_events.c.occurred_at, recruitment_events.c.seq)
            )
            .mappings()
            .all()
        )
        return [json_text_record(row, "payload_json") for row in rows]

    def submissions(self, tx: ReadTransaction, application_id: str):
        cols = tuple(c for c in submissions.c if c.name != "seq")
        rows = (
            self._connection(tx)
            .execute(
                select(*cols)
                .where(submissions.c.application_id == application_id)
                .order_by(submissions.c.submitted_at, submissions.c.seq)
            )
            .mappings()
            .all()
        )
        return [json_text_record(row, "metadata_json") for row in rows]

    def audit_records(self, tx: ReadTransaction, application_id: str):
        cols = tuple(c for c in audit_records.c if c.name != "seq")
        rows = (
            self._connection(tx)
            .execute(
                select(*cols)
                .where(audit_records.c.application_id == application_id)
                .order_by(audit_records.c.occurred_at, audit_records.c.seq)
            )
            .mappings()
            .all()
        )
        return [json_text_record(row, "details_json") for row in rows]

    def _operation(self, tx: ReadTransaction, application_id: str, *, active: bool):
        connection = self._connection(tx)
        query = select(operations).where(operations.c.application_id == application_id)
        if active:
            query = query.where(operations.c.status.in_(("queued", "running"))).order_by(
                case((operations.c.status == "running", 0), else_=1),
                operations.c.created_at,
                operations.c.id,
            )
        else:
            query = query.order_by(operations.c.created_at.desc(), operations.c.id.desc())
        row = connection.execute(query.limit(1)).mappings().one_or_none()
        return None if row is None else as_operation_view(_operation_record(row, connection))

    def active_operation(self, tx: ReadTransaction, application_id: str) -> OperationView | None:
        return self._operation(tx, application_id, active=True)

    def latest_operation(self, tx: ReadTransaction, application_id: str) -> OperationView | None:
        return self._operation(tx, application_id, active=False)

    def has_active_matching_context_operation(
        self, tx: ReadTransaction, application_id: str
    ) -> bool:
        value = (
            self._connection(tx)
            .execute(
                select(operations.c.id)
                .where(
                    operations.c.application_id == application_id,
                    operations.c.status.in_(("queued", "running")),
                    operations.c.operation_type.in_(
                        tuple(kind.value for kind in MATCHING_CONTEXT_OPERATION_TYPES)
                    ),
                )
                .limit(1)
            )
            .scalar_one_or_none()
        )
        return value is not None
