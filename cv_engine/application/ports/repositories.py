"""One capability each: the leaves every composed repository is built from.

Each protocol here names a single area of stored state. A service depends on
the narrowest one that covers what it does, so the adapter cannot quietly
satisfy a service with more reach than the service declared.
"""

from __future__ import annotations

from typing import Any, Protocol, Self, runtime_checkable

from ...domain.models import (
    DecisionRecord,
    SelectionManifest,
    SelectionPlan,
    ValidationReport,
    ValidationRunLineage,
    WorkingDraft,
)
from ..knowledge_mutations import (
    KnowledgeMutation,
    PrepareKnowledgeMutation,
)
from ..operations import (
    CreateOperation,
    OperationFailureCode,
    OperationPhase,
    OperationView,
    PersistedOperation,
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

    def create_application(
        self,
        *,
        company: str,
        target_role: str,
        payload_path: str,
        source_hash: str,
        normalized_hash: str,
        source_url: str | None,
        application_id: str | None = None,
        snapshot_id: str | None = None,
        actor_type: str = ...,
        client: str,
    ) -> tuple[str, str]: ...

    def get_application(self, application_id: str) -> dict[str, Any]: ...

    def list_applications(self) -> list[dict[str, Any]]: ...

    def set_normalized_role(self, application_id: str, normalized_role: str) -> None: ...

    def update_application_notes(
        self, application_id: str, notes: str, expected_notes: str, *, updated_at: str
    ) -> dict[str, Any]: ...

    def record_event(
        self, application_id: str, event_type: str, payload: dict[str, Any]
    ) -> str: ...


class JobStore(Protocol):
    """Immutable job snapshots and the analyses derived from them."""

    def duplicate_application_inputs(self) -> list[dict[str, Any]]: ...

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

    def snapshot_for_content_hash(
        self, application_id: str, content_hash: str
    ) -> dict[str, Any] | None: ...

    def latest_snapshot(self, application_id: str) -> dict[str, Any]: ...

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]: ...

    def save_analysis(
        self,
        application_id: str,
        snapshot_id: str,
        analysis: Any,
        plan: SelectionManifest,
        *,
        provider: str,
        model: str,
        candidate_context_version: str,
        candidate_context_hash: str,
        profile_version: str,
        selection_policy_version: str,
        track_emphasis_dependencies: dict[str, str],
    ) -> tuple[str, SelectionPlan]: ...

    def get_analysis(self, analysis_id: str) -> dict[str, Any]: ...

    def analyses(self, application_id: str) -> list[dict[str, Any]]: ...

    def latest_analysis(self, application_id: str) -> tuple[str, Any]: ...

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
        plan_id: str | None = None,
        created_at: str | None = None,
    ) -> SelectionPlan: ...

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

    def insert_decision(self, record: DecisionRecord) -> None: ...

    def latest_decision(self, application_id: str) -> dict[str, Any]: ...

    def decision_for_artifact_version(self, artifact_version_id: str) -> dict[str, Any]: ...

    def record_generation_run(self, values: dict[str, Any]) -> str: ...

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


class OperationRepository(Protocol):
    """Durable Operations shared safely by concurrent claimers."""

    def create_operation(
        self,
        request: CreateOperation,
        *,
        operation_id: str | None = None,
        created_at: str | None = None,
    ) -> PersistedOperation: ...

    def operation(self, operation_id: str) -> PersistedOperation: ...

    def active_operation(self, application_id: str) -> OperationView | None: ...

    def latest_operation(self, application_id: str) -> OperationView | None: ...

    def claim_operation(
        self,
        operation_id: str,
        *,
        runner_id: str,
        lease_seconds: int = 30,
        now: str | None = None,
    ) -> PersistedOperation | None: ...

    def claim_next_operation(
        self,
        *,
        runner_id: str,
        lease_seconds: int = 30,
        now: str | None = None,
    ) -> PersistedOperation | None: ...

    def heartbeat_operation(
        self,
        operation_id: str,
        *,
        runner_id: str,
        lease_seconds: int = 30,
        now: str | None = None,
    ) -> None: ...

    def interrupt_expired_operations(self, *, now: str | None = None) -> list[str]: ...

    def set_operation_phase(
        self,
        operation_id: str,
        phase: OperationPhase,
        *,
        runner_id: str,
        message: str = "",
    ) -> None: ...

    def cancellation_requested(self, operation_id: str) -> bool: ...

    def request_operation_cancellation(
        self, operation_id: str, *, now: str | None = None
    ) -> PersistedOperation: ...

    def record_operation_output(
        self,
        operation_id: str,
        output_type: str,
        output_id: str,
        *,
        active: bool = False,
        created_at: str | None = None,
    ) -> str: ...

    def activate_operation_output(
        self,
        operation_id: str,
        output_type: str,
        output_id: str,
        *,
        now: str | None = None,
    ) -> None: ...

    def record_operation_attempt(
        self,
        operation_id: str,
        *,
        runner_id: str,
        retry_at: str | None = None,
    ) -> int: ...

    def complete_operation(
        self,
        operation_id: str,
        *,
        runner_id: str,
        now: str | None = None,
    ) -> PersistedOperation: ...

    def fail_operation(
        self,
        operation_id: str,
        code: OperationFailureCode,
        safe_detail: str,
        *,
        runner_id: str,
        technical_log_reference: str | None = None,
        now: str | None = None,
    ) -> PersistedOperation: ...

    def claim_idempotency_receipt(
        self,
        command_type: str,
        idempotency_key: str,
        payload: dict[str, Any],
        *,
        reserved_entity_id: str,
        created_at: str | None = None,
    ) -> dict[str, Any]: ...

    def idempotency_receipt(
        self, command_type: str, idempotency_key: str
    ) -> dict[str, Any] | None: ...

    def complete_idempotency_receipt(
        self,
        receipt_id: str,
        result: dict[str, Any],
        *,
        completed_at: str | None = None,
    ) -> None: ...
