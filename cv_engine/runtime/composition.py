from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..application.operation_runner import OperationRunner
from ..application.operations import OperationType
from ..application.ports import (
    ApplicationRepository,
    ArtifactStore,
    ClassificationProvider,
    KnowledgeStore,
    Renderer,
    RevisionPayloadStore,
    UnitOfWork,
)
from ..application.services.analysis import AnalysisService
from ..application.services.applications import ApplicationService
from ..application.services.drafts import DraftService
from ..application.services.knowledge import KnowledgeService
from ..application.services.operations import (
    AnalysisOperationHandler,
    DraftOperationHandler,
    OperationService,
    RenderOperationHandler,
)
from ..application.services.projections import ApplicationQueryService
from ..application.services.rendering import RenderingService
from ..application.services.tracking import TrackingService
from ..infrastructure.artifacts import FilesystemArtifactStore
from ..infrastructure.knowledge import FileKnowledge
from ..infrastructure.operation_logging import OperationFailureLogger
from ..infrastructure.payloads import PayloadStore
from ..infrastructure.persistence import Repository
from ..infrastructure.providers import OpenAIClassificationProvider
from ..infrastructure.rendering import PlaywrightRenderer
from ..util import new_id
from .execution import ForegroundOperationExecutor, OperationWorker
from .workspace import Workspace


@dataclass(frozen=True)
class Services:
    """Everything a client needs, already wired to one Workspace."""

    workspace: Workspace
    repository: ApplicationRepository
    knowledge: KnowledgeStore
    artifacts: ArtifactStore
    payloads: RevisionPayloadStore
    unit_of_work: Callable[[], UnitOfWork]
    applications: ApplicationService
    queries: ApplicationQueryService
    analysis: AnalysisService
    drafts: DraftService
    rendering: RenderingService
    tracking: TrackingService
    knowledge_lifecycle: KnowledgeService
    operations: OperationService
    operation_runner: OperationRunner
    foreground_operations: ForegroundOperationExecutor
    operation_worker: OperationWorker


def build_services(
    workspace: Workspace,
    *,
    database_path: Path | None = None,
    repository: ApplicationRepository | None = None,
    knowledge: KnowledgeStore | None = None,
    artifacts: ArtifactStore | None = None,
    payloads: RevisionPayloadStore | None = None,
    renderer: Renderer | None = None,
    provider: ClassificationProvider | None = None,
) -> Services:
    """The manual composition root.

    The only place that decides which concrete adapter satisfies which port.
    Callers may substitute any of them — that is how tests replace the browser
    and the AI provider without the application layer knowing either exists.
    """
    resolved_repository = repository or Repository(database_path or workspace.database_path)
    resolved_knowledge = knowledge or FileKnowledge(
        workspace.knowledge_root,
        workspace_root=workspace.root,
        temp_root=workspace.temp_root,
        has_prepared_mutation=lambda: bool(
            resolved_repository.prepared_knowledge_mutations()
        ),
    )
    resolved_artifacts = artifacts or FilesystemArtifactStore(workspace)
    resolved_payloads = payloads or PayloadStore(workspace)
    resolved_renderer = renderer or PlaywrightRenderer(workspace.knowledge_root)
    resolved_provider = provider or OpenAIClassificationProvider(
        workspace.knowledge_root / "ai" / "prompts" / "system-v1.md"
    )
    shared = {
        "repository": resolved_repository,
        "knowledge": resolved_knowledge,
        "artifacts": resolved_artifacts,
        "renderer": resolved_renderer,
        "provider": resolved_provider,
        "snapshots": resolved_payloads,
        "installation_id": workspace.installation_id(),
    }
    analysis_service = AnalysisService(**shared)
    operation_service = OperationService(**shared)
    draft_service = DraftService(**shared)
    rendering_service = RenderingService(**shared)
    failure_logger = OperationFailureLogger(workspace.root, workspace.logs_root)
    runner = OperationRunner(
        resolved_repository,
        {
            OperationType.ANALYZE_JOB: AnalysisOperationHandler(analysis_service),
            OperationType.CREATE_DRAFT: DraftOperationHandler(draft_service),
            OperationType.RENDER_REVISION: RenderOperationHandler(rendering_service),
        },
        runner_id=f"local-{new_id()}",
        technical_logger=failure_logger.record,
    )
    foreground = ForegroundOperationExecutor(resolved_repository, runner)
    worker = OperationWorker(resolved_repository, runner)
    knowledge_service = KnowledgeService(**shared)
    knowledge_service.recover_knowledge_mutations()
    return Services(
        workspace=workspace,
        repository=resolved_repository,
        knowledge=resolved_knowledge,
        artifacts=resolved_artifacts,
        payloads=resolved_payloads,
        unit_of_work=resolved_repository.unit_of_work,
        applications=ApplicationService(**shared),
        queries=ApplicationQueryService(**shared),
        analysis=analysis_service,
        drafts=draft_service,
        rendering=rendering_service,
        tracking=TrackingService(**shared),
        knowledge_lifecycle=knowledge_service,
        operations=operation_service,
        operation_runner=runner,
        foreground_operations=foreground,
        operation_worker=worker,
    )
