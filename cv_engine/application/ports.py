from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from ..domain.knowledge import Knowledge
from ..domain.models import (
    CandidateContext,
    DraftDocument,
    JobClassificationProposal,
    Profile,
    ValidationReport,
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
    application decision, not a storage detail. v1's per-statement transaction
    behaviour is unchanged: the adapter's existing boundary is what this names.
    """

    def __enter__(self) -> "UnitOfWork": ...

    def __exit__(self, *exc: Any) -> bool | None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class ApplicationStore(Protocol):
    """Applications themselves: identity, status, and tracking fields."""

    def create_application(
        self, *, company: str, target_role: str, original_job_text: str, source_url: str | None
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


class JobStore(Protocol):
    """Immutable job snapshots and the analyses derived from them."""

    def latest_snapshot(self, application_id: str) -> dict[str, Any]: ...

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]: ...

    def save_analysis(
        self, application_id: str, snapshot_id: str, analysis: Any, *, provider: str, model: str
    ) -> str: ...

    def get_analysis(self, analysis_id: str) -> dict[str, Any]: ...

    def analyses(self, application_id: str) -> list[dict[str, Any]]: ...

    def latest_analysis(self, application_id: str) -> tuple[str, Any]: ...


class ArtifactRegistry(Protocol):
    """What was produced, what validated it, and what decided it."""

    def register_artifact_version(self, *args: Any, **kwargs: Any) -> str: ...

    def latest_artifact_version(self, *args: Any, **kwargs: Any) -> dict[str, Any]: ...

    def artifact_versions(self, application_id: str) -> list[dict[str, Any]]: ...

    def record_decision(self, *args: Any, **kwargs: Any) -> str: ...

    def latest_decision(self, application_id: str) -> dict[str, Any]: ...

    def decision_for_artifact_version(self, artifact_version_id: str) -> dict[str, Any]: ...

    def record_generation_run(self, values: dict[str, Any]) -> str: ...

    def record_validation(self, *args: Any, **kwargs: Any) -> str: ...

    def validation_for_artifact(
        self, application_id: str, phase: str, artifact_version_id: str
    ) -> ValidationReport: ...


class FactAudit(Protocol):
    """The fact lifecycle's trail, which lives beside the files it describes."""

    def record_fact_event(self, **kwargs: Any) -> str: ...

    def fact_events(self, fact_id: str | None = ...) -> list[dict[str, Any]]: ...

    def latest_fact_statuses(self) -> dict[str, str]: ...


class ApplicationRepository(
    ApplicationStore, JobStore, ArtifactRegistry, FactAudit, Protocol
):
    """Everything a service may ask persistence for, as one composed port.

    The focused protocols above are the real contracts — a service depends on
    the narrow one it uses. This composition exists because one SQLite adapter
    satisfies all of them, and the composition root binds it once.

    It deliberately exposes no connection, path, or private adapter method: the
    application layer must not be able to reach around the port.
    """

    def unit_of_work(self) -> UnitOfWork: ...

    def record_event(
        self, application_id: str, event_type: str, payload: dict[str, Any]
    ) -> str: ...

    def integrity_check(self) -> list[str]: ...

    def artifact_inventory(self) -> list[dict[str, Any]]: ...
