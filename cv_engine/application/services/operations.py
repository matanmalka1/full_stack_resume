from __future__ import annotations

from typing import Any, cast

from ...util import canonical_json, new_id, sha256_file, sha256_text
from ..commands import (
    AnalyzeCommand,
    ApprovalResult,
    ApproveDraftCommand,
    DraftCommand,
    ProposeSelectionPlanCommand,
    RegenerateClaimCommand,
    RegenerateSectionCommand,
    RenderCommand,
    ReplaceWorkingDraftCommand,
)
from ..errors import (
    IDEMPOTENCY_KEY_REUSED,
    ApplicationError,
    DependencyUnavailable,
    InfrastructureFailure,
    LineageBroken,
    PreconditionFailed,
    ProposalRejected,
    ProviderInvalidOutput,
    ProviderRateLimited,
    ProviderRefused,
    ProviderSchemaViolation,
    ProviderTimeout,
    ProviderUnavailable,
    StateConflict,
    UnknownRecord,
)
from ..operation_runner import OperationExecutionError, PreparedOperation, SourceChanged
from ..operations import (
    CreateOperation,
    OperationFailureCode,
    OperationOutputReference,
    OperationSources,
    OperationType,
    OperationView,
    PersistedOperation,
    as_operation_view,
    is_terminal_operation,
)
from ..ports import (
    DraftRepository,
    OperationRepository,
    PreparationRepository,
    ReadinessRepository,
)
from .analysis import AnalysisService, PreparedAnalysis, PreparedSelectionProposal
from .base import ServiceBase
from .drafts import DraftService, PreparedDraft, PreparedRegeneration
from .rendering import ExecutedRender, RenderingService


def analysis_knowledge_context_hash(service: AnalysisService) -> str:
    return sha256_text(canonical_json(service.load_knowledge().versions()))


def _model_hash(value) -> str:
    return sha256_text(canonical_json(value.model_dump(mode="json")))


#: How a classified failure becomes an Operation failure code, and therefore
#: whether it is retried. Resolved through the exception's MRO, so a subclass
#: nobody registered inherits its parent's classification rather than falling
#: through to a generic execution failure.
#:
#: Exactly four of these are transient (`TRANSIENT_FAILURE_CODES`), and
#: `allows_automatic_retry` gives each of them one attempt. Everything else -
#: refusal, schema violation, business validation, an unsupported claim, a
#: conflict, a stale source - is terminal on the first failure, which is what
#: test-plan §6 requires. That policy is not restated here; it follows from the
#: code this table chooses.
FAILURE_CODE_BY_ERROR: dict[type[ApplicationError], OperationFailureCode] = {
    ProviderTimeout: OperationFailureCode.PROVIDER_TIMEOUT,
    ProviderRateLimited: OperationFailureCode.PROVIDER_RATE_LIMITED,
    ProviderUnavailable: OperationFailureCode.PROVIDER_UNAVAILABLE,
    ProviderRefused: OperationFailureCode.PROVIDER_REFUSED,
    ProviderSchemaViolation: OperationFailureCode.SCHEMA_VIOLATION,
    ProviderInvalidOutput: OperationFailureCode.INVALID_OUTPUT,
    # A Proposal the engine refused is an invalid output, not a transport
    # failure, and there is no separate code for it: the baseline schema's
    # `failure_code` CHECK is the specification's list, and inventing a
    # twelfth value would be a schema change for a distinction the safe
    # failure detail already carries.
    ProposalRejected: OperationFailureCode.INVALID_OUTPUT,
    DependencyUnavailable: OperationFailureCode.PROVIDER_REFUSED,
    StateConflict: OperationFailureCode.SOURCE_CHANGED,
    LineageBroken: OperationFailureCode.SOURCE_CHANGED,
    PreconditionFailed: OperationFailureCode.VALIDATION_EXECUTION_FAILED,
    InfrastructureFailure: OperationFailureCode.VALIDATION_EXECUTION_FAILED,
}

#: What a client is told about each classification. Deliberately free of the
#: provider's own words: a job description is untrusted input, and a message
#: echoing provider text back into a Problem Details body would carry it out.
_FAILURE_DETAIL: dict[OperationFailureCode, str] = {
    OperationFailureCode.PROVIDER_TIMEOUT: "The AI provider did not answer in time.",
    OperationFailureCode.PROVIDER_RATE_LIMITED: "The AI provider rate limited the request.",
    OperationFailureCode.PROVIDER_UNAVAILABLE: "The AI provider was unavailable.",
    OperationFailureCode.PROVIDER_REFUSED: "The AI provider refused the request.",
    OperationFailureCode.SCHEMA_VIOLATION: "The AI provider returned an invalid schema.",
    OperationFailureCode.INVALID_OUTPUT: "The AI proposal was rejected.",
    OperationFailureCode.SOURCE_CHANGED: "Operation sources changed.",
    OperationFailureCode.VALIDATION_EXECUTION_FAILED: "Operation execution failed.",
}


def failure_code_for(error: ApplicationError) -> OperationFailureCode:
    for cls in type(error).__mro__:
        if cls in FAILURE_CODE_BY_ERROR:
            return FAILURE_CODE_BY_ERROR[cls]
    return OperationFailureCode.VALIDATION_EXECUTION_FAILED


class AITaskHandler:
    """What the three AI-only handlers share: classification and evidence.

    Written once because the alternative is three copies of the same
    `except` ladder, and a fourth task added later would get whichever copy its
    author happened to read.
    """

    service: Any
    task: str

    @staticmethod
    def evidence_outputs(prepared_value: Any) -> tuple[OperationOutputReference, ...]:
        """The provider response an executed AI task produced, as an inactive output.

        Handed to the runner from `execute` rather than returned from `activate`,
        which is what makes it survive a cancellation. The runner records
        `prepared.outputs` as inactive *before* it re-checks cancellation, and
        activates them only inside a successful commit - so a cancelled or
        stale Operation ends holding exactly what §18 says it should: a
        completed output, recorded, inactive.
        """
        evidence = getattr(prepared_value, "evidence", None)
        if evidence is None:
            return ()
        return (
            OperationOutputReference(
                output_type="provider_response",
                output_id=evidence.artifact_version_id,
                active=False,
            ),
        )

    def prepared(self, value: Any) -> PreparedOperation:
        return PreparedOperation(value=value, outputs=self.evidence_outputs(value))

    def _preserve_rejected(self, operation: PersistedOperation, error: ApplicationError) -> None:
        """Record a refused provider answer as inactive immutable evidence.

        Two shapes arrive here. A `ProposalRejected` carries evidence that
        `preserve` already wrote and registered, so only the Operation output
        reference is missing. An adapter-level refusal or schema violation
        carries raw sanitized bytes and nothing else, so the payload is
        committed and registered here - it is the only place those bytes still
        exist.

        Registering the first kind twice would violate `artifact_versions.path`
        UNIQUE, which is the constraint that makes "one payload, one row" a
        property of the schema rather than of this function remembering.

        A failure here is swallowed deliberately. The Operation already has a
        classified failure the user needs to see; replacing that diagnosis with
        an error about storing evidence for it would be a worse report.
        """
        evidence = getattr(error, "evidence", None)
        provenance = getattr(error, "provenance", None)
        try:
            if evidence is not None:
                artifact_version_id = evidence.artifact_version_id
            elif provenance is not None:
                artifact_version_id = self.service.preserve(
                    operation.application_id, operation.id, provenance.task, provenance
                ).artifact_version_id
            else:
                return
            self.service.repo.record_operation_output(
                operation.id,
                "provider_response",
                artifact_version_id,
                active=False,
            )
        except ApplicationError:
            return

    def _classified(
        self, operation: PersistedOperation, error: ApplicationError
    ) -> OperationExecutionError:
        code = failure_code_for(error)
        self._preserve_rejected(operation, error)
        return OperationExecutionError(code, _FAILURE_DETAIL.get(code, "Operation failed."))


class AnalysisOperationHandler(AITaskHandler):
    task = "propose_job_analysis"

    def __init__(self, service: AnalysisService):
        self.service = service

    @staticmethod
    def _command(operation: PersistedOperation) -> AnalyzeCommand:
        return AnalyzeCommand.model_validate(operation.payload)

    def check_sources(self, operation: PersistedOperation, repository: OperationRepository) -> None:
        sources = operation.sources
        if sources.job_snapshot_id is None or sources.job_snapshot_hash is None:
            raise SourceChanged("Analysis Operation has no frozen job snapshot identity.")
        preparation = cast(PreparationRepository, repository)
        try:
            snapshot = preparation.get_snapshot(sources.job_snapshot_id)
        except UnknownRecord as exc:
            raise SourceChanged("The job snapshot no longer exists.") from exc
        if (
            snapshot["application_id"] != operation.application_id
            or snapshot["source_hash"] != sources.job_snapshot_hash
        ):
            raise SourceChanged("The job snapshot changed before analysis activation.")
        try:
            active_snapshot = preparation.latest_snapshot(operation.application_id)
        except UnknownRecord as exc:
            raise SourceChanged("The Application no longer has an active job snapshot.") from exc
        if active_snapshot["id"] != sources.job_snapshot_id:
            raise SourceChanged("A newer job snapshot replaced the analysis source.")
        if sources.knowledge_context_hash != analysis_knowledge_context_hash(self.service):
            raise SourceChanged("Knowledge changed before analysis activation.")

    def execute(self, operation, cancellation_requested) -> PreparedOperation:
        if cancellation_requested():
            return PreparedOperation()
        try:
            return self.prepared(
                self.service.prepare(self._command(operation), operation_id=operation.id)
            )
        except (DependencyUnavailable, InfrastructureFailure, ProposalRejected) as exc:
            raise self._classified(operation, exc) from exc

    def activate(self, operation, prepared, repository):
        if not isinstance(prepared.value, PreparedAnalysis):
            raise TypeError("analysis handler received an invalid prepared value")
        result = self.service.activate(
            self._command(operation),
            prepared.value,
            cast(PreparationRepository, repository),
        )
        return (
            OperationOutputReference(
                output_type="job_analysis", output_id=result.analysis_id, active=True
            ),
            OperationOutputReference(
                output_type="selection_plan",
                output_id=result.selection_plan_id,
                active=True,
            ),
        )


class DraftOperationHandler(AITaskHandler):
    task = "draft_resume"

    def __init__(self, service: DraftService):
        self.service = service

    @staticmethod
    def _command(operation: PersistedOperation) -> DraftCommand:
        return DraftCommand.model_validate(operation.payload)

    def check_sources(self, operation: PersistedOperation, repository: OperationRepository) -> None:
        sources = operation.sources
        if (
            sources.job_snapshot_id is None
            or sources.job_snapshot_hash is None
            or sources.job_analysis_id is None
            or sources.selection_plan_id is None
        ):
            raise SourceChanged("Draft Operation has incomplete frozen source identity.")
        drafts = cast(DraftRepository, repository)
        try:
            snapshot = drafts.get_snapshot(sources.job_snapshot_id)
            analysis = drafts.get_analysis(sources.job_analysis_id)
            plan = drafts.selection_plan(sources.selection_plan_id)
            active_snapshot = drafts.latest_snapshot(operation.application_id)
            active_analysis_id, _ = drafts.latest_analysis(operation.application_id)
            active_plan = drafts.latest_selection_plan(operation.application_id)
        except UnknownRecord as exc:
            raise SourceChanged("A draft source no longer exists.") from exc
        dependencies = sources.dependency_hashes
        if (
            snapshot["application_id"] != operation.application_id
            or snapshot["source_hash"] != sources.job_snapshot_hash
            or active_snapshot["id"] != sources.job_snapshot_id
            or analysis["application_id"] != operation.application_id
            or analysis["job_snapshot_id"] != sources.job_snapshot_id
            or active_analysis_id != sources.job_analysis_id
            or _model_hash(analysis["analysis"]) != dependencies.get("job_analysis")
            or plan.application_id != operation.application_id
            or plan.job_analysis_id != sources.job_analysis_id
            or active_plan.id != sources.selection_plan_id
            or _model_hash(plan) != dependencies.get("selection_plan")
        ):
            raise SourceChanged("Analysis or SelectionPlan changed before draft activation.")
        if sources.knowledge_context_hash != sha256_text(
            canonical_json(self.service.load_knowledge().versions())
        ):
            raise SourceChanged("Knowledge changed before draft activation.")

    def execute(self, operation, cancellation_requested) -> PreparedOperation:
        if cancellation_requested():
            return PreparedOperation()
        try:
            return self.prepared(
                self.service.prepare(self._command(operation), operation_id=operation.id)
            )
        except (DependencyUnavailable, InfrastructureFailure, ProposalRejected) as exc:
            raise self._classified(operation, exc) from exc

    def activate(self, operation, prepared, repository):
        if not isinstance(prepared.value, PreparedDraft):
            raise TypeError("draft handler received an invalid prepared value")
        result = self.service.activate(
            self._command(operation),
            prepared.value,
            cast(DraftRepository, repository),
        )
        return (
            OperationOutputReference(
                output_type="working_draft",
                output_id=result.working_draft_id,
                active=True,
            ),
        )


class SelectionPlanOperationHandler(AITaskHandler):
    """`propose_selection_plan`: the AI branch of §13 `create_selection_plan`."""

    task = "propose_selection_plan"

    def __init__(self, service: AnalysisService):
        self.service = service

    @staticmethod
    def _command(operation: PersistedOperation) -> ProposeSelectionPlanCommand:
        return ProposeSelectionPlanCommand.model_validate(operation.payload)

    def check_sources(self, operation: PersistedOperation, repository: OperationRepository) -> None:
        sources = operation.sources
        if sources.job_analysis_id is None:
            raise SourceChanged("Selection Operation has no frozen analysis identity.")
        preparation = cast(PreparationRepository, repository)
        try:
            analysis = preparation.get_analysis(sources.job_analysis_id)
            active_analysis_id, _ = preparation.latest_analysis(operation.application_id)
        except UnknownRecord as exc:
            raise SourceChanged("The job analysis no longer exists.") from exc
        if (
            analysis["application_id"] != operation.application_id
            or active_analysis_id != sources.job_analysis_id
            or _model_hash(analysis["analysis"]) != sources.dependency_hashes.get("job_analysis")
        ):
            raise SourceChanged("The analysis changed before the plan proposal activated.")
        if sources.knowledge_context_hash != analysis_knowledge_context_hash(self.service):
            raise SourceChanged("Knowledge changed before the plan proposal activated.")

    def execute(self, operation, cancellation_requested) -> PreparedOperation:
        if cancellation_requested():
            return PreparedOperation()
        try:
            return self.prepared(
                self.service.prepare_selection_proposal(
                    self._command(operation), operation_id=operation.id
                )
            )
        except (DependencyUnavailable, InfrastructureFailure, ProposalRejected) as exc:
            raise self._classified(operation, exc) from exc

    def activate(self, operation, prepared, repository):
        del operation
        if not isinstance(prepared.value, PreparedSelectionProposal):
            raise TypeError("selection handler received an invalid prepared value")
        result = self.service.activate_selection_proposal(
            prepared.value,
            cast(PreparationRepository, repository),
        )
        return (
            OperationOutputReference(
                output_type="selection_plan",
                output_id=result.selection_plan_id,
                active=True,
            ),
        )


class RegenerationOperationHandler(AITaskHandler):
    """`regenerate_section` and `regenerate_claim`, which differ only in the command.

    One class for both because their contract is identical: the same frozen
    draft identity, the same source check, the same optimistic commit. Splitting
    them would give two places for the version check to drift apart, and it is
    the version check that stops a regeneration landing on content the user
    edited while it ran.
    """

    def __init__(self, service: DraftService, *, task: str):
        self.service = service
        self.task = task
        self._command_type = (
            RegenerateSectionCommand if task == "regenerate_section" else RegenerateClaimCommand
        )
        self._prepare = (
            service.prepare_section_regeneration
            if task == "regenerate_section"
            else service.prepare_claim_regeneration
        )

    def _command(self, operation: PersistedOperation):
        return self._command_type.model_validate(operation.payload)

    def check_sources(self, operation: PersistedOperation, repository: OperationRepository) -> None:
        sources = operation.sources
        if (
            sources.working_draft_id is None
            or sources.working_draft_edit_version is None
            or sources.working_draft_content_hash is None
        ):
            raise SourceChanged("Regeneration Operation has no frozen draft identity.")
        drafts = cast(DraftRepository, repository)
        try:
            working = drafts.working_draft(sources.working_draft_id)
        except UnknownRecord as exc:
            raise SourceChanged("The working draft no longer exists.") from exc
        if (
            working.application_id != operation.application_id
            or not working.active
            or working.edit_version != sources.working_draft_edit_version
            or working.content_hash != sources.working_draft_content_hash
            or working.job_analysis_id != sources.job_analysis_id
            or working.selection_plan_id != sources.selection_plan_id
        ):
            raise SourceChanged("The working draft changed before regeneration activated.")
        if sources.knowledge_context_hash != sha256_text(
            canonical_json(self.service.load_knowledge().versions())
        ):
            raise SourceChanged("Knowledge changed before regeneration activated.")

    def execute(self, operation, cancellation_requested) -> PreparedOperation:
        if cancellation_requested():
            return PreparedOperation()
        try:
            return self.prepared(self._prepare(self._command(operation), operation_id=operation.id))
        except (
            DependencyUnavailable,
            InfrastructureFailure,
            ProposalRejected,
            StateConflict,
            LineageBroken,
            UnknownRecord,
        ) as exc:
            raise self._classified(operation, exc) from exc

    def activate(self, operation, prepared, repository):
        del operation
        if not isinstance(prepared.value, PreparedRegeneration):
            raise TypeError("regeneration handler received an invalid prepared value")
        result = self.service.activate_regeneration(
            prepared.value,
            cast(DraftRepository, repository),
        )
        return (
            OperationOutputReference(
                output_type="working_draft",
                output_id=result.working_draft_id,
                active=True,
            ),
        )


class RenderOperationHandler:
    def __init__(self, service: RenderingService):
        self.service = service

    @staticmethod
    def _command(operation: PersistedOperation) -> RenderCommand:
        return RenderCommand.model_validate(operation.payload)

    def check_sources(self, operation: PersistedOperation, repository: OperationRepository) -> None:
        sources = operation.sources
        if sources.approved_revision_id is None:
            raise SourceChanged("Render Operation has no frozen ApprovedRevision identity.")
        readiness = cast(ReadinessRepository, repository)
        try:
            revision = readiness.approved_revision(sources.approved_revision_id)
            manifest = readiness.artifact_version_for_revision(
                sources.approved_revision_id, "claim_manifest", "approved"
            )
            snapshot = readiness.get_snapshot(revision.job_snapshot_id)
            analysis = readiness.get_analysis(revision.job_analysis_id)
            plan = readiness.selection_plan(revision.selection_plan_id)
            manifest_path = self.service.artifacts.resolve(manifest["path"])
        except (UnknownRecord, OSError, ValueError) as exc:
            raise SourceChanged("An approved render source is missing or unreadable.") from exc
        dependencies = sources.dependency_hashes
        if (
            revision.application_id != operation.application_id
            or _model_hash(revision) != dependencies.get("approved_revision")
            or snapshot["source_hash"] != sources.job_snapshot_hash
            or analysis["application_id"] != operation.application_id
            or plan.application_id != operation.application_id
            or sha256_file(manifest_path) != manifest["content_hash"]
            or manifest["content_hash"] != dependencies.get("claim_manifest")
        ):
            raise SourceChanged("Approved render inputs changed before activation.")
        current_knowledge = sha256_text(canonical_json(self.service.load_knowledge().versions()))
        if sources.knowledge_context_hash != current_knowledge:
            raise SourceChanged("Knowledge changed before render activation.")

    def execute(self, operation, cancellation_requested) -> PreparedOperation:
        if cancellation_requested():
            return PreparedOperation()
        try:
            prepared = self.service.prepare(self._command(operation))
            executed = self.service.execute(prepared)
        except InfrastructureFailure as exc:
            message = str(exc).casefold()
            code = (
                OperationFailureCode.BROWSER_START_FAILED
                if "browser" in message and "start" in message
                else OperationFailureCode.RENDER_FAILED
            )
            raise OperationExecutionError(code, "Rendering failed.") from exc
        outputs = tuple(
            OperationOutputReference(output_type=output_type, output_id=output_id, active=False)
            for output_type, output_id in zip(
                ("resume_html", "resume_pdf", "visual_evidence"),
                prepared.artifact_ids,
                strict=True,
            )
        )
        failure = (
            None
            if executed.report.passed
            else OperationExecutionError(
                OperationFailureCode.RENDER_FAILED,
                "Rendered output failed validation.",
            )
        )
        return PreparedOperation(
            value=executed,
            outputs=outputs,
            activate_outputs=executed.report.passed,
            terminal_failure=failure,
        )

    def activate(self, operation, prepared, repository):
        del operation
        if not isinstance(prepared.value, ExecutedRender):
            raise TypeError("render handler received an invalid executed value")
        self.service.activate(
            prepared.value,
            cast(ReadinessRepository, repository),
        )
        return ()


class OperationService(ServiceBase[OperationRepository]):
    """Create, cancel, retry, and query durable Operations.

    Every method returns `OperationView`, never the runner record. Submission is
    included: a `202` body is the same representation `GET /operations/{id}`
    returns, so a submit that handed back `PersistedOperation` would put the
    payload, the frozen sources, the lease, and the idempotency key into an
    acceptance response. The narrowing is here rather than in each caller,
    because a caller that forgets is exactly how it leaked before.
    """

    def submit_analysis(
        self,
        command: AnalyzeCommand,
        *,
        idempotency_key: str,
        analysis_service: AnalysisService,
    ) -> OperationView:
        preparation = cast(PreparationRepository, self.repo)
        try:
            snapshot = preparation.get_snapshot(command.job_snapshot_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown job snapshot: {command.job_snapshot_id}") from exc
        if snapshot["application_id"] != command.application_id:
            raise LineageBroken(
                f"job snapshot {command.job_snapshot_id} does not belong to application "
                f"{command.application_id}"
            )
        request = CreateOperation(
            application_id=command.application_id,
            operation_type=OperationType.ANALYZE_JOB,
            payload=command.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            sources=OperationSources(
                job_snapshot_id=command.job_snapshot_id,
                job_snapshot_hash=snapshot["source_hash"],
                knowledge_context_hash=analysis_knowledge_context_hash(analysis_service),
            ),
            provider=command.provider,
            model=command.model,
        )
        return as_operation_view(
            self.repo.create_operation(request, installation_id=self.installation_id)
        )

    def submit_draft(
        self,
        command: DraftCommand,
        *,
        idempotency_key: str,
        draft_service: DraftService,
    ) -> OperationView:
        drafts = cast(DraftRepository, self.repo)
        try:
            analysis = drafts.get_analysis(command.job_analysis_id)
            plan = drafts.selection_plan(command.selection_plan_id)
            snapshot = drafts.get_snapshot(analysis["job_snapshot_id"])
        except UnknownRecord as exc:
            raise UnknownRecord("unknown source for draft generation") from exc
        if (
            analysis["application_id"] != command.application_id
            or plan.application_id != command.application_id
            or plan.job_analysis_id != command.job_analysis_id
        ):
            raise LineageBroken("draft sources do not belong to the named Application")
        knowledge_hash = sha256_text(canonical_json(draft_service.load_knowledge().versions()))
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
            model="rules-v1" if command.provider == "deterministic" else None,
        )
        return as_operation_view(
            self.repo.create_operation(request, installation_id=self.installation_id)
        )

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
        preparation = cast(PreparationRepository, self.repo)
        try:
            analysis = preparation.get_analysis(command.job_analysis_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown job analysis: {command.job_analysis_id}") from exc
        if analysis["application_id"] != command.application_id:
            raise LineageBroken(
                f"job analysis {command.job_analysis_id} does not belong to application "
                f"{command.application_id}"
            )
        request = CreateOperation(
            application_id=command.application_id,
            operation_type=OperationType.PROPOSE_SELECTION_PLAN,
            payload=command.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            sources=OperationSources(
                job_snapshot_id=analysis["job_snapshot_id"],
                job_analysis_id=command.job_analysis_id,
                knowledge_context_hash=analysis_knowledge_context_hash(analysis_service),
                dependency_hashes={"job_analysis": _model_hash(analysis["analysis"])},
            ),
            provider="openai",
            model=command.model,
        )
        return as_operation_view(
            self.repo.create_operation(request, installation_id=self.installation_id)
        )

    def submit_regeneration(
        self,
        command: RegenerateSectionCommand | RegenerateClaimCommand,
        *,
        idempotency_key: str,
        draft_service: DraftService,
    ) -> OperationView:
        """§14: queue one section or claim regeneration against an exact draft.

        The draft's three-part identity goes into the frozen sources, which is
        what the handler's `check_sources` re-checks at activation. The command
        also states the analysis and plan explicitly - `latest` never appears -
        so a regeneration cannot be launched against sources the client did not
        name.
        """
        drafts = cast(DraftRepository, self.repo)
        try:
            working = drafts.working_draft(command.working_draft_id)
            analysis = drafts.get_analysis(command.job_analysis_id)
            plan = drafts.selection_plan(command.selection_plan_id)
        except UnknownRecord as exc:
            raise UnknownRecord("unknown source for regeneration") from exc
        if (
            working.application_id != command.application_id
            or analysis["application_id"] != command.application_id
            or plan.application_id != command.application_id
            or plan.job_analysis_id != command.job_analysis_id
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
                knowledge_context_hash=sha256_text(
                    canonical_json(draft_service.load_knowledge().versions())
                ),
                dependency_hashes={
                    "job_analysis": _model_hash(analysis["analysis"]),
                    "selection_plan": _model_hash(plan),
                },
            ),
            provider="openai",
            model=None,
        )
        return as_operation_view(
            self.repo.create_operation(request, installation_id=self.installation_id)
        )

    def submit_replacement_draft(
        self,
        command: ReplaceWorkingDraftCommand,
        *,
        idempotency_key: str,
        draft_service: DraftService,
    ) -> OperationView:
        """§14 replace: the Keep decision, then the same draft Operation.

        Replacement is generation against an Application that already has an
        active draft, so it queues the same `CREATE_DRAFT` work and inherits its
        frozen sources and `SOURCE_CHANGED` protection rather than growing a
        second path that would have to repeat them. What replacement adds is the
        two things generation has no opinion about: which exact draft version
        the user meant to replace, and whether to keep it.

        `prepare_replacement` is what proves the named draft belongs to the
        named Application before any of that starts.
        """
        draft_service.prepare_replacement(command)
        return self.submit_draft(
            DraftCommand(
                application_id=command.application_id,
                job_analysis_id=command.job_analysis_id,
                selection_plan_id=command.selection_plan_id,
                provider=command.provider,
            ),
            idempotency_key=idempotency_key,
            draft_service=draft_service,
        )

    def submit_render(
        self,
        command: RenderCommand,
        *,
        idempotency_key: str,
        rendering_service: RenderingService,
    ) -> OperationView:
        readiness = cast(ReadinessRepository, self.repo)
        try:
            revision = readiness.approved_revision(command.approved_revision_id)
            manifest = readiness.artifact_version_for_revision(
                command.approved_revision_id, "claim_manifest", "approved"
            )
            snapshot = readiness.get_snapshot(revision.job_snapshot_id)
        except UnknownRecord as exc:
            raise UnknownRecord(
                f"unknown approved revision: {command.approved_revision_id}"
            ) from exc
        if revision.application_id != command.application_id:
            raise LineageBroken("approved revision does not belong to the named Application")
        request = CreateOperation(
            application_id=command.application_id,
            operation_type=OperationType.RENDER_REVISION,
            payload=command.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            sources=OperationSources(
                job_snapshot_id=revision.job_snapshot_id,
                job_snapshot_hash=snapshot["source_hash"],
                job_analysis_id=revision.job_analysis_id,
                selection_plan_id=revision.selection_plan_id,
                approved_revision_id=revision.id,
                knowledge_context_hash=sha256_text(
                    canonical_json(rendering_service.load_knowledge().versions())
                ),
                dependency_hashes={
                    "approved_revision": _model_hash(revision),
                    "claim_manifest": manifest["content_hash"],
                },
            ),
            provider="deterministic",
            model="playwright",
        )
        return as_operation_view(
            self.repo.create_operation(request, installation_id=self.installation_id)
        )

    def cancel(self, operation_id: str) -> OperationView:
        """Cancel queued work outright; ask running work to stop (§19).

        The narrow view is the contract for every client of this service - the
        CLI and the API alike. Only the runner reads the full record, and it
        reads it from the repository rather than from here.
        """
        return as_operation_view(self.repo.request_operation_cancellation(operation_id))

    def _approval_result(self, revision_id: str) -> ApprovalResult | None:
        drafts = cast(DraftRepository, self.repo)
        try:
            revision = drafts.approved_revision(revision_id)
            markdown = drafts.artifact_version_for_revision(
                revision_id, "resume_markdown", "approved"
            )
            manifest = drafts.artifact_version_for_revision(
                revision_id, "claim_manifest", "approved"
            )
            decision = drafts.decision_for_revision(revision_id)
        except UnknownRecord:
            return None
        return ApprovalResult(
            application_id=revision.application_id,
            revision_id=revision.id,
            version=revision.version_number,
            markdown_artifact_version_id=markdown["id"],
            manifest_artifact_version_id=manifest["id"],
            decision_record_id=decision["id"],
        )

    def _approval_payload(self, command: ApproveDraftCommand) -> dict[str, object]:
        """What the idempotency key is a key *for* (§15).

        All three command arguments plus the draft's content hash. The hash is
        not derivable from the other three - it is what the draft actually says
        right now - so without it a key replayed after an edit would look like
        the same request and return a revision of different content.
        """
        drafts = cast(DraftRepository, self.repo)
        try:
            working = drafts.working_draft(command.working_draft_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown working draft: {command.working_draft_id}") from exc
        return {
            "working_draft_id": command.working_draft_id,
            "expected_edit_version": command.expected_edit_version,
            "validation_run_id": command.validation_run_id,
            "content_hash": working.content_hash,
        }

    def approve_idempotent(
        self,
        command: ApproveDraftCommand,
        *,
        idempotency_key: str,
        draft_service: DraftService,
    ) -> ApprovalResult:
        command_type = "approve_draft"
        existing = self.repo.idempotency_receipt(
            command_type,
            idempotency_key,
            installation_id=self.installation_id,
        )
        if existing is not None:
            if existing["payload"].get("working_draft_id") != command.working_draft_id:
                raise StateConflict(
                    "idempotency key already used for another working draft",
                    code=IDEMPOTENCY_KEY_REUSED,
                )
            completed = self._approval_result(existing["reserved_entity_id"])
            if completed is not None:
                if existing["status"] == "pending":
                    self.repo.complete_idempotency_receipt(
                        existing["id"], completed.model_dump(mode="json")
                    )
                return completed
            if existing["payload"] != self._approval_payload(command):
                raise StateConflict(
                    "idempotency key already used for a different draft version",
                    code=IDEMPOTENCY_KEY_REUSED,
                )
            receipt = existing
        else:
            receipt = self.repo.claim_idempotency_receipt(
                command_type,
                idempotency_key,
                self._approval_payload(command),
                installation_id=self.installation_id,
                reserved_entity_id=new_id(),
            )
        try:
            result = draft_service.approve_draft(
                command,
                revision_id=receipt["reserved_entity_id"],
            )
        except ApplicationError:
            recovered = self._approval_result(receipt["reserved_entity_id"])
            if recovered is None:
                raise
            result = recovered
        self.repo.complete_idempotency_receipt(receipt["id"], result.model_dump(mode="json"))
        return result

    def retry(self, operation_id: str, *, idempotency_key: str) -> OperationView:
        """Queue a new Operation carrying `retry_of_operation_id` (§19).

        The original stays immutable, and reusing its idempotency key returns
        the original rather than creating a second attempt.
        """
        original = self.repo.operation(operation_id)
        if not is_terminal_operation(original.status):
            raise StateConflict("only a terminal Operation can be retried")
        request = CreateOperation(
            application_id=original.application_id,
            operation_type=original.operation_type,
            payload=original.payload,
            idempotency_key=idempotency_key,
            sources=original.sources,
            provider=original.provider,
            model=original.model,
            retry_of_operation_id=original.id,
        )
        return as_operation_view(
            self.repo.create_operation(request, installation_id=self.installation_id)
        )

    def get(self, operation_id: str) -> OperationView:
        """Operation status as a query contract (§20), never the runner record."""
        return as_operation_view(self.repo.operation(operation_id))
