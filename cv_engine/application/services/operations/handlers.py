"""One handler per Operation type: check sources, execute, activate.

The runner owns the lifecycle; these own what a given Operation type means.
Adding an Operation type is a change to this module and to the composition
root's handler table, and to nothing else.
"""

from __future__ import annotations

from dataclasses import fields
from typing import Any

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
    ApplicationError,
    DependencyUnavailable,
    InfrastructureFailure,
    KnowledgeRejected,
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
from ...ports.analysis_plans import AnalysisKnowledgeSource, AnalysisSelectionSourceReader
from ...ports.draft_operations import DraftOperationSourceReader
from ...ports.rendering import RenderContextReader
from ...ports.transactions import ReadTransaction, WriteTransaction
from ..analysis import (
    AnalysisService,
    PreparedAnalysis,
    PreparedSelectionProposal,
    load_analysis_knowledge,
)
from ..analysis_activation import AnalysisActivation
from ..drafts import DraftAuthoringService, PreparedDraft, PreparedRegeneration
from ..drafts.activation import DraftActivation
from ..proposals import ProviderEvidence
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

    def after_activation(self, operation: PersistedOperation, prepared: PreparedOperation) -> None:
        pass

    def verify_external_sources(self, operation: PersistedOperation) -> None:
        del operation

    @classmethod
    def evidence_outputs(cls, prepared_value: Any) -> tuple[OperationOutputReference, ...]:
        """Every provider response an executed AI task produced, as inactive outputs.

        Handed to the runner from `execute` rather than returned from `activate`,
        which is what makes it survive a cancellation. The runner records
        `prepared.outputs` as inactive *before* it re-checks cancellation, and
        activates them only inside a successful commit - so a cancelled or
        stale Operation ends holding exactly what §18 says it should: every
        completed output, recorded, inactive.
        """
        return tuple(
            OperationOutputReference(
                output_type="provider_response",
                output_id=evidence.artifact_version_id,
                active=False,
            )
            for field in fields(prepared_value)
            for evidence in (getattr(prepared_value, field.name),)
            if isinstance(evidence, ProviderEvidence)
        )

    def prepared(self, value: Any) -> PreparedOperation:
        return PreparedOperation(value=value, outputs=self.evidence_outputs(value))

    def _preserve_rejected(
        self, operation: PersistedOperation, error: ApplicationError
    ) -> tuple[OperationOutputReference, ...]:
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
        # Earlier successful calls survive a later call's failure too.
        completed = getattr(error, "completed_evidence", ())
        evidence = getattr(error, "evidence", None)
        provenance = getattr(error, "provenance", None)
        outputs = [
            OperationOutputReference(
                output_type="provider_response", output_id=item.artifact_version_id, active=False
            )
            for item in completed
        ]
        try:
            if evidence is not None and any(
                item.artifact_version_id == evidence.artifact_version_id for item in completed
            ):
                return tuple(outputs)
            if evidence is not None:
                artifact_version_id = evidence.artifact_version_id
            elif provenance is not None:
                artifact_version_id = self.service.preserve(
                    operation.application_id, operation.id, provenance.task, provenance
                ).artifact_version_id
            else:
                return tuple(outputs)
            outputs.append(
                OperationOutputReference(
                    output_type="provider_response", output_id=artifact_version_id, active=False
                )
            )
        except ApplicationError:
            pass
        return tuple(outputs)

    def _classified(
        self, operation: PersistedOperation, error: ApplicationError
    ) -> OperationExecutionError:
        code = failure_code_for(error)
        outputs = self._preserve_rejected(operation, error)
        return OperationExecutionError(code, safe_failure_detail_for(error), outputs=outputs)


class RegisteredEvidenceTaskHandler(AITaskHandler):
    """AI task whose service registers provider evidence before activation."""

    service: Any
    knowledge: AnalysisKnowledgeSource

    def load_knowledge(self):
        return load_analysis_knowledge(self.knowledge)

    def _preserve_rejected(
        self, operation: PersistedOperation, error: ApplicationError
    ) -> tuple[OperationOutputReference, ...]:
        # Completed evidence already includes its durable inactive output registration.
        if getattr(error, "evidence", None) is not None or getattr(error, "completed_evidence", ()):
            return ()
        provenance = getattr(error, "provenance", None)
        if provenance is not None:
            try:
                evidence = self.service.preserve(
                    operation.application_id, operation.id, provenance.task, provenance
                )
                return (
                    OperationOutputReference(
                        output_type="provider_response",
                        output_id=evidence.artifact_version_id,
                        active=False,
                    ),
                )
            except ApplicationError:
                return ()
        return ()


class AnalysisTaskHandler(RegisteredEvidenceTaskHandler):
    service: AnalysisService
    sources: AnalysisSelectionSourceReader


class AnalysisOperationHandler(AnalysisTaskHandler):
    task = "propose_analysis"

    def __init__(
        self,
        service: AnalysisService,
        sources: AnalysisSelectionSourceReader,
        activation: AnalysisActivation,
        knowledge: AnalysisKnowledgeSource,
    ):
        self.service = service
        self.sources = sources
        self.activation = activation
        self.knowledge = knowledge

    @staticmethod
    def _command(operation: PersistedOperation) -> AnalyzeCommand:
        return AnalyzeCommand.model_validate(operation.payload)

    def verify_sources(self, tx: ReadTransaction, operation: PersistedOperation) -> None:
        sources = operation.sources
        if sources.job_snapshot_id is None or sources.job_snapshot_hash is None:
            raise SourceChanged("Analysis Operation has no frozen job snapshot identity.")
        try:
            snapshot = self.sources.analysis_source(tx, sources.job_snapshot_id)
        except UnknownRecord as exc:
            raise SourceChanged("The job snapshot no longer exists.") from exc
        if (
            snapshot.application_id != operation.application_id
            or snapshot.source_hash != sources.job_snapshot_hash
        ):
            raise SourceChanged("The job snapshot changed before analysis activation.")
        if snapshot.deleted_at is not None:
            raise SourceChanged("The Application was deleted before analysis activation.")
        if snapshot.active_snapshot_id != sources.job_snapshot_id:
            raise SourceChanged("A newer job snapshot replaced the analysis source.")

        if self.sources.knowledge_is_prepared(tx):
            raise KnowledgeRejected("Knowledge has an uncommitted prepared mutation")
        if operation.sources.knowledge_context_hash != analysis_knowledge_context_hash(
            self.load_knowledge()
        ):
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

    def activate(self, tx: WriteTransaction, operation, prepared):
        if not isinstance(prepared.value, PreparedAnalysis):
            raise TypeError("analysis handler received an invalid prepared value")
        result = self.activation.activate(tx, self._command(operation), prepared.value)
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


class DraftTaskHandler(RegisteredEvidenceTaskHandler):
    service: DraftAuthoringService
    knowledge: AnalysisKnowledgeSource

    sources: DraftOperationSourceReader

    def verify_knowledge(self, tx: ReadTransaction, _operation: PersistedOperation) -> None:
        if self.sources.knowledge_is_prepared(tx):
            raise KnowledgeRejected("Knowledge has an uncommitted prepared mutation")

    def verify_external_sources(self, operation: PersistedOperation) -> None:
        if operation.sources.knowledge_context_hash != document_knowledge_context_hash(self):
            raise SourceChanged("Knowledge changed before draft activation.")

    def after_activation(self, operation: PersistedOperation, prepared: PreparedOperation) -> None:
        del operation
        if isinstance(prepared.value, (PreparedDraft, PreparedRegeneration)):
            self.service.store_working_draft(prepared.value.source)


class DraftOperationHandler(DraftTaskHandler):
    task = "draft_resume"

    def __init__(
        self,
        service: DraftAuthoringService,
        sources: DraftOperationSourceReader,
        activation: DraftActivation,
        knowledge: AnalysisKnowledgeSource,
    ):
        self.service = service
        self.sources = sources
        self.activation = activation
        self.knowledge = knowledge

    @staticmethod
    def _command(operation: PersistedOperation) -> DraftCommand:
        return DraftCommand.model_validate(operation.payload)

    def verify_sources(self, tx: ReadTransaction, operation: PersistedOperation) -> None:
        sources = operation.sources
        if (
            sources.job_snapshot_id is None
            or sources.job_snapshot_hash is None
            or sources.job_analysis_id is None
            or sources.selection_plan_id is None
        ):
            raise SourceChanged("Draft Operation has incomplete frozen source identity.")
        try:
            current = self.sources.generation_sources(tx, operation)
            snapshot = current.snapshot
            analysis = current.analysis
            plan = current.plan
            active_snapshot = {"id": current.active_snapshot_id}
            active_analysis_id = current.active_analysis_id
        except UnknownRecord as exc:
            raise SourceChanged("A draft source no longer exists.") from exc
        dependencies = sources.dependency_hashes
        if (
            snapshot["application_id"] != operation.application_id
            or snapshot["source_hash"] != sources.job_snapshot_hash
            or active_snapshot["id"] != sources.job_snapshot_id
            or draft_source_mismatch(
                operation.application_id, sources.job_analysis_id, analysis, plan
            )
            is not None
            or analysis["job_snapshot_id"] != sources.job_snapshot_id
            or active_analysis_id != sources.job_analysis_id
            or _model_hash(analysis["analysis"]) != dependencies.get("job_analysis")
            or current.active_plan_id != sources.selection_plan_id
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
                replaced = current.replaced
                if replaced is None:
                    raise UnknownRecord(sources.working_draft_id)
            except UnknownRecord as exc:
                raise SourceChanged("The working draft being replaced no longer exists.") from exc
            if (
                replaced.application_id != operation.application_id
                or not replaced.active
                or replaced.edit_version != sources.working_draft_edit_version
                or replaced.content_hash != sources.working_draft_content_hash
            ):
                raise SourceChanged("The working draft changed before the replacement activated.")
        self.verify_knowledge(tx, operation)

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

    def activate(self, tx: WriteTransaction, operation, prepared):
        if not isinstance(prepared.value, PreparedDraft):
            raise TypeError("draft handler received an invalid prepared value")
        result = self.activation.activate_generation(
            tx,
            self._command(operation),
            prepared.value,
        )
        return (
            OperationOutputReference(
                output_type="working_draft",
                output_id=result.working_draft_id,
                active=True,
            ),
        )


class SelectionPlanOperationHandler(AnalysisTaskHandler):
    """`propose_selection_plan`: the AI branch of §13 `create_selection_plan`."""

    task = "propose_selection_plan"

    def __init__(
        self,
        service: AnalysisService,
        sources: AnalysisSelectionSourceReader,
        activation: AnalysisActivation,
        knowledge: AnalysisKnowledgeSource,
    ):
        self.service = service
        self.sources = sources
        self.activation = activation
        self.knowledge = knowledge

    @staticmethod
    def _command(operation: PersistedOperation) -> ProposeSelectionPlanCommand:
        return ProposeSelectionPlanCommand.model_validate(operation.payload)

    def verify_sources(self, tx: ReadTransaction, operation: PersistedOperation) -> None:
        command = self._command(operation)
        sources = operation.sources
        if sources.job_analysis_id is None:
            raise SourceChanged("Selection Operation has no frozen analysis identity.")
        try:
            source = self.sources.selection_source(tx, sources.job_analysis_id)
        except UnknownRecord as exc:
            raise SourceChanged("The selection plan source no longer exists.") from exc
        if (
            source.application_id != operation.application_id
            or source.deleted_at is not None
            or source.active_analysis_id != sources.job_analysis_id
            or source.active_snapshot_id != source.job_snapshot_id
            or _model_hash(source.analysis) != sources.dependency_hashes.get("job_analysis")
        ):
            raise SourceChanged("The analysis changed before the plan proposal activated.")
        active_plan_id = source.active_plan.id if source.active_plan is not None else None
        if command.enforce_expected_selection_plan and (
            active_plan_id != command.expected_selection_plan_id
        ):
            raise SourceChanged("The active SelectionPlan changed before the proposal activated.")

        if self.sources.knowledge_is_prepared(tx):
            raise KnowledgeRejected("Knowledge has an uncommitted prepared mutation")
        if operation.sources.knowledge_context_hash != document_knowledge_context_hash(self):
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

    def activate(self, tx: WriteTransaction, operation, prepared):
        del operation
        if not isinstance(prepared.value, PreparedSelectionProposal):
            raise TypeError("selection handler received an invalid prepared value")
        result = self.activation.activate_selection_plan(tx, prepared.value.selection)
        return (
            OperationOutputReference(
                output_type="selection_plan",
                output_id=result.selection_plan_id,
                active=True,
            ),
        )


class RegenerationOperationHandler(DraftTaskHandler):
    """`regenerate_section` and `regenerate_claim`, which differ only in the command.

    One class for both because their contract is identical: the same frozen
    draft identity, the same source check, the same optimistic commit. Splitting
    them would give two places for the version check to drift apart, and it is
    the version check that stops a regeneration landing on content the user
    edited while it ran.
    """

    def __init__(
        self,
        service: DraftAuthoringService,
        sources: DraftOperationSourceReader,
        activation: DraftActivation,
        knowledge: AnalysisKnowledgeSource,
        *,
        task: str,
    ):
        self.service = service
        self.sources = sources
        self.activation = activation
        self.knowledge = knowledge
        self.task = task
        self._command_type = (
            RegenerateSectionCommand if task == "regenerate_section" else RegenerateClaimCommand
        )

    def _command(self, operation: PersistedOperation):
        return self._command_type.model_validate(operation.payload)

    def verify_sources(self, tx: ReadTransaction, operation: PersistedOperation) -> None:
        sources = operation.sources
        if (
            sources.working_draft_id is None
            or sources.working_draft_edit_version is None
            or sources.working_draft_content_hash is None
        ):
            raise SourceChanged("Regeneration Operation has no frozen draft identity.")
        try:
            working = self.sources.regeneration_source(tx, sources.working_draft_id)
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
        self.verify_knowledge(tx, operation)

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
            KnowledgeRejected,
            LineageBroken,
            UnknownRecord,
        ) as exc:
            raise self._classified(operation, exc) from exc

    def activate(self, tx: WriteTransaction, operation, prepared):
        del operation
        if not isinstance(prepared.value, PreparedRegeneration):
            raise TypeError("regeneration handler received an invalid prepared value")
        result = self.activation.activate_regeneration(
            tx,
            prepared.value,
        )
        return (
            OperationOutputReference(
                output_type="working_draft",
                output_id=result.working_draft_id,
                active=True,
            ),
        )


class RenderOperationHandler:
    def __init__(self, service: RenderingService, sources: RenderContextReader):
        self.service = service
        self.sources = sources

    @staticmethod
    def _command(operation: PersistedOperation) -> RenderCommand:
        return RenderCommand.model_validate(operation.payload)

    def verify_sources(self, tx: ReadTransaction, operation: PersistedOperation) -> None:
        sources = operation.sources
        if sources.approved_revision_id is None:
            raise SourceChanged("Render Operation has no frozen ApprovedRevision identity.")
        try:
            context = self.sources.operation_sources(tx, sources.approved_revision_id)
            revision, manifest = context.revision, context.manifest
            snapshot, analysis, plan = context.snapshot, context.analysis, context.plan
        except (UnknownRecord, OSError, ValueError) as exc:
            raise SourceChanged("An approved render source is missing or unreadable.") from exc
        dependencies = sources.dependency_hashes
        if (
            revision.application_id != operation.application_id
            or _model_hash(revision) != dependencies.get("approved_revision")
            or snapshot["source_hash"] != sources.job_snapshot_hash
            or analysis["application_id"] != operation.application_id
            or plan.application_id != operation.application_id
            or manifest["content_hash"] != dependencies.get("claim_manifest")
        ):
            raise SourceChanged("Approved render inputs changed before activation.")

    def verify_external_sources(self, operation: PersistedOperation) -> None:
        sources = operation.sources
        current_knowledge = document_knowledge_context_hash(self.service)
        if sources.knowledge_context_hash != current_knowledge:
            raise SourceChanged("Knowledge changed before render activation.")
        revision_id = sources.approved_revision_id
        if revision_id is None or not self.service.operation_source_payloads_match(revision_id):
            raise SourceChanged("An approved render payload changed before activation.")

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
                ("resume_html", "resume_pdf"),
                executed.artifact_ids,
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

    def activate(self, tx: WriteTransaction, operation, prepared):
        del operation
        if not isinstance(prepared.value, ExecutedRender):
            raise TypeError("render handler received an invalid executed value")
        self.service.activate(tx, prepared.value)
        return ()

    def after_activation(self, operation, prepared):
        del operation
        if isinstance(prepared.value, ExecutedRender):
            self.service.verify_activation(prepared.value)
