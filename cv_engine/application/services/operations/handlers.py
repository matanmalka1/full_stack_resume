"""One handler per Operation type: check sources, execute, activate.

The runner owns the lifecycle; these own what a given Operation type means.
Adding an Operation type is a change to this module and to the composition
root's handler table, and to nothing else.
"""

from __future__ import annotations

from typing import Any, cast

from ...commands import (
    AnalyzeCommand,
    DraftCommand,
    ProposeSelectionPlanCommand,
    RegenerateClaimCommand,
    RegenerateSectionCommand,
    RenderCommand,
)
from ...errors import (
    ApplicationError,
    DependencyUnavailable,
    InfrastructureFailure,
    LineageBroken,
    MissingFactRendering,
    ProposalRejected,
    StateConflict,
    UnknownRecord,
)
from ...operation_runner import OperationExecutionError, PreparedOperation, SourceChanged
from ...operations import (
    OperationFailureCode,
    OperationOutputReference,
    PersistedOperation,
)
from ...ports import (
    DraftRepository,
    OperationRepository,
    PreparationRepository,
    ReadinessRepository,
)
from ..analysis import AnalysisService, PreparedAnalysis, PreparedSelectionProposal
from ..drafts import DraftService, PreparedDraft, PreparedRegeneration
from ..rendering import ExecutedRender, RenderingService
from .common import (
    _model_hash,
    analysis_knowledge_context_hash,
    document_knowledge_context_hash,
)
from .failures import failure_code_for, safe_failure_detail_for


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
        return OperationExecutionError(code, safe_failure_detail_for(error))


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
        except (
            DependencyUnavailable,
            InfrastructureFailure,
            MissingFactRendering,
            ProposalRejected,
        ) as exc:
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
        # §14: a replacement froze the identity of the draft it is replacing, and that
        # record is a source like any other. Without this the check above validated every
        # input to *generating* the document and nothing about the one being overwritten,
        # so an edit or an archive landing between the `202` and this point was not seen:
        # the edit was overwritten, and the archive turned the replacement into a brand
        # new draft with a new id.
        if sources.working_draft_id is not None:
            try:
                replaced = drafts.working_draft(sources.working_draft_id)
            except UnknownRecord as exc:
                raise SourceChanged("The working draft being replaced no longer exists.") from exc
            if (
                replaced.application_id != operation.application_id
                or not replaced.active
                or replaced.edit_version != sources.working_draft_edit_version
                or replaced.content_hash != sources.working_draft_content_hash
            ):
                raise SourceChanged("The working draft changed before the replacement activated.")
        if sources.knowledge_context_hash != document_knowledge_context_hash(self.service):
            raise SourceChanged("Knowledge changed before draft activation.")

    def execute(self, operation, cancellation_requested) -> PreparedOperation:
        if cancellation_requested():
            return PreparedOperation()
        try:
            return self.prepared(
                self.service.prepare(self._command(operation), operation_id=operation.id)
            )
        except (
            DependencyUnavailable,
            InfrastructureFailure,
            MissingFactRendering,
            ProposalRejected,
        ) as exc:
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
        if sources.knowledge_context_hash != document_knowledge_context_hash(self.service):
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
        except (
            DependencyUnavailable,
            InfrastructureFailure,
            MissingFactRendering,
            ProposalRejected,
        ) as exc:
            raise self._classified(operation, exc) from exc

    def activate(self, operation, prepared, repository):
        if not isinstance(prepared.value, PreparedSelectionProposal):
            raise TypeError("selection handler received an invalid prepared value")
        try:
            result = self.service.activate_selection_proposal(
                prepared.value,
                cast(PreparationRepository, repository),
            )
        except MissingFactRendering as exc:
            raise self._classified(operation, exc) from exc
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
        if sources.knowledge_context_hash != document_knowledge_context_hash(self.service):
            raise SourceChanged("Knowledge changed before regeneration activated.")

    def execute(self, operation, cancellation_requested) -> PreparedOperation:
        if cancellation_requested():
            return PreparedOperation()
        try:
            command = self._command(operation)
            if isinstance(command, RegenerateSectionCommand):
                result = self.service.prepare_section_regeneration(
                    command, operation_id=operation.id
                )
            elif isinstance(command, RegenerateClaimCommand):
                result = self.service.prepare_claim_regeneration(command, operation_id=operation.id)
            else:
                raise TypeError("regeneration handler parsed an invalid command")
            return self.prepared(result)
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
        except (UnknownRecord, OSError, ValueError) as exc:
            raise SourceChanged("An approved render source is missing or unreadable.") from exc
        dependencies = sources.dependency_hashes
        if (
            revision.application_id != operation.application_id
            or _model_hash(revision) != dependencies.get("approved_revision")
            or snapshot["source_hash"] != sources.job_snapshot_hash
            or analysis["application_id"] != operation.application_id
            or plan.application_id != operation.application_id
            # The manifest is a registered immutable payload: verifying it
            # through the store checks the bytes storage holds, where hashing a
            # resolved local path checked the filesystem no matter where the
            # payload actually lives.
            or self.service.snapshot_payloads.verify_payload(
                manifest["path"], manifest["content_hash"]
            )
            != "ok"
            or manifest["content_hash"] != dependencies.get("claim_manifest")
        ):
            raise SourceChanged("Approved render inputs changed before activation.")
        current_knowledge = document_knowledge_context_hash(self.service)
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
