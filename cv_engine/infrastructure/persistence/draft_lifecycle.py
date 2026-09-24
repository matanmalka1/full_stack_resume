from __future__ import annotations

from ...application.ports.transactions import ReadTransaction, WriteTransaction
from ...domain.contracts.drafts import DraftDocument, WorkingDraft
from ...domain.contracts.records import ApprovedRevision
from .analysis_sql import _lock_application
from .connection import SqlAlchemyTransactionManager
from .drafts_sql import (
    _active_working_draft,
    _approved_revision,
    _approved_revisions,
    _create_approved_revision,
    _create_working_draft,
    _deactivate_working_draft,
    _latest_approved_revision,
    _lock_working_draft,
    _replace_active_working_draft,
    _update_draft_source,
    _working_draft,
)


class SqlAlchemyDraftLifecycleRepository:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def create_working_draft(
        self,
        tx: WriteTransaction,
        application_id: str,
        job_analysis_id: str,
        selection_plan_id: str,
        source: DraftDocument,
        *,
        parent_revision_id: str | None = None,
        working_draft_id: str | None = None,
        created_at: str | None = None,
    ) -> WorkingDraft:
        connection = self._transactions.connection_for(tx, access="write")
        return _create_working_draft(
            connection,
            application_id,
            job_analysis_id,
            selection_plan_id,
            source,
            parent_revision_id=parent_revision_id,
            working_draft_id=working_draft_id,
            created_at=created_at,
        )

    def replace_active_working_draft(
        self,
        tx: WriteTransaction,
        application_id: str,
        job_analysis_id: str,
        selection_plan_id: str,
        source: DraftDocument,
        *,
        parent_revision_id: str | None = None,
        updated_at: str | None = None,
        expected_working_draft_id: str | None = None,
        expected_edit_version: int | None = None,
    ) -> WorkingDraft:
        connection = self._transactions.connection_for(tx, access="write")
        return _replace_active_working_draft(
            connection,
            application_id,
            job_analysis_id,
            selection_plan_id,
            source,
            parent_revision_id=parent_revision_id,
            updated_at=updated_at,
            expected_working_draft_id=expected_working_draft_id,
            expected_edit_version=expected_edit_version,
        )

    def working_draft(self, tx: ReadTransaction, working_draft_id: str) -> WorkingDraft:
        connection = self._transactions.connection_for(tx)
        return _working_draft(connection, working_draft_id)

    def lock_working_draft(self, tx: WriteTransaction, working_draft_id: str) -> WorkingDraft:
        connection = self._transactions.connection_for(tx, access="write")
        return _lock_working_draft(connection, working_draft_id)

    def active_working_draft(self, tx: ReadTransaction, application_id: str) -> WorkingDraft:
        connection = self._transactions.connection_for(tx)
        return _active_working_draft(connection, application_id)

    def update_working_draft(
        self,
        tx: WriteTransaction,
        working_draft_id: str,
        expected_version: int,
        source: DraftDocument,
        *,
        selection_plan_id: str | None = None,
        updated_at: str | None = None,
    ) -> WorkingDraft:
        connection = self._transactions.connection_for(tx, access="write")
        return _update_draft_source(
            connection,
            working_draft_id,
            expected_version,
            source,
            selection_plan_id=selection_plan_id,
            updated_at=updated_at,
        )

    def deactivate_working_draft(
        self,
        tx: WriteTransaction,
        working_draft_id: str,
        expected_version: int,
        *,
        updated_at: str | None = None,
    ) -> WorkingDraft:
        connection = self._transactions.connection_for(tx, access="write")
        return _deactivate_working_draft(
            connection, working_draft_id, expected_version, updated_at=updated_at
        )

    def create_approved_revision(
        self,
        tx: WriteTransaction,
        application_id: str,
        revision_id: str,
        working_draft_id: str,
        validation_run_id: str,
        resume_json_reference: str,
        resume_json_hash: str,
        resume_markdown_reference: str,
        resume_markdown_hash: str,
        decision_provenance: dict[str, str],
        *,
        approved_at: str,
    ) -> ApprovedRevision:
        connection = self._transactions.connection_for(tx, access="write")
        return _create_approved_revision(
            connection,
            application_id,
            revision_id,
            working_draft_id,
            validation_run_id,
            resume_json_reference,
            resume_json_hash,
            resume_markdown_reference,
            resume_markdown_hash,
            decision_provenance,
            approved_at=approved_at,
        )

    def approved_revision(self, tx: ReadTransaction, revision_id: str) -> ApprovedRevision:
        connection = self._transactions.connection_for(tx)
        return _approved_revision(connection, revision_id)

    def latest_approved_revision(
        self, tx: ReadTransaction, application_id: str
    ) -> ApprovedRevision:
        connection = self._transactions.connection_for(tx)
        return _latest_approved_revision(connection, application_id)

    def approved_revisions(
        self, tx: ReadTransaction, application_id: str
    ) -> list[ApprovedRevision]:
        connection = self._transactions.connection_for(tx)
        return _approved_revisions(connection, application_id)

    def lock_application(self, tx: WriteTransaction, application_id: str) -> None:
        _lock_application(self._transactions.connection_for(tx, access="write"), application_id)
