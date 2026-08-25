from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .. import __version__
from ..api import ApiLimits, ApiServices, InstanceIdentity
from ..api.app import API_VERSION
from ..application.operation_runner import OperationRunner
from ..application.operations import OperationType
from ..application.ports import (
    AIProvider,
    ApplicationRepository,
    ArtifactStore,
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
    RegenerationOperationHandler,
    RenderOperationHandler,
    SelectionPlanOperationHandler,
)
from ..application.services.projections import ApplicationQueryService
from ..application.services.rendering import RenderingService
from ..application.services.tracking import TrackingService
from ..application.settings import SettingsService
from ..infrastructure.artifacts import FilesystemArtifactStore
from ..infrastructure.knowledge import FileKnowledge
from ..infrastructure.object_store import LocalObjectStore, ObjectStore, S3ObjectStore
from ..infrastructure.operation_logging import OperationFailureLogger
from ..infrastructure.payloads import PayloadStore
from ..infrastructure.persistence import (
    Repository,
    create_database_engine,
    current_database_revision,
)
from ..infrastructure.providers import OpenAIProvider
from ..infrastructure.rendering import PlaywrightRenderer
from ..util import new_id
from .config import API_MAX_BODY_BYTES_DEFAULT, RuntimeConfig, resolve_config
from .execution import ForegroundOperationExecutor, OperationWorker
from .workspace import Workspace, WorkspaceError


def _repo_root() -> Path:
    """The repository root, where a `.env` lives when no Workspace is open."""
    return Path(__file__).resolve().parent.parent.parent


def _default_config() -> RuntimeConfig:
    """The settings a caller that passed none is implicitly asking for."""
    return resolve_config(env=os.environ, repo_root=_repo_root())


@dataclass(frozen=True)
class Services:
    """Everything a client needs, already wired to one Workspace."""

    workspace: Workspace
    database_url: str
    schema_version: str
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
    settings: SettingsService


def build_object_store(workspace: Workspace, config: RuntimeConfig) -> ObjectStore:
    """Choose the immutable payload backend named by configuration.

    Local is the default and stays the default: a caller that configures
    nothing gets exactly the filesystem behaviour it had, which is what keeps
    the deterministic offline workflow working with no cloud SDK installed.

    The choice is made here, in the composition root, rather than inside
    `PayloadStore`. A store that branched on a backend name internally would
    put the polymorphism in the wrong place - the two implementations already
    differ behind one protocol, and nothing above this line should be able to
    tell which one it got.
    """
    backend = str(config.get("object_store") or "local").strip().lower()
    if backend == "local":
        return LocalObjectStore(workspace.artifacts_root)
    if backend != "s3":
        raise WorkspaceError(f"unknown object store backend: {backend} (expected 'local' or 's3')")
    bucket = config.get("s3_bucket")
    if not bucket:
        raise WorkspaceError("object store 's3' requires a bucket; set CV_S3_BUCKET")
    return S3ObjectStore(
        str(bucket),
        prefix=str(config.get("s3_prefix") or ""),
        endpoint_url=config.get("s3_endpoint_url") or None,
        region_name=config.get("s3_region") or None,
    )


def build_services(
    workspace: Workspace,
    *,
    database_url: str | None = None,
    repository: ApplicationRepository | None = None,
    knowledge: KnowledgeStore | None = None,
    artifacts: ArtifactStore | None = None,
    payloads: RevisionPayloadStore | None = None,
    renderer: Renderer | None = None,
    provider: AIProvider | None = None,
    config: RuntimeConfig | None = None,
) -> Services:
    """The manual composition root.

    The only place that decides which concrete adapter satisfies which port.
    Callers may substitute any of them — that is how tests replace the browser
    and the AI provider without the application layer knowing either exists.
    """
    resolved_config = config or _default_config()
    resolved_database_url = database_url or str(resolved_config.get("database_url"))
    if repository is None:
        engine = create_database_engine(resolved_database_url)
        resolved_repository = Repository(engine)
        schema_version = current_database_revision(engine) or ""
    else:
        resolved_repository = repository
        repository_engine = getattr(repository, "engine", None)
        schema_version = (
            current_database_revision(repository_engine) if repository_engine is not None else None
        ) or ""
    resolved_knowledge = knowledge or FileKnowledge(
        workspace.knowledge_root,
        workspace_root=workspace.root,
        temp_root=workspace.temp_root,
        has_prepared_mutation=lambda: bool(resolved_repository.prepared_knowledge_mutations()),
    )
    resolved_artifacts = artifacts or FilesystemArtifactStore(workspace)
    resolved_payloads = payloads or PayloadStore(
        workspace, build_object_store(workspace, resolved_config)
    )
    resolved_renderer = renderer or PlaywrightRenderer(workspace.knowledge_root)
    # Built only when a key is configured. The deterministic workflow must
    # reach Ready with `OPENAI_API_KEY` unset, so constructing an adapter that
    # refuses at import time would break the offline path for every command,
    # including the ones that never call a provider. `None` here is what the
    # services turn into an explicit refusal when AI mode is *requested*.
    resolved_provider = provider
    api_key = resolved_config.get("openai_api_key")
    if resolved_provider is None and api_key:
        resolved_provider = OpenAIProvider(
            resolved_knowledge.task_contracts(),
            default_model=str(resolved_config.get("model")),
            api_key=str(api_key),
        )
    shared = {
        "repository": resolved_repository,
        "knowledge": resolved_knowledge,
        "artifacts": resolved_artifacts,
        "renderer": resolved_renderer,
        "provider": resolved_provider,
        "snapshots": resolved_payloads,
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
            OperationType.PROPOSE_SELECTION_PLAN: SelectionPlanOperationHandler(analysis_service),
            OperationType.CREATE_DRAFT: DraftOperationHandler(draft_service),
            OperationType.REGENERATE_SECTION: RegenerationOperationHandler(
                draft_service, task="regenerate_section"
            ),
            OperationType.REGENERATE_CLAIM: RegenerationOperationHandler(
                draft_service, task="regenerate_claim"
            ),
            OperationType.RENDER_REVISION: RenderOperationHandler(rendering_service),
        },
        runner_id=f"local-{new_id()}",
        technical_logger=failure_logger.record,
    )
    foreground = ForegroundOperationExecutor(resolved_repository, runner)
    worker = OperationWorker(resolved_repository, runner)
    knowledge_service = KnowledgeService(**shared)
    knowledge_service.recover_knowledge_mutations()
    settings_service = SettingsService(
        resolved_repository, provider_configured=resolved_provider is not None
    )
    return Services(
        workspace=workspace,
        database_url=resolved_database_url,
        schema_version=schema_version,
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
        settings=settings_service,
    )


def build_api_services(
    services: Services,
    *,
    config: RuntimeConfig | None = None,
) -> ApiServices:
    """Narrow `Services` down to what the HTTP layer is allowed to reach.

    `Services` also holds repositories, stores, a renderer, a provider, and the
    Operation worker. A router needs none of those, and being able to reach one
    is how business logic ends up in a router, so the API is handed a container
    that simply does not carry them.

    The worker is deliberately not passed either: `create_app` builds a server,
    and the supervisor hosts the worker.
    """
    max_body_bytes = API_MAX_BODY_BYTES_DEFAULT
    dev_origin: str | None = None
    if config is not None:
        max_body_bytes = int(config.get("api_max_body_bytes"))
        dev_origin = config.get("api_dev_origin")
    return ApiServices(
        applications=services.applications,
        queries=services.queries,
        analysis=services.analysis,
        drafts=services.drafts,
        rendering=services.rendering,
        tracking=services.tracking,
        knowledge=services.knowledge_lifecycle,
        operations=services.operations,
        settings=services.settings,
        identity=InstanceIdentity(
            workspace_id=services.workspace.workspace_id,
            product_version=__version__,
            api_version=API_VERSION,
            schema_version=services.schema_version,
        ),
        limits=ApiLimits(max_body_bytes=max_body_bytes, dev_origin=dev_origin),
    )
