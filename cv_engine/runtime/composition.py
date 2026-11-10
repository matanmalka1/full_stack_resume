from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .. import __version__
from ..api import ApiLimits, ApiServices, InstanceIdentity
from ..api.app import API_VERSION
from ..application.actor import Actor
from ..application.commands import RegenerateClaimCommand, RegenerateSectionCommand
from ..application.operation_runner import OperationRunner
from ..application.operations import OperationType
from ..application.ports import (
    AIProvider,
    Renderer,
)
from ..application.ports.user_knowledge import UserKnowledgeSource
from ..application.services.accounts import AccountService
from ..application.services.ai_calls import AICallRunner
from ..application.services.analysis.activation import AnalysisActivation
from ..application.services.analysis.service import AnalysisService
from ..application.services.applications.intake import ApplicationService
from ..application.services.applications.queries import ApplicationQueryService
from ..application.services.drafts import DraftAuthoringService, DraftEditingService
from ..application.services.drafts.activation import DraftActivation
from ..application.services.drafts.history import DraftHistoryService
from ..application.services.drafts.review import DraftReviewService
from ..application.services.gap_questions import GapQuestionActivation, GapQuestionService
from ..application.services.knowledge import (
    FactLifecycleService,
    KnowledgeQueryService,
)
from ..application.services.knowledge.exporting import KnowledgeExportService
from ..application.services.knowledge.importing import KnowledgeImportService
from ..application.services.maintenance import MaintenanceService
from ..application.services.operations import (
    AnalysisOperationHandler,
    DraftOperationHandler,
    GapFactOperationHandler,
    GapQuestionsOperationHandler,
    OperationLifecycleService,
    OperationSubmissionService,
    RegenerationOperationHandler,
    RenderOperationHandler,
)
from ..application.services.rendering import RenderingService
from ..application.services.settings import SettingsService
from ..infrastructure.database_knowledge import DatabaseKnowledge
from ..infrastructure.document_files import DocumentFiles
from ..infrastructure.knowledge import load_task_contracts
from ..infrastructure.operation_logging import OperationFailureLogger
from ..infrastructure.passwords import Argon2PasswordHasher
from ..infrastructure.persistence import (
    SqlAlchemyTransactionManager,
    create_database_engine,
    current_database_revision,
)
from ..infrastructure.persistence.accounts import SqlAlchemyAccountRepository
from ..infrastructure.persistence.ai_calls import SqlAlchemyAICallLog
from ..infrastructure.persistence.analysis_plans import SqlAlchemyAnalysisPlanRepository
from ..infrastructure.persistence.analysis_sources import SqlAlchemyAnalysisContextSourceReader
from ..infrastructure.persistence.application_projections import (
    SqlAlchemyApplicationProjectionReader,
)
from ..infrastructure.persistence.audit_log import SqlAlchemyAuditLog
from ..infrastructure.persistence.documents import SqlAlchemyDocumentStore
from ..infrastructure.persistence.draft_history_sources import (
    SqlAlchemyDraftHistoryApplicationReader,
)
from ..infrastructure.persistence.gap_questions import SqlAlchemyGapQuestionStore
from ..infrastructure.persistence.intake_application_store import SqlAlchemyApplicationStore
from ..infrastructure.persistence.knowledge_lifecycle import (
    SqlAlchemyKnowledgeLifecycleRepository,
)
from ..infrastructure.persistence.maintenance import SqlAlchemyMaintenanceInspection
from ..infrastructure.persistence.operation_client import SqlAlchemyOperationClientStore
from ..infrastructure.persistence.operation_execution import SqlAlchemyOperationExecutionStore
from ..infrastructure.persistence.settings_store import SqlAlchemySettingsStore
from ..infrastructure.persistence.user_knowledge import SqlAlchemyUserKnowledgeRepository
from ..infrastructure.persistence.worker_lock import worker_exclusivity
from ..infrastructure.providers import OpenAIProvider
from ..infrastructure.rendering import PlaywrightRenderer
from ..util import new_id
from .config import API_MAX_BODY_BYTES_DEFAULT, RuntimeConfig, resolve_config
from .execution import OperationWorker
from .paths import AppPaths


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
    knowledge: UserKnowledgeSource
    applications: ApplicationService
    queries: ApplicationQueryService
    analysis: AnalysisService
    drafts: DraftAuthoringService
    draft_editing: DraftEditingService
    draft_history: DraftHistoryService
    draft_review: DraftReviewService
    rendering: RenderingService
    maintenance: MaintenanceService
    knowledge_lifecycle: FactLifecycleService
    knowledge_queries: KnowledgeQueryService
    operation_submissions: OperationSubmissionService
    operation_lifecycle: OperationLifecycleService
    operation_runner: OperationRunner
    operation_worker: OperationWorker
    settings: SettingsService
    accounts: AccountService
    knowledge_import: KnowledgeImportService
    knowledge_export: KnowledgeExportService
    gap_questions: GapQuestionService


def build_services(
    paths: AppPaths,
    *,
    database_url: str | None = None,
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
    engine = create_database_engine(resolved_database_url)
    schema_version = current_database_revision(engine) or ""
    transactions = SqlAlchemyTransactionManager(engine)
    account_repository = SqlAlchemyAccountRepository(transactions)
    account_service = AccountService(
        transactions,
        account_repository,
        Argon2PasswordHasher(),
        session_days=int(resolved_config.get("session_days")),
    )
    intake_applications = SqlAlchemyApplicationStore(transactions)
    intake_audit = SqlAlchemyAuditLog(transactions)
    knowledge_lifecycle_store = SqlAlchemyKnowledgeLifecycleRepository(transactions)
    user_knowledge = SqlAlchemyUserKnowledgeRepository(transactions)
    # Knowledge is the user's rows; templates and policy are the installation's files.
    resolved_knowledge = DatabaseKnowledge(transactions, user_knowledge, paths.knowledge_root)
    resolved_renderer = renderer or PlaywrightRenderer(paths.knowledge_root)
    # Built only when a key is configured. Constructing an adapter that refuses
    # at import time would break every command, including the ones that never
    # call a provider. `None` here is what the services turn into an explicit
    # refusal when an AI command runs.
    resolved_provider = provider
    api_key = resolved_config.get("openai_api_key")
    if resolved_provider is None and api_key:
        resolved_provider = OpenAIProvider(
            load_task_contracts(paths.knowledge_root),
            default_model=str(resolved_config.get("model")),
            api_key=str(api_key),
        )
    analysis_plans = SqlAlchemyAnalysisPlanRepository(transactions)
    analysis_sources = SqlAlchemyAnalysisContextSourceReader(transactions)
    application_projections = SqlAlchemyApplicationProjectionReader(transactions)
    ai_calls = AICallRunner(transactions=transactions, log=SqlAlchemyAICallLog(transactions))
    operation_client = SqlAlchemyOperationClientStore(transactions)
    operation_execution = SqlAlchemyOperationExecutionStore(transactions)
    knowledge_queries = KnowledgeQueryService(
        transactions=transactions, store=knowledge_lifecycle_store, knowledge=resolved_knowledge
    )
    maintenance_service = MaintenanceService(
        transactions=transactions,
        inspection=SqlAlchemyMaintenanceInspection(transactions),
        knowledge=knowledge_queries,
    )
    documents = SqlAlchemyDocumentStore(transactions)
    document_files = DocumentFiles(paths)
    # One activation per use-case, shared by the service's synchronous path and the
    # Operation handler that activates the same result inside the runner's scope.
    analysis_activation = AnalysisActivation(
        analysis_plans, analysis_sources, documents, SqlAlchemySettingsStore(transactions)
    )
    draft_activation = DraftActivation(documents)
    analysis_service = AnalysisService(
        transactions=transactions,
        activation=analysis_activation,
        sources=analysis_sources,
        documents=documents,
        ai_calls=ai_calls,
        knowledge=resolved_knowledge,
        provider=resolved_provider,
    )
    draft_history = DraftHistoryService(
        transactions=transactions,
        documents=documents,
        sources=analysis_sources,
        applications=SqlAlchemyDraftHistoryApplicationReader(transactions),
        knowledge=resolved_knowledge,
    )
    operation_submissions = OperationSubmissionService(
        transactions=transactions,
        operations=operation_client,
        settings=SqlAlchemySettingsStore(transactions),
        default_ai_model=str(resolved_config.get("model")),
    )
    operation_lifecycle = OperationLifecycleService(
        transactions, operation_client, documents=documents
    )
    draft_editing = DraftEditingService(
        transactions=transactions,
        documents=documents,
        sources=analysis_sources,
        files=document_files,
        knowledge=resolved_knowledge,
    )
    draft_service = DraftAuthoringService(
        transactions=transactions,
        documents=documents,
        sources=analysis_sources,
        knowledge=resolved_knowledge,
        provider=resolved_provider,
        ai_calls=ai_calls,
        renderer=resolved_renderer,
    )
    draft_review = DraftReviewService(
        transactions=transactions,
        documents=documents,
        sources=analysis_sources,
        knowledge=resolved_knowledge,
        audit=intake_audit,
    )
    rendering_service = RenderingService(
        transactions=transactions,
        documents=documents,
        sources=analysis_sources,
        files=document_files,
        knowledge=resolved_knowledge,
        renderer=resolved_renderer,
    )
    knowledge_service = FactLifecycleService(
        transactions=transactions,
        store=knowledge_lifecycle_store,
        knowledge=resolved_knowledge,
        repository=user_knowledge,
        documents=documents,
        sources=analysis_sources,
    )
    gap_store = SqlAlchemyGapQuestionStore(transactions)
    gap_activation = GapQuestionActivation(gap_store, analysis_sources, knowledge_service)
    gap_service = GapQuestionService(
        transactions=transactions,
        store=gap_store,
        analyses=analysis_sources,
        knowledge=resolved_knowledge,
        ai_calls=ai_calls,
        provider=resolved_provider,
        activation=gap_activation,
    )
    failure_logger = OperationFailureLogger(paths.root, paths.logs_root)
    runner = OperationRunner(
        {
            OperationType.RENDER_DOCUMENT: RenderOperationHandler(
                rendering_service, documents, analysis_sources, resolved_knowledge
            ),
            OperationType.CREATE_DRAFT: DraftOperationHandler(
                draft_service, documents, draft_activation
            ),
            OperationType.REGENERATE_SECTION: RegenerationOperationHandler(
                draft_service,
                documents,
                draft_activation,
                command_type=RegenerateSectionCommand,
            ),
            OperationType.REGENERATE_CLAIM: RegenerationOperationHandler(
                draft_service,
                documents,
                draft_activation,
                command_type=RegenerateClaimCommand,
            ),
            OperationType.ANALYZE_JOB: AnalysisOperationHandler(
                analysis_service,
                analysis_sources,
                analysis_activation,
                resolved_knowledge,
                documents,
                continuations=operation_client,
            ),
            OperationType.ASK_GAP_QUESTIONS: GapQuestionsOperationHandler(
                gap_service, gap_activation
            ),
            OperationType.DRAFT_GAP_FACT: GapFactOperationHandler(gap_service, gap_activation),
        },
        transactions=transactions,
        execution_store=operation_execution,
        runner_id=f"local-{new_id()}",
        technical_logger=failure_logger.record,
        operation_failure_logger=failure_logger.record_operation_failure,
        operation_event_logger=failure_logger.record_event,
    )

    def cancel_for_its_owner(operation_id: str) -> object:
        """The worker cancels its own running Operations when it loses its lock. It holds
        only their IDs, so it reads each one's owner the way it reads it on a claim: from
        the database, through the Operation's Application (architecture §18.3)."""
        with transactions.read() as tx:
            owner = operation_execution.operation(tx, operation_id).owner_user_id
        return operation_lifecycle.cancel(Actor(user_id=owner), operation_id)

    worker = OperationWorker(
        runner,
        request_cancellation=cancel_for_its_owner,
        exclusive=lambda: worker_exclusivity(engine),
        concurrency=int(resolved_config.get("worker_concurrency")),
        maintenance=account_service.cleanup_rate_limits,
    )
    settings_service = SettingsService(
        transactions,
        SqlAlchemySettingsStore(transactions),
        provider_configured=resolved_provider is not None,
        runtime_default_model=str(resolved_config.get("model")),
    )
    return Services(
        paths=paths,
        database_url=resolved_database_url,
        schema_version=schema_version,
        knowledge=resolved_knowledge,
        applications=ApplicationService(
            transactions=transactions,
            applications=intake_applications,
            audit=intake_audit,
        ),
        queries=ApplicationQueryService(
            transactions=transactions,
            projections=application_projections,
            documents=documents,
            knowledge=resolved_knowledge,
        ),
        analysis=analysis_service,
        drafts=draft_service,
        draft_editing=draft_editing,
        draft_history=draft_history,
        draft_review=draft_review,
        rendering=rendering_service,
        maintenance=maintenance_service,
        knowledge_lifecycle=knowledge_service,
        knowledge_queries=knowledge_queries,
        operation_submissions=operation_submissions,
        operation_lifecycle=operation_lifecycle,
        operation_runner=runner,
        operation_worker=worker,
        settings=settings_service,
        accounts=account_service,
        knowledge_import=KnowledgeImportService(
            transactions,
            account_repository,
            user_knowledge,
        ),
        knowledge_export=KnowledgeExportService(
            transactions,
            account_repository,
            resolved_knowledge,
        ),
        gap_questions=gap_service,
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
    public_origin: str | None = None
    trusted_proxy_hops = 0
    if config is not None:
        max_body_bytes = config.get("api_max_body_bytes")
        dev_origin = config.get("api_dev_origin")
        public_origin = config.get("api_public_origin")
        trusted_proxy_hops = config.get("trusted_proxy_hops")
    return ApiServices(
        applications=services.applications,
        queries=services.queries,
        analysis=services.analysis,
        drafts=services.drafts,
        draft_editing=services.draft_editing,
        draft_history=services.draft_history,
        draft_review=services.draft_review,
        rendering=services.rendering,
        knowledge=services.knowledge_lifecycle,
        knowledge_queries=services.knowledge_queries,
        operation_submissions=services.operation_submissions,
        operation_lifecycle=services.operation_lifecycle,
        settings=services.settings,
        accounts=services.accounts,
        gap_questions=services.gap_questions,
        identity=InstanceIdentity(
            product_version=__version__,
            api_version=API_VERSION,
            schema_version=services.schema_version,
        ),
        limits=ApiLimits(
            max_body_bytes=max_body_bytes,
            dev_origin=dev_origin,
            public_origin=public_origin,
            trusted_proxy_hops=trusted_proxy_hops,
        ),
    )
