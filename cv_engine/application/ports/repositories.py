"""One capability each: the leaves every composed repository is built from.

Each protocol here names a single area of stored state. A service depends on
the narrowest one that covers what it does, so the adapter cannot quietly
satisfy a service with more reach than the service declared.
"""

from __future__ import annotations

from typing import Any, Protocol, Self, runtime_checkable

from ...domain.contracts.drafts import WorkingDraft
from ...domain.contracts.records import (
    ValidationRunLineage,
)
from ...domain.contracts.selection import (
    SelectionPlan,
)
from ...domain.contracts.validation import ValidationReport
from ..knowledge_mutations import (
    KnowledgeMutation,
    PrepareKnowledgeMutation,
)


@runtime_checkable
class UnitOfWork(Protocol):
    """One atomic boundary around a command's writes.

    Declared here because whether a command's records land together is an
    application decision, not a storage detail. A successful scope still rolls
    back unless the use-case explicitly calls ``commit()``. The contract is
    load-bearing for the multi-record commands, which must land atomically.
    """

    def __enter__(self) -> UnitOfWork: ...

    def __exit__(self, *exc: Any) -> bool | None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class ApplicationStore(Protocol):
    """Applications themselves: identity, status, and tracking fields."""

    def get_application(self, application_id: str) -> dict[str, Any]: ...

    def list_applications(self, *, include_deleted: bool = False) -> list[dict[str, Any]]: ...

    def set_application_deleted(self, application_id: str, deleted_at: str) -> None: ...


class JobStore(Protocol):
    """Immutable job snapshots and the analyses derived from them."""

    def add_job_snapshot(
        self,
        application_id: str,
        payload_path: str,
        source_hash: str,
        normalized_hash: str,
        source_url: str | None = ...,
        source_metadata: dict[str, Any] | None = ...,
        snapshot_id: str | None = ...,
        captured_at: str | None = ...,
    ) -> str: ...

    def latest_snapshot(self, application_id: str) -> dict[str, Any]: ...

    def job_snapshots(self, application_id: str) -> list[dict[str, Any]]: ...

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]: ...

    def get_analysis(self, analysis_id: str) -> dict[str, Any]: ...

    def analyses(self, application_id: str) -> list[dict[str, Any]]: ...

    def latest_analysis(self, application_id: str) -> tuple[str, Any]: ...

    def selection_plan(self, selection_plan_id: str) -> SelectionPlan: ...

    def latest_selection_plan(self, application_id: str) -> SelectionPlan: ...


class ArtifactRegistry(Protocol):
    """What was produced, what validated it, and what decided it."""

    def register_artifact_version(
        self,
        application_id: str | None,
        artifact_type: str,
        logical_name: str,
        path: str,
        content_hash: str,
        lifecycle_status: str,
        *,
        revision_id: str | None = None,
        job_snapshot_id: str | None = None,
        track: str | None = None,
        profile: str | None = None,
        emphasis: str | None = None,
        facts_version: str | None = None,
        metadata: dict[str, Any] | None = None,
        approved_at: str | None = None,
        submitted_at: str | None = None,
        artifact_version_id: str | None = None,
    ) -> str: ...

    def latest_artifact_version(
        self,
        application_id: str,
        artifact_type: str,
        lifecycle_status: str | None = None,
    ) -> dict[str, Any]: ...

    def artifact_versions(self, application_id: str) -> list[dict[str, Any]]: ...

    def artifact_version(self, artifact_version_id: str) -> dict[str, Any]: ...

    def artifact_version_for_revision(
        self,
        revision_id: str,
        artifact_type: str,
        lifecycle_status: str | None = None,
    ) -> dict[str, Any]: ...

    def latest_decision(self, application_id: str) -> dict[str, Any]: ...

    def decision_for_artifact_version(self, artifact_version_id: str) -> dict[str, Any]: ...

    def record_validation(
        self,
        application_id: str,
        phase: str,
        report: ValidationReport,
        artifact_version_id: str | None = None,
        *,
        lineage: ValidationRunLineage | None = None,
    ) -> str: ...

    def validation_for_artifact(
        self, application_id: str, phase: str, artifact_version_id: str
    ) -> ValidationReport: ...

    def validation_report(self, validation_id: str) -> ValidationReport: ...

    def validation_run(self, validation_id: str) -> dict[str, Any]: ...

    def validation_lineage(self, validation_id: str) -> ValidationRunLineage: ...

    def latest_validation_for_working_draft(
        self, working_draft_id: str
    ) -> dict[str, Any] | None: ...


class FactAudit(Protocol):
    """The fact lifecycle's trail, which lives beside the files it describes."""

    def record_fact_event(
        self,
        *,
        fact_id: str,
        source_file: str,
        event_type: str,
        from_status: str | None,
        to_status: str,
        fact: dict[str, Any],
        facts_version: str,
        lifecycle_version: str,
        reason: str = ...,
        application_id: str | None = ...,
        claim_id: str | None = ...,
        event_id: str | None = ...,
        created_at: str | None = ...,
    ) -> str: ...

    def fact_events(self, fact_id: str | None = ...) -> list[dict[str, Any]]: ...

    def fact_event(self, event_id: str) -> dict[str, Any] | None: ...

    def latest_fact_statuses(self) -> dict[str, str]: ...


class WorkingDraftReader(Protocol):
    """Read access to the one active working draft of an application."""

    def active_working_draft(self, application_id: str) -> WorkingDraft: ...


class KnowledgeMutationRepository(Protocol):
    def unit_of_work(self) -> UnitOfWork: ...

    def prepare_knowledge_mutation(
        self, request: PrepareKnowledgeMutation, *, prepared_at: str | None = ...
    ) -> KnowledgeMutation: ...

    def knowledge_mutation(self, mutation_id: str) -> KnowledgeMutation: ...

    def prepared_knowledge_mutations(self) -> list[KnowledgeMutation]: ...

    def quarantined_knowledge_mutations(self) -> list[KnowledgeMutation]: ...

    def commit_knowledge_mutation(
        self, mutation_id: str, *, committed_at: str | None = ...
    ) -> KnowledgeMutation: ...

    def quarantine_knowledge_mutation(
        self, mutation_id: str, reason: str, *, quarantined_at: str | None = ...
    ) -> KnowledgeMutation: ...

    def bind(self, uow: UnitOfWork) -> Self: ...
