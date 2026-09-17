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

    def update_working_draft(
        self,
        working_draft_id: str,
        expected_version: int,
        source: DraftDocument,
        *,
        selection_plan_id: str | None = None,
        updated_at: str | None = None,
    ) -> WorkingDraft: ...

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
