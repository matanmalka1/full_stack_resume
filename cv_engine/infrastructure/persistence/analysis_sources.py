"""Only the persisted sources consumed by analysis and selection preparation/checks."""

from __future__ import annotations

from sqlalchemy import select

from ...application.errors import UnknownRecord
from ...application.ports.analysis_plans import (
    ActiveSelectionSource,
    AnalysisSnapshotSource,
    SelectionSource,
)
from ...application.ports.transactions import ReadTransaction
from ...domain.contracts.taxonomy import Emphasis
from .analysis_sql import _analysis_record
from .connection import SqlAlchemyTransactionManager
from .tables import (
    applications,
    job_analyses,
    job_snapshots,
    knowledge_mutation_journal,
    selection_plans,
)


class SqlAlchemyAnalysisSelectionSourceReader:
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

    def analysis_source(self, tx: ReadTransaction, job_snapshot_id: str) -> AnalysisSnapshotSource:
        connection = self._transactions.connection_for(tx)
        row = (
            connection.execute(
                select(
                    job_snapshots.c.application_id,
                    job_snapshots.c.id,
                    job_snapshots.c.payload_path,
                    job_snapshots.c.source_hash,
                    job_snapshots.c.normalized_hash,
                    applications.c.deleted_at,
                )
                .join(applications)
                .where(job_snapshots.c.id == job_snapshot_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(f"unknown job snapshot: {job_snapshot_id}")
        active_id = connection.execute(
            select(job_snapshots.c.id)
            .where(job_snapshots.c.application_id == row["application_id"])
            .order_by(job_snapshots.c.version_number.desc())
            .limit(1)
        ).scalar_one()
        return AnalysisSnapshotSource(
            application_id=row["application_id"],
            job_snapshot_id=row["id"],
            payload_path=row["payload_path"],
            source_hash=row["source_hash"],
            normalized_hash=row["normalized_hash"],
            active_snapshot_id=active_id,
            deleted_at=row["deleted_at"],
        )

    def selection_source(self, tx: ReadTransaction, job_analysis_id: str) -> SelectionSource:
        connection = self._transactions.connection_for(tx)
        row = (
            connection.execute(
                select(
                    job_analyses.c.id,
                    job_analyses.c.application_id,
                    job_analyses.c.job_snapshot_id,
                    job_analyses.c.structured_json,
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
        active_snapshot = connection.execute(
            select(job_snapshots.c.id)
            .where(job_snapshots.c.application_id == row["application_id"])
            .order_by(job_snapshots.c.version_number.desc())
            .limit(1)
        ).scalar_one()
        active_analysis = connection.execute(
            select(job_analyses.c.id)
            .where(job_analyses.c.application_id == row["application_id"])
            .order_by(job_analyses.c.version_number.desc())
            .limit(1)
        ).scalar_one_or_none()
        plan_row = (
            connection.execute(
                select(
                    selection_plans.c.id,
                    selection_plans.c.job_analysis_id,
                    selection_plans.c.plan_json["emphasis"].astext.label("emphasis"),
                    selection_plans.c.plan_json["emphasis_override"].astext.label(
                        "emphasis_override"
                    ),
                )
                .where(selection_plans.c.application_id == row["application_id"])
                .order_by(selection_plans.c.version_number.desc())
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
        active_plan = (
            ActiveSelectionSource(
                id=plan_row["id"],
                emphasis=Emphasis(plan_row["emphasis"]),
                emphasis_override=Emphasis(plan_row["emphasis_override"])
                if plan_row["emphasis_override"] is not None
                else None,
            )
            if plan_row is not None and plan_row["job_analysis_id"] == job_analysis_id
            else None
        )
        return SelectionSource(
            application_id=row["application_id"],
            job_analysis_id=job_analysis_id,
            job_snapshot_id=row["job_snapshot_id"],
            analysis=_analysis_record(row)["analysis"],
            active_analysis_id=active_analysis,
            active_snapshot_id=active_snapshot,
            active_plan=active_plan,
            deleted_at=row["deleted_at"],
        )
