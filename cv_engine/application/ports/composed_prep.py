"""CV-preparation composed repository views: identity through Ready proof.

Base order is significant: Python linearizes it, and a base inserted out of
order raises `TypeError` at import rather than at first use.
"""

from __future__ import annotations

from typing import Any, Protocol, Self

from ...domain.contracts.drafts import DraftDocument, WorkingDraft
from ...domain.contracts.records import ApprovedRevision, AuditRecord
from ..knowledge_mutations import KnowledgeMutation
from .repositories import (
    ApplicationStore,
    ArtifactRegistry,
    JobStore,
    UnitOfWork,
    WorkingDraftReader,
)


class PreparationRepository(ApplicationStore, JobStore, Protocol):
    """Application identity plus immutable snapshot/analysis preparation."""

    def insert_audit(self, record: AuditRecord) -> None: ...

    def unit_of_work(self) -> UnitOfWork: ...

    def bind(self, uow: UnitOfWork) -> Self: ...


class DraftRepository(ApplicationStore, JobStore, ArtifactRegistry, WorkingDraftReader, Protocol):
    """The records needed to validate, approve, render, and qualify a draft."""

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
    ) -> WorkingDraft: ...

    def working_draft(self, working_draft_id: str) -> WorkingDraft: ...

    def replace_active_working_draft(
        self,
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

    def update_working_draft(
        self,
        working_draft_id: str,
        expected_version: int,
        source: DraftDocument,
        *,
        selection_plan_id: str | None = None,
        updated_at: str | None = None,
    ) -> WorkingDraft: ...

    def deactivate_working_draft(
        self,
        working_draft_id: str,
        expected_version: int,
        *,
        updated_at: str | None = None,
    ) -> WorkingDraft: ...

    def create_approved_revision(
        self,
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

    def approved_revision(self, revision_id: str) -> ApprovedRevision: ...

    def latest_approved_revision(self, application_id: str) -> ApprovedRevision: ...

    def decision_for_revision(self, revision_id: str) -> dict[str, Any]: ...

    def insert_audit(self, record: AuditRecord) -> None: ...

    def unit_of_work(self) -> UnitOfWork: ...

    def bind(self, uow: UnitOfWork) -> Self: ...

    def quarantined_knowledge_mutations(self) -> list[KnowledgeMutation]: ...


class ReadinessRepository(DraftRepository, Protocol):
    """Draft lineage plus the database integrity proof required for Ready."""

    def integrity_check(self) -> list[str]: ...

    def artifact_inventory(self) -> list[dict[str, Any]]: ...
