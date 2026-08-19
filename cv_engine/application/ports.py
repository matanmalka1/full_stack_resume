from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Self, runtime_checkable

from ..domain.knowledge import Knowledge
from ..domain.models import (
    ApprovedRevision,
    AuditRecord,
    CandidateContext,
    DecisionRecord,
    DraftDocument,
    JobClassificationProposal,
    Profile,
    SelectionManifest,
    SelectionPlan,
    ValidationReport,
    ValidationRunLineage,
    WorkingDraft,
)
from .operations import (
    CreateOperation,
    OperationFailureCode,
    OperationPhase,
    OperationView,
    PersistedOperation,
)


@dataclass(frozen=True)
class DraftPaths:
    """Where one draft's two payloads ended up."""

    markdown: Path
    manifest: Path


@dataclass(frozen=True)
class StoredDraft:
    """A draft as it was stored, with the exact document text that was written.

    The text travels with the locations so a caller can validate what is stored
    without reading it back, and cannot accidentally validate something else.
    """

    paths: DraftPaths
    markdown: str


@dataclass(frozen=True)
class SnapshotPayload:
    """Storage-neutral metadata for one immutable JobSnapshot payload."""

    reference: str
    sha256: str
    size: int


@dataclass(frozen=True)
class RevisionPayloads:
    """The two verified immutable payloads owned by one ApprovedRevision."""

    structured: SnapshotPayload
    markdown: SnapshotPayload


@dataclass(frozen=True)
class RenderTargets:
    """Where one approved version's rendered outputs belong."""

    html: Path
    pdf: Path
    screenshot: Path
    recruiter_pdf_filename: str


class ArtifactStore(Protocol):
    """Where immutable and working payloads live.

    The application layer asks for "this application's working draft" or "this
    approved version"; it never composes a directory name and never opens a
    file. That is what keeps the storage layout an infrastructure decision
    instead of a rule spread across services.
    """

    def working_paths(self, application_id: str) -> DraftPaths: ...

    def write_working_draft(self, draft: Any) -> StoredDraft: ...

    def load_working_draft(self, application_id: str) -> Any: ...

    def working_markdown(self, application_id: str) -> str: ...

    def read_document(self, path: Path) -> str: ...

    def load_draft(self, manifest_path: Path) -> Any: ...

    def paths_beside(self, manifest_path: Path) -> DraftPaths: ...

    def approved_version_dir(self, application_id: str, version: int) -> Path: ...

    def publish_working_draft(self, application_id: str, version: int) -> DraftPaths: ...

    def resolve(self, stored_path: str) -> Path: ...

    def relative(self, path: Path) -> str: ...


class SnapshotPayloadStore(Protocol):
    def commit_snapshot(
        self,
        application_id: str,
        snapshot_id: str,
        text: str,
    ) -> SnapshotPayload: ...

    def read_snapshot(self, reference: str, expected_hash: str) -> str: ...


class RevisionPayloadStore(SnapshotPayloadStore, Protocol):
    def commit_revision(
        self,
        application_id: str,
        revision_id: str,
        structured_json: str,
        markdown: str,
    ) -> RevisionPayloads: ...

    def render_targets(
        self,
        application_id: str,
        revision_id: str,
        html_artifact_version_id: str,
        pdf_artifact_version_id: str,
        screenshot_artifact_version_id: str,
        recruiter_pdf_filename: str,
    ) -> RenderTargets: ...


class KnowledgeStore(Protocol):
    """Where canonical knowledge comes from, without saying it is files.

    Writes go through it too: creating, promoting, and attaching a fact all
    rewrite a canonical source, and where that source lives is not something
    the application layer is allowed to know.
    """

    def load(self) -> Knowledge: ...

    def facts(self) -> Any: ...

    def create_fact(self, source_name: str, payload: dict, *, canonical: bool = False) -> Any: ...

    def promote_fact(
        self, fact_id: str, target: Any, *, explicitly_confirmed: bool
    ) -> tuple[Any, Any]: ...

    def attach_fact(
        self, profile: str, fact_id: str, section: str, *, pin: bool = False
    ) -> tuple[Profile, str]: ...


class Renderer(Protocol):
    """HTML, PDF, and rendered-output validation.

    Kept behind a port because the browser is the slowest and least available
    dependency in the system: tests substitute it, and no application rule may
    depend on Playwright being present.
    """

    def render_html(
        self, draft: DraftDocument, output_path: Path, candidate: CandidateContext
    ) -> Path: ...

    def render_pdf(
        self, html_path: Path, pdf_path: Path, screenshot_path: Path
    ) -> dict[str, Any]: ...

    def validate_rendered(
        self,
        draft: DraftDocument,
        profile: Profile,
        html_path: Path,
        pdf_path: Path,
        screenshot_path: Path,
        geometry: dict[str, Any],
        candidate: CandidateContext,
        delivered_pdf_filename: str | None = None,
    ) -> ValidationReport: ...

    def filename_for(self, normalized_role: str, candidate: CandidateContext) -> str: ...


class ClassificationProvider(Protocol):
    """An AI provider's one v1 task, as a proposal the core may refuse."""

    def classify_job(self, payload: dict[str, Any], *, model: str) -> JobClassificationProposal: ...


@runtime_checkable
class UnitOfWork(Protocol):
    """One atomic boundary around a command's writes.

    Declared here because whether a command's records land together is an
    application decision, not a storage detail. A successful scope still rolls
    back unless the use-case explicitly calls ``commit()``. M1 defines this
    contract while preserving v1 command grouping; M2 makes it load-bearing for
    the multi-record v2 commands.
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
        client: str = ...,
        installation_id: str = ...,
    ) -> tuple[str, str]: ...

    def get_application(self, application_id: str) -> dict[str, Any]: ...

    def list_applications(self) -> list[dict[str, Any]]: ...

    def set_normalized_role(self, application_id: str, normalized_role: str) -> None: ...

    def record_event(
        self, application_id: str, event_type: str, payload: dict[str, Any]
    ) -> str: ...


class JobStore(Protocol):
    """Immutable job snapshots and the analyses derived from them."""

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
    ) -> str: ...

    def fact_events(self, fact_id: str | None = ...) -> list[dict[str, Any]]: ...

    def latest_fact_statuses(self) -> dict[str, str]: ...


class WorkingDraftReader(Protocol):
    """Read access to the one active working draft of an application."""

    def active_working_draft(self, application_id: str) -> WorkingDraft: ...


class PreparationRepository(ApplicationStore, JobStore, Protocol):
    """Application identity plus immutable snapshot/analysis preparation."""


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


class KnowledgeAuditRepository(FactAudit, WorkingDraftReader, Protocol):
    """The SQLite audit side of the file-backed Knowledge lifecycle.

    Promoting a manual claim reads the working draft the claim was edited in,
    so the port says so instead of relying on the adapter carrying more than
    the service declared.
    """


class OperationRepository(Protocol):
    """Durable Operations shared by foreground and background runners."""

    def create_operation(
        self,
        request: CreateOperation,
        *,
        installation_id: str,
        operation_id: str | None = None,
        created_at: str | None = None,
    ) -> PersistedOperation: ...

    def operation(self, operation_id: str) -> PersistedOperation: ...

    def active_operation(self, application_id: str) -> OperationView | None: ...

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
        installation_id: str,
        reserved_entity_id: str,
        created_at: str | None = None,
    ) -> dict[str, Any]: ...

    def idempotency_receipt(
        self, command_type: str, idempotency_key: str, *, installation_id: str
    ) -> dict[str, Any] | None: ...

    def complete_idempotency_receipt(
        self,
        receipt_id: str,
        result: dict[str, Any],
        *,
        completed_at: str | None = None,
    ) -> None: ...


class QueryRepository(
    ApplicationStore, JobStore, ArtifactRegistry, WorkingDraftReader, OperationRepository, Protocol
):
    """Read sources used to build storage-neutral query projections."""

    def read_transaction(self) -> AbstractContextManager[Self]: ...

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

    def insert_legacy_recruitment_event(
        self,
        *,
        application_id: str,
        mapped_from_status: str | None,
        mapped_to_status: str,
        legacy_event_id: str | None,
        legacy_from_status: str | None,
        legacy_to_status: str,
        occurred_at: str,
        reason: str = "",
        terminal_outcome: str | None = None,
    ) -> str: ...

    def recruitment_events(self, application_id: str) -> list[dict[str, Any]]: ...

    def submissions(self, application_id: str) -> list[dict[str, Any]]: ...

    def insert_audit(self, record: AuditRecord) -> None: ...

    def audit_records(self, application_id: str) -> list[dict[str, Any]]: ...


class ApplicationRepository(
    TrackingRepository,
    KnowledgeAuditRepository,
    OperationRepository,
    Protocol,
):
    """Composition-root view of the adapter; services use focused ports above."""

    def unit_of_work(self) -> UnitOfWork: ...

    def integrity_check(self) -> list[str]: ...

    def artifact_inventory(self) -> list[dict[str, Any]]: ...
