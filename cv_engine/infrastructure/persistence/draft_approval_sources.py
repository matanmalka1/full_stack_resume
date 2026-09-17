from __future__ import annotations

from sqlalchemy import select

from ...application.commands import ApprovalResult
from ...application.errors import UnknownRecord
from ...application.ports.draft_approval import ApprovalReplay, DraftApprovalContext
from ...application.ports.transactions import ReadTransaction
from ...domain.contracts.drafts import WorkingDraft
from .analysis_sql import _selection_plan_record
from .artifacts_sql import (
    _artifact_version_for_revision,
    _decision_for_revision,
    _validation_lineage,
    _validation_report,
)
from .connection import SqlAlchemyTransactionManager
from .draft_validation_sources import _draft_chain_sources
from .drafts_sql import _approved_revision
from .tables import applications, knowledge_mutation_journal, selection_plans


class SqlAlchemyDraftApprovalSourceReader:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def approval_context(
        self, tx: ReadTransaction, working: WorkingDraft, validation_run_id: str
    ) -> DraftApprovalContext:
        connection = self._transactions.connection_for(tx)
        application = (
            connection.execute(
                select(
                    applications.c.company, applications.c.target_role, applications.c.deleted_at
                ).where(applications.c.id == working.application_id)
            )
            .mappings()
            .one_or_none()
        )
        if application is None:
            raise UnknownRecord(working.application_id)
        quarantine = connection.execute(
            select(knowledge_mutation_journal.c.id)
            .where(knowledge_mutation_journal.c.state == "QUARANTINED")
            .order_by(knowledge_mutation_journal.c.quarantined_at, knowledge_mutation_journal.c.id)
            .limit(1)
        ).scalar_one_or_none()
        plan = (
            connection.execute(
                select(selection_plans).where(selection_plans.c.id == working.selection_plan_id)
            )
            .mappings()
            .one_or_none()
        )
        try:
            lineage = _validation_lineage(connection, validation_run_id)
            report = _validation_report(connection, validation_run_id)
        except UnknownRecord:
            lineage = None
            report = None
        return DraftApprovalContext(
            application["company"],
            application["target_role"],
            application["deleted_at"],
            quarantine,
            _draft_chain_sources(connection, working.application_id, working.source),
            _selection_plan_record(plan) if plan is not None else None,
            lineage,
            report,
        )

    def approval_replay(self, tx: ReadTransaction, revision_id: str) -> ApprovalReplay:
        connection = self._transactions.connection_for(tx)
        try:
            revision = _approved_revision(connection, revision_id)
        except UnknownRecord:
            return ApprovalReplay(None, None)
        try:
            markdown = _artifact_version_for_revision(
                connection, revision_id, "resume_markdown", "approved"
            )
            manifest = _artifact_version_for_revision(
                connection, revision_id, "claim_manifest", "approved"
            )
            decision = _decision_for_revision(connection, revision_id)
        except UnknownRecord:
            return ApprovalReplay(None, revision.decision_provenance)
        return ApprovalReplay(
            ApprovalResult(
                application_id=revision.application_id,
                revision_id=revision.id,
                version=revision.version_number,
                markdown_artifact_version_id=markdown["id"],
                manifest_artifact_version_id=manifest["id"],
                decision_record_id=decision["id"],
            ),
            revision.decision_provenance,
        )
