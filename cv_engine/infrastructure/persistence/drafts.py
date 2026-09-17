from __future__ import annotations

from ...domain.contracts.drafts import DraftDocument, WorkingDraft
from ...domain.contracts.records import ApprovedRevision
from .base import SqlAlchemyRepositoryBase
from .drafts_sql import (
    _active_working_draft,
    _approved_revision,
    _approved_revisions,
    _create_working_draft,
    _latest_approved_revision,
    _update_draft_source,
    _working_draft,
)


class SqlAlchemyDraftRepository(SqlAlchemyRepositoryBase):
    """The one mutable WorkingDraft record and its optimistic edit token."""

    def create_working_draft(
        self,
        application_id: str,
        job_analysis_id: str,
        selection_plan_id: str,
        source: DraftDocument,
        *,
        parent_revision_id: str | None = None,
        working_draft_id: str | None = None,
        created_at: str | None = None,
    ) -> WorkingDraft:
        with self.transaction() as connection:
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

    def working_draft(self, working_draft_id: str) -> WorkingDraft:
        with self.read_connection() as connection:
            return _working_draft(connection, working_draft_id)

    def active_working_draft(self, application_id: str) -> WorkingDraft:
        with self.read_connection() as connection:
            return _active_working_draft(connection, application_id)

    def update_working_draft(
        self,
        working_draft_id: str,
        expected_version: int,
        source: DraftDocument,
        *,
        selection_plan_id: str | None = None,
        updated_at: str | None = None,
    ) -> WorkingDraft:
        with self.transaction() as connection:
            return _update_draft_source(
                connection,
                working_draft_id,
                expected_version,
                source,
                selection_plan_id=selection_plan_id,
                updated_at=updated_at,
            )

    def approved_revision(self, revision_id: str) -> ApprovedRevision:
        with self.read_connection() as connection:
            return _approved_revision(connection, revision_id)

    def latest_approved_revision(self, application_id: str) -> ApprovedRevision:
        with self.read_connection() as connection:
            return _latest_approved_revision(connection, application_id)

    def approved_revisions(self, application_id: str) -> list[ApprovedRevision]:
        with self.read_connection() as connection:
            return _approved_revisions(connection, application_id)
