from __future__ import annotations

from typing import cast

from ...util import canonical_json, new_id, sha256_file, sha256_text
from ..commands import AnalyzeCommand, ApprovalResult, DraftCommand, RenderCommand
from ..errors import (
    IDEMPOTENCY_KEY_REUSED,
    ApplicationError,
    DependencyUnavailable,
    InfrastructureFailure,
    LineageBroken,
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
from .analysis import AnalysisService, PreparedAnalysis
from .base import ServiceBase
from .drafts import DraftService, PreparedDraft
from .rendering import ExecutedRender, RenderingService


def analysis_knowledge_context_hash(service: AnalysisService) -> str:
    return sha256_text(canonical_json(service.load_knowledge().versions()))


def _model_hash(value) -> str:
    return sha256_text(canonical_json(value.model_dump(mode="json")))


class AnalysisOperationHandler:
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
            return PreparedOperation(value=self.service.prepare(self._command(operation)))
        except DependencyUnavailable as exc:
            raise OperationExecutionError(
                OperationFailureCode.PROVIDER_REFUSED,
                "The requested provider is not configured.",
            ) from exc
        except InfrastructureFailure as exc:
            message = str(exc).casefold()
            if operation.provider in (None, "deterministic"):
                code = OperationFailureCode.VALIDATION_EXECUTION_FAILED
            elif "429" in message or "rate limit" in message:
                code = OperationFailureCode.PROVIDER_RATE_LIMITED
            elif "timeout" in message or "timed out" in message:
                code = OperationFailureCode.PROVIDER_TIMEOUT
            elif "http 5" in message or "request failed" in message:
                code = OperationFailureCode.PROVIDER_UNAVAILABLE
            elif "invalid provider structured output" in message:
                code = OperationFailureCode.INVALID_OUTPUT
            else:
                code = OperationFailureCode.PROVIDER_REFUSED
            raise OperationExecutionError(code, "Analysis provider failed.") from exc

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


class DraftOperationHandler:
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
        return PreparedOperation(value=self.service.prepare(self._command(operation)))

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
    """Create, cancel, retry, and query durable Operations."""

    def submit_analysis(
        self,
        command: AnalyzeCommand,
        *,
        idempotency_key: str,
        analysis_service: AnalysisService,
    ) -> PersistedOperation:
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
        return self.repo.create_operation(request, installation_id=self.installation_id)

    def submit_draft(
        self,
        command: DraftCommand,
        *,
        idempotency_key: str,
        draft_service: DraftService,
    ) -> PersistedOperation:
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
            provider="deterministic",
            model="rules-v1",
        )
        return self.repo.create_operation(request, installation_id=self.installation_id)

    def submit_render(
        self,
        command: RenderCommand,
        *,
        idempotency_key: str,
        rendering_service: RenderingService,
    ) -> PersistedOperation:
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
        return self.repo.create_operation(request, installation_id=self.installation_id)

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

    def approve_idempotent(
        self,
        application_id: str,
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
            if existing["payload"].get("application_id") != application_id:
                raise StateConflict(
                    "idempotency key already used for another application",
                    code=IDEMPOTENCY_KEY_REUSED,
                )
            completed = self._approval_result(existing["reserved_entity_id"])
            if completed is not None:
                if existing["status"] == "pending":
                    self.repo.complete_idempotency_receipt(
                        existing["id"], completed.model_dump(mode="json")
                    )
                return completed
            payload = existing["payload"]
            try:
                working = cast(DraftRepository, self.repo).active_working_draft(application_id)
            except UnknownRecord as exc:
                raise StateConflict("pending approval has no recoverable WorkingDraft") from exc
            if payload != {
                "application_id": application_id,
                "working_draft_id": working.id,
                "edit_version": working.edit_version,
                "content_hash": working.content_hash,
            }:
                raise StateConflict(
                    "idempotency key already used for a different draft version",
                    code=IDEMPOTENCY_KEY_REUSED,
                )
            receipt = existing
        else:
            try:
                working = cast(DraftRepository, self.repo).active_working_draft(application_id)
            except UnknownRecord as exc:
                raise UnknownRecord(f"no working draft for application: {application_id}") from exc
            payload = {
                "application_id": application_id,
                "working_draft_id": working.id,
                "edit_version": working.edit_version,
                "content_hash": working.content_hash,
            }
            receipt = self.repo.claim_idempotency_receipt(
                command_type,
                idempotency_key,
                payload,
                installation_id=self.installation_id,
                reserved_entity_id=new_id(),
            )
        try:
            result = draft_service.approve(
                application_id,
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
