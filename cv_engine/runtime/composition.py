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
from ..application.ports.analysis_plans import AnalysisKnowledgeSource
from ..application.services.analysis import AnalysisService
from ..application.services.applications import ApplicationService
from ..application.services.drafts import DraftAuthoringService
from ..application.services.drafts.approval import DraftApprovalService
from ..application.services.drafts.approval_commit import ApprovalCommitter
from ..application.services.drafts.history import DraftHistoryService
from ..application.services.drafts.selection import SelectionChangeService
from ..application.services.drafts.validation import DraftValidationService
from ..application.services.knowledge import KnowledgeService
from ..application.services.maintenance import MaintenanceService
from ..application.services.operations import (
    AnalysisOperationHandler,
    DraftOperationHandler,
    OperationService,
    RegenerationOperationHandler,
    RenderOperationHandler,
    SelectionPlanOperationHandler,
)
from ..application.services.projections import ApplicationQueryService
from ..application.services.recruitment import RecruitmentService
from ..application.services.rendering import RenderingService
from ..application.services.submission import SubmissionService
from ..application.settings import SettingsService
from ..infrastructure.artifacts import FilesystemArtifactStore
from ..infrastructure.knowledge import FileKnowledge
from ..infrastructure.object_store import LocalObjectStore, ObjectStore, S3ObjectStore
from ..infrastructure.operation_logging import OperationFailureLogger
from ..infrastructure.payloads import PayloadStore
from ..infrastructure.persistence import (
    Repository,
    SqlAlchemyTransactionManager,
    create_database_engine,
    current_database_revision,
)
from ..infrastructure.persistence.analysis_plans import SqlAlchemyAnalysisPlanRepository
from ..infrastructure.persistence.analysis_sources import SqlAlchemyAnalysisSelectionSourceReader
from ..infrastructure.persistence.application_store import SqlAlchemyApplicationStore
from ..infrastructure.persistence.artifact_catalog import SqlAlchemyArtifactCatalog
from ..infrastructure.persistence.audit_log import SqlAlchemyAuditLog
from ..infrastructure.persistence.decision_store import SqlAlchemyDecisionRepository
from ..infrastructure.persistence.draft_approval_sources import SqlAlchemyDraftApprovalSourceReader
from ..infrastructure.persistence.draft_authoring_sources import (
    SqlAlchemyDraftAuthoringSourceReader,
)
from ..infrastructure.persistence.draft_history_sources import (
    SqlAlchemyDraftHistoryApplicationReader,
)
from ..infrastructure.persistence.draft_lifecycle import SqlAlchemyDraftLifecycleRepository
from ..infrastructure.persistence.draft_operation_sources import (
    SqlAlchemyDraftOperationSourceReader,
)
from ..infrastructure.persistence.draft_validation_sources import (
    SqlAlchemyDraftValidationSourceReader,
)
from ..infrastructure.persistence.idempotency import SqlAlchemyIdempotencyRepository
from ..infrastructure.persistence.job_snapshots import SqlAlchemyJobSnapshotStore
from ..infrastructure.persistence.maintenance import SqlAlchemyMaintenanceInspection
from ..infrastructure.persistence.operation_activation import SqlAlchemyOperationActivationStore
from ..infrastructure.persistence.provider_evidence import SqlAlchemyProviderEvidenceStore
from ..infrastructure.persistence.ready_evidence import SqlAlchemyReadyEvidenceReader
from ..infrastructure.persistence.recruitment import SqlAlchemyRecruitmentRepository
from ..infrastructure.persistence.recruitment_store import (
    SqlAlchemyInitialRecruitmentEventWriter,
)
from ..infrastructure.persistence.render_context import SqlAlchemyRenderContextReader
from ..infrastructure.persistence.selection_drafts import SqlAlchemySelectionDraftStore
from ..infrastructure.persistence.submission_context import SqlAlchemySubmissionContextReader
from ..infrastructure.persistence.validation_store import SqlAlchemyValidationRepository
from ..infrastructure.providers import OpenAIProvider
from ..infrastructure.rendering import PlaywrightRenderer
from ..util import new_id
from .config import API_MAX_BODY_BYTES_DEFAULT, RuntimeConfig, resolve_config
from .execution import OperationWorker
from .paths import AppPaths, PathConfigurationError


def _config_for(root: Path) -> RuntimeConfig:
    """The settings a caller that passed none is implicitly asking for.

    Resolved against the root actually in use, not against the installation
    root. Reading `.env` and the project config from one directory while the
    paths point at another is how a test project silently runs on the real
    installation's settings.
    """
    return resolve_config(env=os.environ, project_root=root)


@dataclass(frozen=True)
class Services:
    """Everything a client needs, wired to one fixed application root."""

    paths: AppPaths
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
    drafts: DraftAuthoringService
    draft_validation: DraftValidationService
    draft_history: DraftHistoryService
    draft_approval: DraftApprovalService
    rendering: RenderingService
    recruitment: RecruitmentService
    submission: SubmissionService
    maintenance: MaintenanceService
    knowledge_lifecycle: KnowledgeService
    operations: OperationService
    operation_runner: OperationRunner
    operation_worker: OperationWorker
    settings: SettingsService


def build_object_store(paths: AppPaths, config: RuntimeConfig) -> ObjectStore:
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
        return LocalObjectStore(paths.artifacts_root)
    if backend != "s3":
        raise PathConfigurationError(
            f"unknown object store backend: {backend} (expected 'local' or 's3')"
        )
    bucket = config.get("s3_bucket")
    if not bucket:
        raise PathConfigurationError("object store 's3' requires a bucket; set CV_S3_BUCKET")
    return S3ObjectStore(
        str(bucket),
        prefix=str(config.get("s3_prefix") or ""),
        endpoint_url=config.get("s3_endpoint_url") or None,
        region_name=config.get("s3_region") or None,
    )


def build_services(
    paths: AppPaths,
    *,
    database_url: str | None = None,
    repository: ApplicationRepository | None = None,
    knowledge: KnowledgeStore | None = None,
    activation_knowledge: AnalysisKnowledgeSource | None = None,
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
    resolved_config = config or _config_for(paths.root)
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
        if repository_engine is None:
            raise TypeError("temporary repository substitution must expose its SQLAlchemy engine")
        engine = repository_engine
    transactions = SqlAlchemyTransactionManager(engine)
    intake_applications = SqlAlchemyApplicationStore(transactions)
    intake_snapshots = SqlAlchemyJobSnapshotStore(transactions)
    intake_recruitment = SqlAlchemyInitialRecruitmentEventWriter(transactions)
    intake_audit = SqlAlchemyAuditLog(transactions)
    resolved_knowledge = knowledge or FileKnowledge(
        paths.knowledge_root,
        project_root=paths.root,
        temp_root=paths.temp_root,
        has_prepared_mutation=lambda: bool(resolved_repository.prepared_knowledge_mutations()),
    )
    resolved_artifacts = artifacts or FilesystemArtifactStore(paths)
    resolved_payloads = payloads or PayloadStore(paths, build_object_store(paths, resolved_config))
    resolved_renderer = renderer or PlaywrightRenderer(paths.knowledge_root)
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
    analysis_plans = SqlAlchemyAnalysisPlanRepository(transactions)
    analysis_sources = SqlAlchemyAnalysisSelectionSourceReader(transactions)
    evidence_store = SqlAlchemyProviderEvidenceStore(transactions)
    activation_store = SqlAlchemyOperationActivationStore(transactions)
    # Activation probes recovery state through the runner token. This file-only
    # reader must not invoke the legacy recovery callback and open another DB scope.
    resolved_activation_knowledge = (
        activation_knowledge
        or knowledge
        or FileKnowledge(
            paths.knowledge_root,
            project_root=paths.root,
            temp_root=paths.temp_root,
        )
    )
    analysis_service = AnalysisService(
        transactions=transactions,
        plans=analysis_plans,
        sources=analysis_sources,
        evidence=evidence_store,
        knowledge=resolved_knowledge,
        payloads=resolved_payloads,
        provider=resolved_provider,
    )
    draft_lifecycle = SqlAlchemyDraftLifecycleRepository(transactions)
    draft_catalog = SqlAlchemyArtifactCatalog(transactions)
    draft_decisions = SqlAlchemyDecisionRepository(transactions)
    draft_history = DraftHistoryService(
        transactions=transactions,
        drafts=draft_lifecycle,
        catalog=draft_catalog,
        decisions=draft_decisions,
        audit=intake_audit,
        payloads=resolved_payloads,
        applications=SqlAlchemyDraftHistoryApplicationReader(transactions),
    )
    operation_service = OperationService(
        draft_history=draft_history,
        **shared,
        default_ai_model=str(resolved_config.get("model")),
    )
    draft_validations = SqlAlchemyValidationRepository(transactions)
    draft_receipts = SqlAlchemyIdempotencyRepository(transactions)
    draft_service = DraftAuthoringService(
        transactions=transactions,
        drafts=draft_lifecycle,
        plans=analysis_plans,
        validations=draft_validations,
        sources=SqlAlchemyDraftAuthoringSourceReader(transactions),
        knowledge=resolved_knowledge,
        artifacts=resolved_artifacts,
        provider=resolved_provider,
        evidence=analysis_service,
        selection_changes=SelectionChangeService(
            transactions,
            SqlAlchemySelectionDraftStore(transactions),
            resolved_knowledge,
            resolved_artifacts,
        ),
    )
    draft_validation = DraftValidationService(
        transactions=transactions,
        drafts=draft_lifecycle,
        sources=SqlAlchemyDraftValidationSourceReader(transactions),
        validations=draft_validations,
        knowledge=resolved_knowledge,
    )
    draft_approval = DraftApprovalService(
        transactions=transactions,
        drafts=draft_lifecycle,
        sources=SqlAlchemyDraftApprovalSourceReader(transactions),
        receipts=draft_receipts,
        knowledge=resolved_knowledge,
        artifacts=resolved_artifacts,
        renderer=resolved_renderer,
        payloads=resolved_payloads,
        committer=ApprovalCommitter(
            draft_lifecycle, draft_catalog, draft_decisions, intake_audit, draft_receipts
        ),
    )
    rendering_service = RenderingService(
        transactions=transactions,
        catalog=draft_catalog,
        validations=draft_validations,
        ready_evidence=SqlAlchemyReadyEvidenceReader(transactions),
        contexts=SqlAlchemyRenderContextReader(transactions),
        drafts=draft_lifecycle,
        knowledge=resolved_knowledge,
        renderer=resolved_renderer,
        payloads=resolved_payloads,
    )
    recruitment_store = SqlAlchemyRecruitmentRepository(transactions)
    recruitment_service = RecruitmentService(transactions, recruitment_store, intake_audit)
    submission_service = SubmissionService(
        transactions=transactions,
        contexts=SqlAlchemySubmissionContextReader(transactions),
        recruitment=recruitment_store,
        artifacts=draft_catalog,
        audit=intake_audit,
        ready=rendering_service,
    )
    failure_logger = OperationFailureLogger(paths.root, paths.logs_root)
    draft_operation_sources = SqlAlchemyDraftOperationSourceReader(transactions)
    runner = OperationRunner(
        resolved_repository,
        {},
        transaction_handlers={
            OperationType.RENDER_REVISION: RenderOperationHandler(
                rendering_service, SqlAlchemyRenderContextReader(transactions)
            ),
            OperationType.CREATE_DRAFT: DraftOperationHandler(
                draft_service,
                draft_operation_sources,
                draft_service.activation,
                resolved_activation_knowledge,
            ),
            OperationType.REGENERATE_SECTION: RegenerationOperationHandler(
                draft_service,
                draft_operation_sources,
                draft_service.activation,
                resolved_activation_knowledge,
                task="regenerate_section",
            ),
            OperationType.REGENERATE_CLAIM: RegenerationOperationHandler(
                draft_service,
                draft_operation_sources,
                draft_service.activation,
                resolved_activation_knowledge,
                task="regenerate_claim",
            ),
            OperationType.ANALYZE_JOB: AnalysisOperationHandler(
                analysis_service,
                analysis_sources,
                analysis_service.activation,
                resolved_activation_knowledge,
            ),
            OperationType.PROPOSE_SELECTION_PLAN: SelectionPlanOperationHandler(
                analysis_service,
                analysis_sources,
                analysis_service.activation,
                resolved_activation_knowledge,
            ),
        },
        transactions=transactions,
        activation_store=activation_store,
        runner_id=f"local-{new_id()}",
        technical_logger=failure_logger.record,
        operation_failure_logger=failure_logger.record_operation_failure,
        operation_event_logger=failure_logger.record_event,
    )
    worker = OperationWorker(resolved_repository, runner)
    knowledge_service = KnowledgeService(**shared)
    knowledge_service.recover_knowledge_mutations()
    maintenance_service = MaintenanceService(
        payloads=resolved_payloads,
        transactions=transactions,
        inspection=SqlAlchemyMaintenanceInspection(transactions),
        knowledge=knowledge_service,
    )
    settings_service = SettingsService(
        resolved_repository,
        provider_configured=resolved_provider is not None,
        runtime_default_model=str(resolved_config.get("model")),
    )
    return Services(
        paths=paths,
        database_url=resolved_database_url,
        schema_version=schema_version,
        repository=resolved_repository,
        knowledge=resolved_knowledge,
        artifacts=resolved_artifacts,
        payloads=resolved_payloads,
        unit_of_work=resolved_repository.unit_of_work,
        applications=ApplicationService(
            transactions=transactions,
            applications=intake_applications,
            snapshots=intake_snapshots,
            recruitment=intake_recruitment,
            audit=intake_audit,
            payloads=resolved_payloads,
        ),
        queries=ApplicationQueryService(ready=rendering_service, **shared),
        analysis=analysis_service,
        drafts=draft_service,
        draft_validation=draft_validation,
        draft_history=draft_history,
        draft_approval=draft_approval,
        rendering=rendering_service,
        recruitment=recruitment_service,
        submission=submission_service,
        maintenance=maintenance_service,
        knowledge_lifecycle=knowledge_service,
        operations=operation_service,
        operation_runner=runner,
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
    and the worker runs as its own process.
    """
    max_body_bytes = API_MAX_BODY_BYTES_DEFAULT
    dev_origin: str | None = None
    if config is not None:
        max_body_bytes = config.get("api_max_body_bytes")
        dev_origin = config.get("api_dev_origin")
    return ApiServices(
        applications=services.applications,
        queries=services.queries,
        analysis=services.analysis,
        drafts=services.drafts,
        draft_validation=services.draft_validation,
        draft_history=services.draft_history,
        draft_approval=services.draft_approval,
        rendering=services.rendering,
        recruitment=services.recruitment,
        submission=services.submission,
        knowledge=services.knowledge_lifecycle,
        maintenance=services.maintenance,
        operations=services.operations,
        settings=services.settings,
        identity=InstanceIdentity(
            product_version=__version__,
            api_version=API_VERSION,
            schema_version=services.schema_version,
        ),
        limits=ApiLimits(max_body_bytes=max_body_bytes, dev_origin=dev_origin),
    )
