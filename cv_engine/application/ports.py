from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from ..domain.knowledge import Knowledge
from ..domain.models import (
    CandidateContext,
    DraftDocument,
    JobClassificationProposal,
    Profile,
    ValidationReport,
)


class KnowledgeStore(Protocol):
    """Where canonical knowledge comes from, without saying it is files."""

    @property
    def base_dir(self) -> Path: ...

    def load(self) -> Knowledge: ...


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


class ApplicationRepository(Protocol):
    """The persisted application state the application layer depends on.

    Structural, so infrastructure's SQLite repository satisfies it without
    importing anything from this layer, and so no service has to know that the
    store is SQLite at all.
    """

    path: Path

    def create_application(
        self, *, company: str, target_role: str, original_job_text: str, source_url: str | None
    ) -> tuple[str, str]: ...

    def get_application(self, application_id: str) -> dict[str, Any]: ...

    def list_applications(self) -> list[dict[str, Any]]: ...

    def latest_snapshot(self, application_id: str) -> dict[str, Any]: ...

    def save_analysis(
        self, application_id: str, snapshot_id: str, analysis: Any, *, provider: str, model: str
    ) -> str: ...

    def get_analysis(self, analysis_id: str) -> dict[str, Any]: ...

    def latest_analysis(self, application_id: str) -> tuple[str, Any]: ...

    def transition_status(self, application_id: str, target: Any, reason: str = ...) -> None: ...

    def set_next_action(
        self, application_id: str, action: str | None, action_date: str | None
    ) -> None: ...

    def set_normalized_role(self, application_id: str, normalized_role: str) -> None: ...

    def record_event(
        self, application_id: str, event_type: str, payload: dict[str, Any]
    ) -> str: ...

    def record_fact_event(self, **kwargs: Any) -> str: ...

    def fact_events(self, fact_id: str | None = ...) -> list[dict[str, Any]]: ...

    def latest_fact_statuses(self) -> dict[str, str]: ...

    def register_artifact_version(self, *args: Any, **kwargs: Any) -> str: ...

    def latest_artifact_version(self, *args: Any, **kwargs: Any) -> dict[str, Any]: ...

    def artifact_versions(self, application_id: str) -> list[dict[str, Any]]: ...

    def record_decision(self, *args: Any, **kwargs: Any) -> str: ...

    def latest_decision(self, application_id: str) -> dict[str, Any]: ...

    def record_generation_run(self, values: dict[str, Any]) -> str: ...

    def record_validation(self, *args: Any, **kwargs: Any) -> str: ...

    def validation_for_artifact(
        self, application_id: str, phase: str, artifact_version_id: str
    ) -> ValidationReport: ...

    def integrity_check(self) -> list[str]: ...
