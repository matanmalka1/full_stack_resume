from __future__ import annotations

from sqlalchemy import select

from ...application.errors import UnknownRecord
from ...application.operations import PersistedOperation
from ...application.ports.drafts import DraftGenerationSources
from ...application.ports.transactions import ReadTransaction
from ...domain.contracts.drafts import WorkingDraft
from .analysis_sql import _analysis_record, _selection_plan_record
from .connection import SqlAlchemyTransactionManager
from .drafts_sql import _working_draft
from .tables import job_analyses, job_snapshots, knowledge_mutation_journal, selection_plans


class SqlAlchemyDraftOperationSourceReader:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def generation_sources(
        self, tx: ReadTransaction, operation: PersistedOperation
    ) -> DraftGenerationSources:
        connection = self._transactions.connection_for(tx)
        frozen = operation.sources
        snapshot = (
            connection.execute(
                select(
                    job_snapshots.c.application_id,
                    job_snapshots.c.source_hash,
                ).where(job_snapshots.c.id == frozen.job_snapshot_id)
            )
            .mappings()
            .one_or_none()
        )
        analysis = (
            connection.execute(
                select(
                    job_analyses.c.id,
                    job_analyses.c.application_id,
                    job_analyses.c.job_snapshot_id,
                    job_analyses.c.structured_json,
                ).where(job_analyses.c.id == frozen.job_analysis_id)
            )
            .mappings()
            .one_or_none()
        )
        plan = (
            connection.execute(
                select(selection_plans).where(selection_plans.c.id == frozen.selection_plan_id)
            )
            .mappings()
            .one_or_none()
        )
        active_snapshot = connection.execute(
            select(job_snapshots.c.id)
            .where(job_snapshots.c.application_id == operation.application_id)
            .order_by(job_snapshots.c.version_number.desc())
            .limit(1)
        ).scalar_one_or_none()
        active_analysis = connection.execute(
            select(job_analyses.c.id)
            .where(job_analyses.c.application_id == operation.application_id)
            .order_by(job_analyses.c.version_number.desc())
            .limit(1)
        ).scalar_one_or_none()
        active_plan = (
            connection.execute(
                select(selection_plans)
                .where(selection_plans.c.application_id == operation.application_id)
                .order_by(selection_plans.c.version_number.desc())
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
        if (
            snapshot is None
            or analysis is None
            or plan is None
            or active_snapshot is None
            or active_analysis is None
            or active_plan is None
        ):
            raise UnknownRecord("draft activation source missing")
        replaced = (
            _working_draft(connection, frozen.working_draft_id)
            if frozen.working_draft_id is not None
            else None
        )
        return DraftGenerationSources(
            dict(snapshot),
            _analysis_record(analysis),
            _selection_plan_record(plan),
            active_snapshot,
            active_analysis,
            _selection_plan_record(active_plan).id,
            replaced,
        )

    def regeneration_source(self, tx: ReadTransaction, working_draft_id: str) -> WorkingDraft:
        return _working_draft(self._transactions.connection_for(tx), working_draft_id)

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
