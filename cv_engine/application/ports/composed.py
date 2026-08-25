"""The repository views a service or the composition root actually receives.

Each one is a union of the capability protocols in `repositories`, plus the
methods that only make sense once those capabilities are held together. The
base order is significant: Python linearizes it, and a base inserted out of
order raises `TypeError` at import rather than at first use — which is what
the whole package gets checked by every time it is imported.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Protocol, Self

from ...domain.models import (
    ApprovedRevision,
    AuditRecord,
    DraftDocument,
    SelectionManifest,
    SelectionPlan,
    WorkingDraft,
)
from ..knowledge_mutations import (
    KnowledgeMutation,
)
from ..settings import SettingsRepository
from .repositories import (
    ApplicationStore,
    ArtifactRegistry,
    FactAudit,
    JobStore,
    KnowledgeMutationRepository,
    OperationRepository,
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


class KnowledgeAuditRepository(
    FactAudit, WorkingDraftReader, KnowledgeMutationRepository, Protocol
):
    """The database audit side of the file-backed Knowledge lifecycle.

    Promoting a manual claim reads the working draft the claim was edited in,
    so the port says so instead of relying on the adapter carrying more than
    the service declared.
    """

    def get_analysis(self, analysis_id: str) -> dict[str, Any]: ...

    def create_selection_plan(
        self,
        application_id: str,
        job_analysis_id: str,
        plan: SelectionManifest,
        *,
        candidate_context_version: str,
        candidate_context_hash: str,
        profile_version: str,
        selection_policy_version: str,
        track_emphasis_dependencies: dict[str, str],
        plan_id: str | None = ...,
        created_at: str | None = ...,
    ) -> SelectionPlan: ...

    def selection_plan(self, selection_plan_id: str) -> SelectionPlan: ...


class QueryRepository(
    ApplicationStore, JobStore, ArtifactRegistry, WorkingDraftReader, OperationRepository, Protocol
):
    """Read sources used to build storage-neutral query projections."""

    def read_transaction(self) -> AbstractContextManager[Self]: ...

    def working_draft(self, working_draft_id: str) -> WorkingDraft: ...

    def approved_revisions(self, application_id: str) -> list[ApprovedRevision]: ...

    def approved_revision(self, revision_id: str) -> ApprovedRevision: ...

    def decision_for_revision(self, revision_id: str) -> dict[str, Any]: ...

    def integrity_check(self) -> list[str]: ...


class ReadinessRepository(DraftRepository, Protocol):
    """Draft lineage plus the database integrity proof required for Ready."""

    def integrity_check(self) -> list[str]: ...


class TrackingRepository(ReadinessRepository, Protocol):
    """Recruitment mutations plus the full Ready proof required by submission."""

    def insert_submission(
        self,
        submission_id: str,
        application_id: str,
        submission_type: str,
        approved_revision_id: str | None,
        artifact_version_id: str | None,
        submitted_at: str,
        metadata: dict[str, Any],
    ) -> None: ...

    def insert_recruitment_event(
        self,
        *,
        application_id: str,
        expected_current_status: str,
        target_status: str,
        event_type: str,
        reason: str,
        actor_type: str,
        client: str,
        installation_id: str,
        occurred_at: str,
        terminal_outcome: str | None,
        corrects_event_id: str | None = None,
        payload: dict[str, Any] | None = None,
        event_id: str | None = None,
    ) -> str: ...

    def insert_next_action_event(
        self,
        *,
        application_id: str,
        next_action: str | None,
        next_action_date: str | None,
        actor_type: str,
        client: str,
        installation_id: str,
        occurred_at: str,
    ) -> str: ...

    def recruitment_event(self, event_id: str) -> dict[str, Any]: ...

    def recruitment_events(self, application_id: str) -> list[dict[str, Any]]: ...

    def submissions(self, application_id: str) -> list[dict[str, Any]]: ...

    def insert_audit(self, record: AuditRecord) -> None: ...

    def audit_records(self, application_id: str) -> list[dict[str, Any]]: ...


class ApplicationRepository(
    TrackingRepository,
    KnowledgeAuditRepository,
    OperationRepository,
    SettingsRepository,
    Protocol,
):
    """Composition-root view of the adapter; services use focused ports above."""

    def unit_of_work(self) -> UnitOfWork: ...

    def integrity_check(self) -> list[str]: ...

    def artifact_inventory(self) -> list[dict[str, Any]]: ...
