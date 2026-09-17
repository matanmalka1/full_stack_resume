"""Minimal SQL projection for explicit draft validation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.engine import Connection

from ...application.chain import DraftChainSources
from ...application.errors import UnknownRecord
from ...application.ports.draft_validation import DraftValidationContext
from ...application.ports.transactions import ReadTransaction
from ...domain.contracts.drafts import DraftDocument, WorkingDraft
from .analysis_sql import _analysis_record, _selection_plan_record
from .connection import SqlAlchemyTransactionManager
from .tables import applications, job_analyses, job_snapshots, selection_plans


def _draft_chain_sources(
    connection: Connection, application_id: str, draft: DraftDocument
) -> DraftChainSources:
    record = None
    snapshot = None
    latest_snapshot_id = None
    history = ()
    if draft.application_id == application_id and draft.job_analysis_id is not None:
        row = (
            connection.execute(
                select(
                    job_analyses.c.id,
                    job_analyses.c.application_id,
                    job_analyses.c.job_snapshot_id,
                    job_analyses.c.version_number,
                    job_analyses.c.structured_json,
                ).where(job_analyses.c.id == draft.job_analysis_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is not None:
            record = _analysis_record(row)
            owner = connection.execute(
                select(job_snapshots.c.application_id).where(
                    job_snapshots.c.id == draft.job_snapshot_id
                )
            ).scalar_one_or_none()
            if owner is not None:
                snapshot = {"application_id": owner}
            if row["application_id"] == application_id:
                latest_snapshot_id = connection.execute(
                    select(job_snapshots.c.id)
                    .where(job_snapshots.c.application_id == application_id)
                    .order_by(job_snapshots.c.version_number.desc())
                    .limit(1)
                ).scalar_one_or_none()
                rows = (
                    connection.execute(
                        select(
                            job_analyses.c.id,
                            job_analyses.c.version_number,
                            job_analyses.c.structured_json,
                        )
                        .where(job_analyses.c.application_id == application_id)
                        .order_by(job_analyses.c.version_number)
                    )
                    .mappings()
                    .all()
                )
                history = tuple(_analysis_record(item) for item in rows)
    return DraftChainSources(record, snapshot, latest_snapshot_id, history)


class SqlAlchemyDraftValidationSourceReader:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def validation_context(
        self, tx: ReadTransaction, working: WorkingDraft
    ) -> DraftValidationContext:
        connection = self._transactions.connection_for(tx)
        application = (
            connection.execute(
                select(applications.c.deleted_at).where(applications.c.id == working.application_id)
            )
            .mappings()
            .one_or_none()
        )
        if application is None:
            raise UnknownRecord(working.application_id)
        plan = (
            connection.execute(
                select(selection_plans).where(selection_plans.c.id == working.selection_plan_id)
            )
            .mappings()
            .one_or_none()
        )
        if plan is None:
            raise UnknownRecord(f"no selection plan {working.selection_plan_id}")
        return DraftValidationContext(
            application["deleted_at"],
            _draft_chain_sources(connection, working.application_id, working.source),
            _selection_plan_record(plan),
        )
