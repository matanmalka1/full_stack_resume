from __future__ import annotations

from typing import Any, Protocol

from ...domain.contracts.drafts import DraftDocument, WorkingDraft
from ...domain.contracts.records import ApprovedRevision
from .transactions import ReadTransaction, WriteTransaction


class DraftLifecycleStore(Protocol):
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
    ) -> WorkingDraft: ...

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
    ) -> WorkingDraft: ...

    def working_draft(self, tx: ReadTransaction, working_draft_id: str) -> WorkingDraft: ...

    def lock_working_draft(self, tx: WriteTransaction, working_draft_id: str) -> WorkingDraft: ...

    def active_working_draft(self, tx: ReadTransaction, application_id: str) -> WorkingDraft: ...

    def update_working_draft(
        self,
        tx: WriteTransaction,
        working_draft_id: str,
        expected_version: int,
        source: DraftDocument,
        *,
        selection_plan_id: str | None = None,
        updated_at: str | None = None,
    ) -> WorkingDraft: ...

    def deactivate_working_draft(
        self,
        tx: WriteTransaction,
        working_draft_id: str,
        expected_version: int,
        *,
        updated_at: str | None = None,
    ) -> WorkingDraft: ...

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
    ) -> ApprovedRevision: ...

    def approved_revision(self, tx: ReadTransaction, revision_id: str) -> ApprovedRevision: ...

    def latest_approved_revision(
        self, tx: ReadTransaction, application_id: str
    ) -> ApprovedRevision: ...

    def approved_revisions(
        self, tx: ReadTransaction, application_id: str
    ) -> list[ApprovedRevision]: ...

    def record_event(
        self, tx: WriteTransaction, application_id: str, event_type: str, payload: dict[str, Any]
    ) -> str: ...

    def record_generation_run(self, tx: WriteTransaction, values: dict[str, Any]) -> str: ...

    def lock_application(self, tx: WriteTransaction, application_id: str) -> None: ...
