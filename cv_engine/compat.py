from __future__ import annotations

from pathlib import Path
from typing import Any

from .application.errors import WorkflowError
from .domain.facts import FactStore
from .domain.models import CandidateContext, ValidationReport
from .domain.profiles import ProfileStore
from .domain.selection import EmphasisPolicyStore
from .runtime.composition import build_services
from .runtime.workspace import Workspace, load_workspace


def resolve_job_snapshot_id(repository: Any, application_id: str) -> str:
    """The snapshot a legacy caller meant when it named none.

    v2 commands take explicit source IDs. v1 signatures do not carry one, so
    the resolution happens here, in the compatibility layer, where `latest` is
    a query convenience rather than part of what a command means.
    """
    return repository.latest_snapshot(application_id)["id"]


def resolve_job_analysis_id(repository: Any, application_id: str) -> str:
    """The analysis a legacy caller meant when it named none."""
    return repository.latest_analysis(application_id)[0]


class Engine:
    """Temporary compatibility façade over the application services.

    It lives outside the layered packages on purpose: it is the v1 surface the
    old CLI and test suite still address, not a v2 boundary, and it is deleted
    once those callers use the services directly.

    It exists so the v1 CLI and the v1 test suite keep working while the
    services take ownership of the workflow. It holds no business logic of its
    own: every method delegates, and the façade is removed once its callers
    address the services directly.
    """

    def __init__(
        self,
        workspace: Workspace | Path,
        db_path: Path | None = None,
        *,
        services: Any = None,
    ):
        self.workspace = (
            workspace if isinstance(workspace, Workspace) else load_workspace(Path(workspace))
        )
        self.services = services or build_services(self.workspace, database_path=db_path)
        self.root = self.workspace.root
        self.knowledge_root = self.workspace.knowledge_root
        self.artifacts_root = self.workspace.artifacts_root
        self.repo = self.services.repository
        self.db_path = self.repo.path

    # --- knowledge -------------------------------------------------------

    @property
    def base_dir(self) -> Path:
        return self.services.knowledge.base_dir

    def knowledge(self) -> tuple[FactStore, ProfileStore, EmphasisPolicyStore]:
        return self.services.knowledge_lifecycle.knowledge()

    def candidate(self, facts: FactStore | None = None) -> CandidateContext:
        return self.services.knowledge_lifecycle.candidate(facts)

    def knowledge_versions(self) -> dict[str, str]:
        return self.services.knowledge_lifecycle.knowledge_versions()

    def list_facts(self, status: str | None = None) -> list[dict[str, Any]]:
        return self.services.knowledge_lifecycle.list_facts(status)

    def show_fact(self, fact_id: str) -> dict[str, Any]:
        return self.services.knowledge_lifecycle.show_fact(fact_id)

    def fact_history(self, fact_id: str | None = None) -> list[dict[str, Any]]:
        return self.services.knowledge_lifecycle.fact_history(fact_id)

    def add_fact(self, source: str, payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return self.services.knowledge_lifecycle.add_fact(source, payload, **kwargs)

    def promote_fact(self, fact_id: str, target: str, **kwargs: Any) -> dict[str, Any]:
        return self.services.knowledge_lifecycle.promote_fact(fact_id, target, **kwargs)

    def capture_claim_fact(self, application_id: str, claim_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.services.knowledge_lifecycle.capture_claim_fact(
            application_id, claim_id, **kwargs
        )

    def attach_fact(self, fact_id: str, profile: str, section: str, **kwargs: Any) -> dict[str, Any]:
        return self.services.knowledge_lifecycle.attach_fact(fact_id, profile, section, **kwargs)

    def reconcile_facts(self) -> dict[str, Any]:
        return self.services.knowledge_lifecycle.reconcile_facts()

    # --- preparation -----------------------------------------------------

    def ingest(self, company: str, role: str, job_text: str, url: str | None = None) -> tuple[str, str]:
        ingested = self.services.applications.ingest(company, role, job_text, url)
        return ingested.application_id, ingested.job_snapshot_id

    def analyze(self, application_id: str, **kwargs: Any) -> tuple[str, Any]:
        job_snapshot_id = kwargs.pop(
            "job_snapshot_id", None
        ) or resolve_job_snapshot_id(self.repo, application_id)
        analysed = self.services.analysis.analyze(application_id, job_snapshot_id, **kwargs)
        return analysed.analysis_id, analysed.analysis

    def draft(
        self, application_id: str, job_analysis_id: str | None = None
    ) -> tuple[Path, Path, ValidationReport]:
        analysis_id = job_analysis_id or resolve_job_analysis_id(self.repo, application_id)
        drafted = self.services.drafts.draft(application_id, analysis_id)
        return drafted.markdown, drafted.manifest, drafted.validation

    def validate_working(self, application_id: str) -> ValidationReport:
        return self.services.drafts.validate_working(application_id)

    def edit_claim(
        self, application_id: str, claim_id: str, fact_ids: list[str], **kwargs: Any
    ) -> tuple[Path, ValidationReport]:
        edited = self.services.drafts.edit_claim(application_id, claim_id, fact_ids, **kwargs)
        return edited.markdown, edited.validation

    def link_claim(
        self, application_id: str, claim_id: str, text: str, fact_ids: list[str]
    ) -> tuple[Path, ValidationReport]:
        edited = self.services.drafts.link_claim(application_id, claim_id, text, fact_ids)
        return edited.markdown, edited.validation

    def sync_working_claims(self, application_id: str) -> tuple[Path, ValidationReport]:
        edited = self.services.drafts.sync_working_claims(application_id)
        return edited.markdown, edited.validation

    def approve(self, application_id: str) -> dict[str, Any]:
        approved = self.services.drafts.approve(application_id)
        return {
            "version": approved.version,
            "directory": approved.directory,
            "decision_record_id": approved.decision_record_id,
        }

    # --- rendering and tracking ------------------------------------------

    def render(self, application_id: str) -> tuple[Path, ValidationReport]:
        rendered = self.services.rendering.render(application_id)
        return rendered.pdf, rendered.validation

    def ready_report(self, application_id: str) -> ValidationReport:
        return self.services.rendering.ready_report(application_id)

    def submit(self, application_id: str, reason: str = "submitted to employer") -> dict[str, Any]:
        submitted = self.services.tracking.submit(application_id, reason)
        return {
            "application_id": submitted.application_id,
            "pdf_artifact_version_id": submitted.pdf_artifact_version_id,
            **submitted.application,
        }

    def fast(
        self,
        company: str,
        role: str,
        job_text: str,
        *,
        url: str | None = None,
        track: str | None = None,
        profile: str | None = None,
        emphasis: str | None = None,
        language: str | None = None,
        accept_low_fit: bool = False,
    ) -> dict[str, Any]:
        """The explicit no-pause flow: an approval instruction, not a bypass.

        Invoking it is itself the user's approval decision, recorded as such.
        It chains the same use-cases in the same order and every validation and
        blocker still applies; nothing here can approve unvalidated content.
        """
        application_id, _ = self.ingest(company, role, job_text, url)
        self.analyze(
            application_id,
            track=track,
            profile=profile,
            emphasis=emphasis,
            language=language,
            accept_low_fit=accept_low_fit,
        )
        _, _, report = self.draft(application_id)
        if not report.passed:
            raise WorkflowError("fast mode blocked by pre-render validation")
        approval = self.approve(application_id)
        pdf, ready_report = self.render(application_id)
        if not ready_report.passed:
            raise WorkflowError("fast mode blocked by post-render validation")
        return {"application_id": application_id, "approval": approval, "pdf": str(pdf), "ready": True}


__all__ = [
    "Engine",
    "WorkflowError",
    "resolve_job_analysis_id",
    "resolve_job_snapshot_id",
]
