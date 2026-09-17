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
from ...chain import draft_source_mismatch
from ...commands import (
    AnalyzeCommand,
    DraftCommand,
    ProposeSelectionPlanCommand,
    RegenerateClaimCommand,
    RegenerateSectionCommand,
    RenderCommand,
)
from ...errors import (
    LineageBroken,
    StateConflict,
    UnknownRecord,
)
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
from ..analysis import AnalysisService
from ..drafts import DraftAuthoringService
from ..rendering import RenderingService
from .common import (
    _model_hash,
    analysis_knowledge_context_hash,
    document_knowledge_context_hash,
)


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

    def submit_draft(
        self,
        command: DraftCommand,
        *,
        idempotency_key: str,
        draft_service: DraftAuthoringService,
        operation_id: str | None = None,
    ) -> OperationView:
        self._load_active_application(command.application_id)
        command = (
            self._freeze_ai_execution(command)
            if command.provider == "openai"
            else command.model_copy(update={"model": "rules-v1", "reasoning_effort": None})
        )
        try:
            analysis = draft_service.analysis_record(command.job_analysis_id)
            plan = draft_service.selection_plan(command.selection_plan_id)
            snapshot = draft_service.snapshot_source(analysis["job_snapshot_id"])
        except UnknownRecord as exc:
            raise UnknownRecord("unknown source for draft generation") from exc
        if (
            draft_source_mismatch(command.application_id, command.job_analysis_id, analysis, plan)
            is not None
        ):
            raise LineageBroken("draft sources do not belong to the named Application")
        if command.parent_revision_id is not None:
            try:
                parent = draft_service.approved_revision(command.parent_revision_id)
            except UnknownRecord as exc:
                raise UnknownRecord(
                    f"unknown parent approved revision: {command.parent_revision_id}"
                ) from exc
            if parent.application_id != command.application_id:
                raise LineageBroken(
                    f"approved revision {parent.id} does not belong to application "
                    f"{command.application_id}"
                )
        knowledge_hash = document_knowledge_context_hash(draft_service)
        # §14: a replacement freezes the identity of the draft it is replacing, so the
        # runner can re-check at activation that the record is still the one the user
        # meant. Generation with nothing to replace freezes none, and the validator on
        # `OperationSources` requires the three fields together or not at all.
        replaced_id: str | None = None
        replaced_version: int | None = None
        replaced_hash: str | None = None
        if command.replaces_working_draft_id is not None:
            existing = draft_service.working_draft(command.replaces_working_draft_id)
            if existing.application_id != command.application_id:
                raise LineageBroken(
                    f"working draft {existing.id} does not belong to application "
                    f"{command.application_id}"
                )
            if existing.edit_version != command.replaces_expected_edit_version:
                raise StateConflict(
                    f"working draft {existing.id} is at edit version "
                    f"{existing.edit_version}, not {command.replaces_expected_edit_version}"
                )
            replaced_id = existing.id
            replaced_version = existing.edit_version
            replaced_hash = existing.content_hash
        request = CreateOperation(
            application_id=command.application_id,
            operation_type=OperationType.CREATE_DRAFT,
            payload=command.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            sources=OperationSources(
                job_snapshot_id=snapshot["id"],
                job_snapshot_hash=snapshot["source_hash"],
                job_analysis_id=command.job_analysis_id,
                selection_plan_id=command.selection_plan_id,
                knowledge_context_hash=knowledge_hash,
                working_draft_id=replaced_id,
                working_draft_edit_version=replaced_version,
                working_draft_content_hash=replaced_hash,
                dependency_hashes={
                    "job_analysis": _model_hash(analysis["analysis"]),
                    "selection_plan": _model_hash(plan),
                },
            ),
            # The mode the client chose, recorded on the Operation. It also
            # decides whether the AI resource slot is required, which
            # `required_operation_resources` derives from these two fields
            # rather than from a second list of AI operation types.
            provider=command.provider,
            model=command.model,
            reasoning_effort=self._validated_reasoning_effort(command.reasoning_effort),
        )
        return self._enqueue(request, operation_id=operation_id)

    def submit_selection_plan_proposal(
        self,
        command: ProposeSelectionPlanCommand,
        *,
        idempotency_key: str,
        analysis_service: AnalysisService,
    ) -> OperationView:
        """§13, AI mode: queue the proposal; no provider call in a request.

        The analysis is frozen with its content hash, so a review decision that
        replaces the analysis while this is queued fails the source check
        instead of proposing a plan for an analysis nobody is looking at.
        """
        self._load_active_application(command.application_id)
        command = self._freeze_ai_execution(command)
        source = analysis_service.selection_source(command.application_id, command.job_analysis_id)
        analysis_service.refuse_deleted(source.application_id, source.deleted_at)
        # A caller that omitted an expectation gets the current compatible pointer frozen
        # here. An HTTP client that stated one - including explicit `null` for no plan -
        # keeps exactly that expectation. Deferring a mismatch to the Operation's source
        # check preserves idempotent replay: the same key and payload can still return its
        # original terminal Operation after that Operation itself changed the active plan.
        expected_plan_id = command.expected_selection_plan_id
        if not command.enforce_expected_selection_plan:
            expected_plan_id = source.active_plan.id if source.active_plan is not None else None
        command = command.model_copy(
            update={
                "expected_selection_plan_id": expected_plan_id,
                "enforce_expected_selection_plan": True,
            }
        )
        request = CreateOperation(
            application_id=command.application_id,
            operation_type=OperationType.PROPOSE_SELECTION_PLAN,
            payload=command.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            sources=OperationSources(
                job_snapshot_id=source.job_snapshot_id,
                job_analysis_id=command.job_analysis_id,
                # Building a plan reads no requirement concepts: it consumes the
                # analysis, which is already frozen in `dependency_hashes`.
                knowledge_context_hash=document_knowledge_context_hash(analysis_service),
                dependency_hashes={"job_analysis": _model_hash(source.analysis)},
            ),
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
        """§14: queue one section or claim regeneration against an exact draft.

        The draft's three-part identity goes into the frozen sources, which is
        what the handler's `check_sources` re-checks at activation. The command
        also states the analysis and plan explicitly - `latest` never appears -
        so a regeneration cannot be launched against sources the client did not
        name.
        """
        self._load_active_application(command.application_id)
        command = self._freeze_ai_execution(command)
        try:
            working = draft_service.working_draft(command.working_draft_id)
            analysis = draft_service.analysis_record(command.job_analysis_id)
            plan = draft_service.selection_plan(command.selection_plan_id)
        except UnknownRecord as exc:
            raise UnknownRecord("unknown source for regeneration") from exc
        if (
            working.application_id != command.application_id
            or draft_source_mismatch(
                command.application_id, command.job_analysis_id, analysis, plan
            )
            is not None
        ):
            raise LineageBroken("regeneration sources do not belong to the named Application")
        if working.edit_version != command.expected_edit_version:
            raise StateConflict(
                f"working draft {working.id} is at edit version {working.edit_version}, "
                f"not {command.expected_edit_version}"
            )
        if working.content_hash != command.expected_content_hash:
            raise StateConflict(
                f"working draft {working.id} has content hash {working.content_hash}, "
                f"not {command.expected_content_hash}"
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
            sources=OperationSources(
                job_analysis_id=command.job_analysis_id,
                selection_plan_id=command.selection_plan_id,
                working_draft_id=working.id,
                working_draft_edit_version=working.edit_version,
                working_draft_content_hash=working.content_hash,
                knowledge_context_hash=document_knowledge_context_hash(draft_service),
                dependency_hashes={
                    "job_analysis": _model_hash(analysis["analysis"]),
                    "selection_plan": _model_hash(plan),
                },
            ),
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
        self._load_active_application(command.application_id)
        try:
            sources = rendering_service.freeze_operation_sources(
                command, document_knowledge_context_hash(rendering_service)
            )
        except UnknownRecord as exc:
            raise UnknownRecord(
                f"unknown approved revision: {command.approved_revision_id}"
            ) from exc
        request = CreateOperation(
            application_id=command.application_id,
            operation_type=OperationType.RENDER_REVISION,
            payload=command.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            sources=sources,
            provider="deterministic",
            model="playwright",
        )
        return self._enqueue(request)
