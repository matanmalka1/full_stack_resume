"""Draft persistence and source contracts, grouped by lifecycle.

Consumer-specific protocols keep authoring, validation, approval, history, and
worker reads explicit without a separate module for each interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ...domain.contracts.drafts import DraftDocument, WorkingDraft
from ...domain.contracts.providers import ProviderTaskResult
from ...domain.contracts.records import ApprovedRevision, ValidationRunLineage
from ...domain.contracts.selection import SelectionPlan
from ...domain.contracts.validation import ValidationReport
from ..chain import DraftChainSources
from ..commands import ApprovalResult
from ..operations import PersistedOperation
from ..services.proposals import ProviderEvidence
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


class DraftAuthoringSourceReader(Protocol):
    def analysis_source(self, tx: ReadTransaction, analysis_id: str) -> dict: ...

    def active_snapshot_id(self, tx: ReadTransaction, application_id: str) -> str: ...

    def snapshot_source(self, tx: ReadTransaction, snapshot_id: str) -> dict: ...

    def deleted_at(self, tx: ReadTransaction, application_id: str) -> str | None: ...

    def chain_source(
        self, tx: ReadTransaction, application_id: str, draft: DraftDocument
    ) -> DraftChainSources: ...


class DraftEvidencePreserver(Protocol):
    """External payload preservation followed by durable inactive registration."""

    def preserve(
        self, application_id: str, operation_id: str, task: str, provenance: ProviderTaskResult
    ) -> ProviderEvidence: ...


@dataclass(frozen=True)
class DraftGenerationSources:
    snapshot: dict
    analysis: dict
    plan: SelectionPlan
    active_snapshot_id: str
    active_analysis_id: str
    active_plan_id: str
    replaced: WorkingDraft | None


class DraftOperationSourceReader(Protocol):
    def generation_sources(
        self, tx: ReadTransaction, operation: PersistedOperation
    ) -> DraftGenerationSources: ...

    def regeneration_source(self, tx: ReadTransaction, working_draft_id: str) -> WorkingDraft: ...

    def knowledge_is_prepared(self, tx: ReadTransaction) -> bool: ...


@dataclass(frozen=True)
class DraftValidationContext:
    deleted_at: str | None
    chain: DraftChainSources
    plan: SelectionPlan


class DraftValidationSourceReader(Protocol):
    """Atomic read of the application disposition, lineage and named plan."""

    def validation_context(
        self, tx: ReadTransaction, working: WorkingDraft
    ) -> DraftValidationContext: ...


@dataclass(frozen=True)
class DraftApprovalContext:
    company: str
    target_role: str
    deleted_at: str | None
    quarantined_mutation_id: str | None
    chain: DraftChainSources
    plan: SelectionPlan | None
    validation_lineage: ValidationRunLineage | None
    validation_report: ValidationReport | None


@dataclass(frozen=True)
class ApprovalReplay:
    result: ApprovalResult | None
    provenance: dict[str, str] | None


class DraftApprovalSourceReader(Protocol):
    def approval_context(
        self, tx: ReadTransaction, working: WorkingDraft, validation_run_id: str
    ) -> DraftApprovalContext: ...

    def approval_replay(self, tx: ReadTransaction, revision_id: str) -> ApprovalReplay: ...


@dataclass(frozen=True)
class DraftHistoryApplication:
    company: str
    target_role: str
    deleted_at: str | None


class DraftHistoryApplicationReader(Protocol):
    """Consistent history-source labels; disposition guards archival writes."""

    def history_application(
        self, tx: ReadTransaction, application_id: str
    ) -> DraftHistoryApplication: ...
