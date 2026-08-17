from __future__ import annotations

from pathlib import Path
from typing import Any

from .application.commands import AnalyzeCommand, DraftCommand, IngestCommand
from .application.errors import KnowledgeRejected, WorkflowError
from .domain.facts import FactStore, FactStoreError
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
        return self.services.knowledge_lifecycle.knowledge_versions().model_dump()

    def list_facts(self, status: str | None = None) -> list[dict[str, Any]]:
        result = self.services.knowledge_lifecycle.list_facts(status)
        return [
            {**item.fact.model_dump(mode="json"), "recorded_status": item.recorded_status}
            for item in result.items
        ]

    def show_fact(self, fact_id: str) -> dict[str, Any]:
        result = self.services.knowledge_lifecycle.show_fact(fact_id)
        return {
            **result.fact.model_dump(mode="json"),
            "events": [event.model_dump(mode="json") for event in result.events],
        }

    def fact_history(self, fact_id: str | None = None) -> list[dict[str, Any]]:
        return [
            event.model_dump(mode="json")
            for event in self.services.knowledge_lifecycle.fact_history(fact_id).events
        ]

    def add_fact(self, source: str, payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        try:
            result = self.services.knowledge_lifecycle.add_fact(source, payload, **kwargs)
        except KnowledgeRejected as exc:
            if isinstance(exc.__cause__, FactStoreError):
                raise exc.__cause__
            raise
        return result.model_dump(mode="json")

    def promote_fact(self, fact_id: str, target: str, **kwargs: Any) -> dict[str, Any]:
        try:
            result = self.services.knowledge_lifecycle.promote_fact(fact_id, target, **kwargs)
        except KnowledgeRejected as exc:
            if isinstance(exc.__cause__, FactStoreError):
                raise exc.__cause__
            raise
        return result.model_dump(mode="json")

    def capture_claim_fact(self, application_id: str, claim_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.services.knowledge_lifecycle.capture_claim_fact(
            application_id, claim_id, **kwargs
        ).model_dump(mode="json")

    def attach_fact(self, fact_id: str, profile: str, section: str, **kwargs: Any) -> dict[str, Any]:
        result = self.services.knowledge_lifecycle.attach_fact(
            fact_id, profile, section, **kwargs
        ).model_dump(mode="json")
        result["profile_path"] = result.pop("profile_source")
        return result

    def reconcile_facts(self) -> dict[str, Any]:
        return self.services.knowledge_lifecycle.reconcile_facts().model_dump(mode="json")

    # --- preparation -----------------------------------------------------

    def ingest(self, company: str, role: str, job_text: str, url: str | None = None) -> tuple[str, str]:
        ingested = self.services.applications.ingest(IngestCommand(
            company=company,
            target_role=role,
            job_text=job_text,
            source_url=url,
        ))
        return ingested.application_id, ingested.job_snapshot_id

    def analyze(self, application_id: str, **kwargs: Any) -> tuple[str, Any]:
        job_snapshot_id = kwargs.pop(
            "job_snapshot_id", None
        ) or resolve_job_snapshot_id(self.repo, application_id)
        analysed = self.services.analysis.analyze(AnalyzeCommand(
            application_id=application_id,
            job_snapshot_id=job_snapshot_id,
            track_override=kwargs.pop("track", None),
            profile_override=kwargs.pop("profile", None),
            emphasis_override=kwargs.pop("emphasis", None),
            language_override=kwargs.pop("language", None),
            accept_low_fit=kwargs.pop("accept_low_fit", False),
            provider=kwargs.pop("provider", "deterministic"),
            model=kwargs.pop("model", "rules-v1"),
            **kwargs,
        ))
        return analysed.analysis_id, analysed.analysis

    def draft(
        self, application_id: str, job_analysis_id: str | None = None
    ) -> tuple[Path, Path, ValidationReport]:
        analysis_id = job_analysis_id or resolve_job_analysis_id(self.repo, application_id)
        drafted = self.services.drafts.draft(DraftCommand(
            application_id=application_id,
            job_analysis_id=analysis_id,
        ))
        paths = self.services.artifacts.working_paths(application_id)
        return paths.markdown, paths.manifest, drafted.validation

    def validate_working(self, application_id: str) -> ValidationReport:
        return self.services.drafts.validate_working(application_id)

    def edit_claim(
        self, application_id: str, claim_id: str, fact_ids: list[str], **kwargs: Any
    ) -> tuple[Path, ValidationReport]:
        edited = self.services.drafts.edit_claim(application_id, claim_id, fact_ids, **kwargs)
        return self.services.artifacts.working_paths(application_id).markdown, edited.validation

    def link_claim(
        self, application_id: str, claim_id: str, text: str, fact_ids: list[str]
    ) -> tuple[Path, ValidationReport]:
        edited = self.services.drafts.link_claim(application_id, claim_id, text, fact_ids)
        return self.services.artifacts.working_paths(application_id).markdown, edited.validation

    def sync_working_claims(self, application_id: str) -> tuple[Path, ValidationReport]:
        edited = self.services.drafts.sync_working_claims(application_id)
        return self.services.artifacts.working_paths(application_id).markdown, edited.validation

    def approve(self, application_id: str) -> dict[str, Any]:
        approved = self.services.drafts.approve(application_id)
        return {
            "version": approved.version,
            "directory": self.services.artifacts.approved_version_dir(
                application_id, approved.version
            ),
            "decision_record_id": approved.decision_record_id,
        }

    # --- rendering and tracking ------------------------------------------

    def render(self, application_id: str) -> tuple[Path, ValidationReport]:
        rendered = self.services.rendering.render(application_id)
        record = self.repo.latest_artifact_version(application_id, "resume_pdf")
        return self.services.artifacts.resolve(record["path"]), rendered.validation

    def ready_report(self, application_id: str) -> ValidationReport:
        return self.services.rendering.ready_report(application_id)

    def submit(self, application_id: str, reason: str = "submitted to employer") -> dict[str, Any]:
        submitted = self.services.tracking.submit(application_id, reason)
        application = self.services.queries.application_detail(application_id).application
        return {
            "application_id": submitted.application_id,
            "pdf_artifact_version_id": submitted.pdf_artifact_version_id,
            **application.model_dump(mode="json"),
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
