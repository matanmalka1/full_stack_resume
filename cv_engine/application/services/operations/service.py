"""Submission of durable Operations.

What a submitted Operation *does* lives in `handlers`; this module owns the
record: the frozen sources, the idempotency key, and the `OperationView` every
method narrows to before returning.
"""

from __future__ import annotations

from ....util import new_id
from ...ai_configuration import (
    DEFAULT_AI_MODEL,
    DEFAULT_REASONING_EFFORT,
    ReasoningEffort,
    normalize_ai_model,
    normalize_reasoning_effort,
)
from ...commands import (
    AnalyzeCommand,
    DraftCommand,
    ProposeSelectionCommand,
    RegenerateClaimCommand,
    RegenerateSectionCommand,
    RenderCommand,
)
from ...errors import PreconditionFailed, StateConflict, UnknownRecord
from ...operations import (
    CreateOperation,
    OperationSources,
    OperationType,
    OperationView,
    as_operation_view,
)
from ...ports.operation_client import OperationClientStore
from ...ports.settings import SettingsStore
from ...ports.transactions import TransactionManager
from ..analysis.service import AnalysisService
from ..documents import DocumentSource, refuse_deleted, require_hash
from ..drafts import DraftAuthoringService
from ..rendering import RenderingService
from .common import analysis_knowledge_context_hash


class OperationSubmissionService:
    """Validate and freeze commands before making queued work visible.

    Every method returns `OperationView`, never the runner record. Submission is
    included: a `202` body is the same representation `GET /operations/{id}`
    returns, so a submit that handed back `PersistedOperation` would put the
    payload, the frozen sources, the lease, and the idempotency key into an
    acceptance response. The narrowing is here rather than in each caller,
    because a caller that forgets is exactly how it leaked before.
    """

    def __init__(
        self,
        *,
        default_ai_model: str = DEFAULT_AI_MODEL,
        default_reasoning_effort: str = DEFAULT_REASONING_EFFORT,
        transactions: TransactionManager,
        operations: OperationClientStore,
        settings: SettingsStore,
    ):
        self.transactions = transactions
        self.operations = operations
        self.settings = settings
        self._default_ai_model = normalize_ai_model(default_ai_model)
        self._default_reasoning_effort = normalize_reasoning_effort(default_reasoning_effort)

    def _freeze_ai_execution(self, command):
        """Copy current safe preferences into the immutable Operation payload."""
        with self.transactions.read() as tx:
            stored = self.settings.settings(tx)
        model = normalize_ai_model(
            command.model or stored.default_ai_model or self._default_ai_model
        )
        effort = normalize_reasoning_effort(
            command.reasoning_effort
            or stored.default_reasoning_effort
            or self._default_reasoning_effort
        )
        return command.model_copy(update={"model": model, "reasoning_effort": effort})

    def _load_active_application(self, application_id: str) -> dict[str, object]:
        try:
            with self.transactions.read() as tx:
                application = self.operations.application(tx, application_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown application: {application_id}") from exc
        if application.get("deleted_at") is not None:
            raise StateConflict(f"application is deleted: {application_id}")
        return application

    def _enqueue(
        self, request: CreateOperation, *, operation_id: str | None = None
    ) -> OperationView:
        with self.transactions.write() as tx:
            stored = self.operations.enqueue(tx, request, operation_id=operation_id or new_id())
        return as_operation_view(stored)

    @staticmethod
    def _validated_reasoning_effort(value: str | None) -> ReasoningEffort | None:
        """Keep an absent deterministic effort absent; validate any stored value."""
        return None if value is None else normalize_reasoning_effort(value)

    def submit_analysis(
        self,
        command: AnalyzeCommand,
        *,
        idempotency_key: str,
        analysis_service: AnalysisService,
    ) -> OperationView:
        self._load_active_application(command.application_id)
        command = self._freeze_ai_execution(command)
        snapshot = analysis_service.snapshot_source(command.application_id, command.job_snapshot_id)
        analysis_service.refuse_deleted(snapshot.application_id, snapshot.deleted_at)
        request = CreateOperation(
            application_id=command.application_id,
            operation_type=OperationType.ANALYZE_JOB,
            payload=command.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            sources=OperationSources(
                job_snapshot_id=command.job_snapshot_id,
                job_snapshot_hash=snapshot.source_hash,
                knowledge_context_hash=analysis_knowledge_context_hash(
                    analysis_service.load_knowledge()
                ),
            ),
            provider=command.provider,
            model=command.model,
            reasoning_effort=self._validated_reasoning_effort(command.reasoning_effort),
        )
        return self._enqueue(request)

    def _document_sources(self, source: DocumentSource, expected_document_hash: str):
        """Freeze the document the command was issued against, and what it is pinned to."""
        refuse_deleted(source.document.application_id, source.deleted_at)
        require_hash(source.document, expected_document_hash)
        return OperationSources(
            job_snapshot_id=source.job_snapshot_id,
            job_analysis_id=source.document.analysis_id,
            expected_document_hash=expected_document_hash,
        )

    def submit_draft(
        self,
        command: DraftCommand,
        *,
        idempotency_key: str,
        draft_service: DraftAuthoringService,
        operation_id: str | None = None,
    ) -> OperationView:
        """§14 `create_draft`: queue generation against the document the client read."""
        self._load_active_application(command.application_id)
        command = (
            self._freeze_ai_execution(command)
            if command.provider == "openai"
            else command.model_copy(update={"model": "rules-v1", "reasoning_effort": None})
        )
        source = draft_service.document_source(command.application_id)
        sources = self._document_sources(source, command.expected_document_hash)
        if source.document.content is not None:
            raise PreconditionFailed(
                "the document already has content; edit or regenerate it, or build it "
                "again from its analysis"
            )
        request = CreateOperation(
            application_id=command.application_id,
            operation_type=OperationType.CREATE_DRAFT,
            payload=command.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            sources=sources,
            # The mode the client chose, recorded on the Operation. It also decides
            # whether the AI resource slot is required.
            provider=command.provider,
            model=command.model,
            reasoning_effort=self._validated_reasoning_effort(command.reasoning_effort),
        )
        return self._enqueue(request, operation_id=operation_id)

    def submit_selection_proposal(
        self,
        command: ProposeSelectionCommand,
        *,
        idempotency_key: str,
        analysis_service: AnalysisService,
    ) -> OperationView:
        """§14 `propose_selection`: queue the proposal; no provider call in a request."""
        self._load_active_application(command.application_id)
        command = self._freeze_ai_execution(command)
        source = analysis_service.document_source(command.application_id)
        sources = self._document_sources(source, command.expected_document_hash)
        if source.document.content is not None:
            raise PreconditionFailed(
                "a selection proposal applies only while the document has no content"
            )
        request = CreateOperation(
            application_id=command.application_id,
            operation_type=OperationType.PROPOSE_SELECTION,
            payload=command.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            sources=sources,
            provider="openai",
            model=command.model,
            reasoning_effort=self._validated_reasoning_effort(command.reasoning_effort),
        )
        return self._enqueue(request)

    def submit_regeneration(
        self,
        command: RegenerateSectionCommand | RegenerateClaimCommand,
        *,
        idempotency_key: str,
        draft_service: DraftAuthoringService,
    ) -> OperationView:
        """§14: queue one section or claim regeneration against an exact document hash."""
        self._load_active_application(command.application_id)
        command = self._freeze_ai_execution(command)
        source = draft_service.document_source(command.application_id)
        sources = self._document_sources(source, command.expected_document_hash)
        content = source.document.content
        if content is None:
            raise PreconditionFailed("the document has no content to regenerate yet")
        if isinstance(command, RegenerateSectionCommand):
            if not any(section.name == command.section for section in content.sections):
                raise UnknownRecord(f"unknown section in the document: {command.section}")
        else:
            claim = next(
                (
                    item
                    for section in content.sections
                    for item in section.claims
                    if item.claim_id == command.claim_id
                ),
                None,
            )
            if claim is None:
                raise UnknownRecord(f"unknown claim in the document: {command.claim_id}")
            if command.keep_text and (claim.claim_type != "pending" or not claim.fact_ids):
                raise PreconditionFailed(
                    "only a pending claim linked to at least one fact can have its own "
                    "wording reviewed"
                )
        operation_type = (
            OperationType.REGENERATE_SECTION
            if isinstance(command, RegenerateSectionCommand)
            else OperationType.REGENERATE_CLAIM
        )
        request = CreateOperation(
            application_id=command.application_id,
            operation_type=operation_type,
            payload=command.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            sources=sources,
            provider="openai",
            model=command.model,
            reasoning_effort=self._validated_reasoning_effort(command.reasoning_effort),
        )
        return self._enqueue(request)

    def submit_render(
        self,
        command: RenderCommand,
        *,
        idempotency_key: str,
        rendering_service: RenderingService,
    ) -> OperationView:
        """§16: admit only an approved document with no review reason, then queue."""
        self._load_active_application(command.application_id)
        rendering_service.admit(command)
        request = CreateOperation(
            application_id=command.application_id,
            operation_type=OperationType.RENDER_DOCUMENT,
            payload=command.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            sources=OperationSources(expected_document_hash=command.expected_document_hash),
            provider="deterministic",
            model="playwright",
        )
        return self._enqueue(request)
