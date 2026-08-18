from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from ..domain.knowledge import Knowledge
from ..domain.models import (
    ApprovedRevision,
    CandidateContext,
    DraftDocument,
    JobClassificationProposal,
    Profile,
    SelectionManifest,
    SelectionPlan,
    ValidationReport,
    ValidationRunLineage,
    WorkingDraft,
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

    def render_targets(self, manifest_path: Path, pdf_filename: str) -> RenderTargets: ...

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
    ) -> ValidationReport: ...

    def filename_for(self, normalized_role: str, candidate: CandidateContext) -> str: ...


class ClassificationProvider(Protocol):
    """An AI provider's one v1 task, as a proposal the core may refuse."""

    def classify_job(
        self, payload: dict[str, Any], *, model: str
    ) -> JobClassificationProposal: ...


@runtime_checkable
class UnitOfWork(Protocol):
    """One atomic boundary around a command's writes.

    Declared here because whether a command's records land together is an
    application decision, not a storage detail. A successful scope still rolls
    back unless the use-case explicitly calls ``commit()``. M1 defines this
    contract while preserving v1 command grouping; M2 makes it load-bearing for
    the multi-record v2 commands.
    """

    def __enter__(self) -> "UnitOfWork": ...

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
    ) -> tuple[str, str]: ...

    def get_application(self, application_id: str) -> dict[str, Any]: ...

    def list_applications(self) -> list[dict[str, Any]]: ...

    def transition_status(self, application_id: str, target: Any, reason: str = ...) -> None: ...

    def set_next_action(
        self, application_id: str, action: str | None, action_date: str | None
    ) -> None: ...

    def set_normalized_role(self, application_id: str, normalized_role: str) -> None: ...

    def set_ready(self, application_id: str, pdf_artifact_version_id: str, reason: str = ...) -> None: ...

    def record_submission(
        self, application_id: str, pdf_artifact_version_id: str, reason: str = ...
    ) -> str: ...

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
    ) -> str: ...

    def latest_artifact_version(
        self,
        application_id: str,
        artifact_type: str,
        lifecycle_status: str | None = None,
    ) -> dict[str, Any]: ...

    def artifact_versions(self, application_id: str) -> list[dict[str, Any]]: ...

    def record_decision(
        self,
        application_id: str,
        artifact_version_id: str,
        job_snapshot_id: str,
        job_analysis_id: str,
        structured: dict[str, Any],
        summary: str,
    ) -> str: ...

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

    def validation_lineage(self, validation_id: str) -> ValidationRunLineage: ...


class FactAudit(Protocol):
    """The fact lifecycle's trail, which lives beside the files it describes."""

    def record_fact_event(self, **kwargs: Any) -> str: ...

    def fact_events(self, fact_id: str | None = ...) -> list[dict[str, Any]]: ...

    def latest_fact_statuses(self) -> dict[str, str]: ...


class PreparationRepository(ApplicationStore, JobStore, Protocol):
    """Application identity plus immutable snapshot/analysis preparation."""


class DraftRepository(ApplicationStore, JobStore, ArtifactRegistry, Protocol):
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

    def active_working_draft(self, application_id: str) -> WorkingDraft: ...

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

    def unit_of_work(self) -> UnitOfWork: ...

    def bind(self, uow: UnitOfWork) -> "DraftRepository": ...


class KnowledgeAuditRepository(FactAudit, Protocol):
    """The SQLite audit side of the file-backed Knowledge lifecycle."""


class QueryRepository(ApplicationStore, JobStore, ArtifactRegistry, Protocol):
    """Read sources used to build storage-neutral query projections."""


class ReadinessRepository(DraftRepository, Protocol):
    """Draft lineage plus the database integrity proof required for Ready."""

    def integrity_check(self) -> list[str]: ...


class TrackingRepository(ReadinessRepository, Protocol):
    """Recruitment mutations plus the full Ready proof required by submission."""


class ApplicationRepository(
    TrackingRepository,
    KnowledgeAuditRepository,
    Protocol,
):
    """Composition-root view of the adapter; services use focused ports above."""

    def unit_of_work(self) -> UnitOfWork: ...

    def integrity_check(self) -> list[str]: ...

    def artifact_inventory(self) -> list[dict[str, Any]]: ...
