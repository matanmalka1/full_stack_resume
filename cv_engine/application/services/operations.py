from __future__ import annotations

from typing import cast

from ...util import canonical_json, sha256_file, sha256_text
from ..commands import AnalyzeCommand, DraftCommand, RenderCommand
from ..errors import InfrastructureFailure, LineageBroken, StateConflict, UnknownRecord
from ..operation_runner import OperationExecutionError, PreparedOperation, SourceChanged
from ..operations import (
    CreateOperation,
    OperationFailureCode,
    OperationOutputReference,
    OperationSources,
    OperationType,
    PersistedOperation,
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

    def check_sources(
        self, operation: PersistedOperation, repository: OperationRepository
    ) -> None:
        sources = operation.sources
        if sources.job_snapshot_id is None or sources.job_snapshot_hash is None:
            raise SourceChanged("Analysis Operation has no frozen job snapshot identity.")
        preparation = cast(PreparationRepository, repository)
        try:
            snapshot = preparation.get_snapshot(sources.job_snapshot_id)
        except KeyError as exc:
            raise SourceChanged("The job snapshot no longer exists.") from exc
        if (
            snapshot["application_id"] != operation.application_id
            or snapshot["source_hash"] != sources.job_snapshot_hash
        ):
            raise SourceChanged("The job snapshot changed before analysis activation.")
        try:
            active_snapshot = preparation.latest_snapshot(operation.application_id)
        except KeyError as exc:
            raise SourceChanged("The Application no longer has an active job snapshot.") from exc
        if active_snapshot["id"] != sources.job_snapshot_id:
            raise SourceChanged("A newer job snapshot replaced the analysis source.")
        if sources.knowledge_context_hash != analysis_knowledge_context_hash(self.service):
            raise SourceChanged("Knowledge changed before analysis activation.")

    def execute(self, operation, cancellation_requested) -> PreparedOperation:
        if cancellation_requested():
            return PreparedOperation()
        return PreparedOperation(value=self.service.prepare(self._command(operation)))

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

    def check_sources(
        self, operation: PersistedOperation, repository: OperationRepository
    ) -> None:
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
        except KeyError as exc:
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

    def check_sources(
        self, operation: PersistedOperation, repository: OperationRepository
    ) -> None:
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
        except (KeyError, OSError, ValueError) as exc:
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
        current_knowledge = sha256_text(
            canonical_json(self.service.load_knowledge().versions())
        )
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
        except KeyError as exc:
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
        except KeyError as exc:
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
        except KeyError as exc:
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

    def cancel(self, operation_id: str) -> PersistedOperation:
        return self.repo.request_operation_cancellation(operation_id)

    def retry(self, operation_id: str, *, idempotency_key: str) -> PersistedOperation:
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
        return self.repo.create_operation(request, installation_id=self.installation_id)

    def get(self, operation_id: str) -> PersistedOperation:
        return self.repo.operation(operation_id)
