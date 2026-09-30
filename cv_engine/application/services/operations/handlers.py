"""One handler per Operation type: check sources, execute, activate.

The runner owns the lifecycle; these own what a given Operation type means.
Adding an Operation type is a change to this module and to the composition
root's handler table, and to nothing else.

Every Operation that mutates the CV document froze `expected_document_hash` when it
was submitted. Its source check and its activation compare that hash against the
document under the runner's Application lock; a mismatch discards the result and
fails the Operation with `SOURCE_CHANGED` (state-and-use-cases.md §11).
Draft-producing Operations do not recheck input freshness: their output is
unapproved, and check/approve/render validate against the current context.
"""

from __future__ import annotations

import re
from dataclasses import fields
from typing import Any

from ....domain.contracts.validation import ValidationReport
from ...commands import (
    AnalyzeCommand,
    DraftCommand,
    ProposeSelectionCommand,
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
    PreconditionFailed,
    ProposalRejected,
    StateConflict,
    UnknownRecord,
    ValidationBlocked,
)
from ...operation_runner import OperationExecutionError, PreparedOperation, SourceChanged
from ...operations import (
    FailureReason,
    OperationFailureCode,
    OperationOutputReference,
    PdfPageLimitReason,
    PersistedOperation,
    RenderCheckCode,
    RenderCheckReason,
)
from ...ports.analysis_plans import AnalysisKnowledgeSource, AnalysisSelectionSourceReader
from ...ports.documents import DocumentStore, RenderedFiles
from ...ports.transactions import ReadTransaction, WriteTransaction
from ..analysis.activation import AnalysisActivation
from ..analysis.preparation import PreparedAnalysis
from ..analysis.selection_policy import PreparedSelectionProposal
from ..analysis.service import AnalysisService, load_analysis_knowledge
from ..drafts import DraftAuthoringService, PreparedDraft, PreparedRegeneration
from ..drafts.activation import DraftActivation
from ..proposals import ProviderEvidence
from ..rendering import ExecutedRender, RenderingService
from .common import analysis_knowledge_context_hash
from .failures import failure_code_for, failure_reason_for, safe_failure_detail_for


def _document_output(document_id: str) -> tuple[OperationOutputReference, ...]:
    return (
        OperationOutputReference(output_type="cv_document", output_id=document_id, active=True),
    )


def verify_document_hash(
    tx: ReadTransaction, documents: DocumentStore, operation: PersistedOperation
) -> str:
    """The frozen `expected_document_hash` still describes the document, or SOURCE_CHANGED."""
    expected = operation.sources.expected_document_hash
    if expected is None:
        raise SourceChanged("The Operation has no frozen document identity.")
    document = documents.document(tx, operation.application_id)
    if document is None or document.document_hash != expected:
        raise SourceChanged("The CV document changed before the Operation activated.")
    return document.id


def _safe_render_failure_detail(report: ValidationReport) -> str:
    """Return actionable render detail without exposing paths or browser internals."""
    issue = next((item for item in report.issues if item.hard), None)
    if issue is None:
        return "Rendered output did not pass validation."
    if issue.code == "page-count" and re.fullmatch(r"\d+ pages; maximum \d+", issue.message):
        return f"Rendered PDF has {issue.message}."
    safe_messages = {
        "text-coverage": "Rendered PDF text is not sufficiently recoverable by ATS readers.",
        "link-targets": "Rendered PDF is missing one or more expected contact links.",
        "overflow": "Rendered content exceeds the page boundaries.",
        "document-direction": "Rendered document direction does not match its language.",
        "mixed-direction-isolation": (
            "Rendered right-to-left content is missing direction isolation."
        ),
        "filename": "Rendered PDF filename does not match the required recruiter filename.",
        "html-missing": "Rendered HTML is missing or empty.",
        "pdf-missing": "Rendered PDF is missing or empty.",
        "pdf-corrupt": "Rendered PDF could not be read.",
    }
    return safe_messages.get(issue.code, "Rendered output did not pass validation.")


#: Render validation issue codes and the reason each is reported under. An issue
#: code this table does not know is reported as the generic `render_validation`.
_RENDER_REASON_CODES: dict[str, RenderCheckCode] = {
    "text-coverage": "pdf_text_coverage",
    "link-targets": "pdf_link_targets",
    "overflow": "content_overflow",
    "document-direction": "document_direction",
    "mixed-direction-isolation": "direction_isolation",
    "filename": "pdf_filename",
    "html-missing": "html_missing",
    "pdf-missing": "pdf_missing",
    "pdf-corrupt": "pdf_corrupt",
}


def _render_failure_reason(report: ValidationReport) -> FailureReason:
    """The same first hard issue `_safe_render_failure_detail` reports, structured."""
    issue = next((item for item in report.issues if item.hard), None)
    if issue is None:
        return RenderCheckReason(code="render_validation")
    if issue.code == "page-count":
        match = re.fullmatch(r"(\d+) pages; maximum (\d+)", issue.message)
        if match is not None:
            return PdfPageLimitReason(pages=int(match[1]), maximum=int(match[2]))
    return RenderCheckReason(code=_RENDER_REASON_CODES.get(issue.code, "render_validation"))


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

    def discard(self, operation: PersistedOperation, prepared: PreparedOperation) -> None:
        """Nothing to clean up: provider evidence is immutable and stays inactive."""
        del operation, prepared

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
        return OperationExecutionError(
            code,
            safe_failure_detail_for(error),
            outputs=outputs,
            reason=failure_reason_for(error),
        )


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
    """`analyze_job`, bound to its input JobSnapshot rather than to a document."""

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
        try:
            result = self.activation.activate(tx, self._command(operation), prepared.value)
        except StateConflict as exc:
            raise SourceChanged("The analysis context changed before activation.") from exc
        outputs = [
            OperationOutputReference(
                output_type="job_analysis", output_id=result.analysis_id, active=True
            )
        ]
        if result.created_document and result.document_id is not None:
            outputs.extend(_document_output(result.document_id))
        return tuple(outputs)


class SelectionPlanOperationHandler(AnalysisTaskHandler):
    """`propose_selection`: the AI form of §14 `update_selection`, under its content rule."""

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
    def _command(operation: PersistedOperation) -> ProposeSelectionCommand:
        return ProposeSelectionCommand.model_validate(operation.payload)

    def verify_sources(self, tx: ReadTransaction, operation: PersistedOperation) -> None:
        verify_document_hash(tx, self.service.documents, operation)

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
            # The document moved between the source check and execution.
            StateConflict,
        ) as exc:
            raise self._classified(operation, exc) from exc

    def activate(self, tx: WriteTransaction, operation, prepared):
        if not isinstance(prepared.value, PreparedSelectionProposal):
            raise TypeError("selection handler received an invalid prepared value")
        try:
            document_id = self.activation.activate_selection_proposal(
                tx, self._command(operation), prepared.value, self.load_knowledge()
            )
        except StateConflict as exc:
            raise SourceChanged("The CV document changed before the proposal activated.") from exc
        except PreconditionFailed as exc:
            raise OperationExecutionError(
                OperationFailureCode.INVALID_OUTPUT,
                "The AI proposal was rejected.",
            ) from exc
        return _document_output(document_id)


class DraftTaskHandler(RegisteredEvidenceTaskHandler):
    service: DraftAuthoringService
    knowledge: AnalysisKnowledgeSource
    documents: DocumentStore

    def verify_sources(self, tx: ReadTransaction, operation: PersistedOperation) -> None:
        verify_document_hash(tx, self.documents, operation)


class DraftOperationHandler(DraftTaskHandler):
    """`create_draft`: AI content, written only at the frozen hash."""

    task = "draft_resume"

    def __init__(
        self,
        service: DraftAuthoringService,
        documents: DocumentStore,
        activation: DraftActivation,
        knowledge: AnalysisKnowledgeSource,
    ):
        self.service = service
        self.documents = documents
        self.activation = activation
        self.knowledge = knowledge

    @staticmethod
    def _command(operation: PersistedOperation) -> DraftCommand:
        return DraftCommand.model_validate(operation.payload)

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
            # The document moved between the source check and execution.
            StateConflict,
        ) as exc:
            raise self._classified(operation, exc) from exc

    def activate(self, tx: WriteTransaction, operation, prepared):
        del operation
        if not isinstance(prepared.value, PreparedDraft):
            raise TypeError("draft handler received an invalid prepared value")
        try:
            result = self.activation.activate_generation(tx, prepared.value)
        except StateConflict as exc:
            raise SourceChanged("The CV document changed before the draft activated.") from exc
        return _document_output(result.document_id)


class RegenerationOperationHandler(DraftTaskHandler):
    """`regenerate_section` and `regenerate_claim`, which differ only in the command.

    One class for both because their contract is identical: the same frozen hash,
    the same source check, the same optimistic commit.
    """

    def __init__(
        self,
        service: DraftAuthoringService,
        documents: DocumentStore,
        activation: DraftActivation,
        knowledge: AnalysisKnowledgeSource,
        *,
        task: str,
    ):
        self.service = service
        self.documents = documents
        self.activation = activation
        self.knowledge = knowledge
        self.task = task
        self._command_type = (
            RegenerateSectionCommand if task == "regenerate_section" else RegenerateClaimCommand
        )

    def _command(self, operation: PersistedOperation):
        return self._command_type.model_validate(operation.payload)

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
        try:
            result = self.activation.activate_regeneration(tx, prepared.value)
        except StateConflict as exc:
            raise SourceChanged("The CV document changed before regeneration activated.") from exc
        return _document_output(result.document_id)


def _render_failure(
    code: OperationFailureCode, detail: str, reason: FailureReason | None
) -> tuple[OperationExecutionError, dict[str, Any]]:
    """The Operation failure and the structured `last_render_error` it records."""
    error = OperationExecutionError(code, detail, reason=reason)
    recorded: dict[str, Any] = (
        reason.model_dump(mode="json") if reason is not None else {"code": code.value.lower()}
    )
    return error, {**recorded, "failure_code": code.value, "detail": detail}


class RenderOperationHandler:
    """`render_document`: render outside every scope, activate under the row lock."""

    def __init__(
        self,
        service: RenderingService,
        documents: DocumentStore,
        sources: AnalysisSelectionSourceReader,
        knowledge: AnalysisKnowledgeSource,
    ):
        self.service = service
        self.documents = documents
        self.sources = sources
        self.knowledge = knowledge
        #: Files a committed activation released, by Operation, for `after_activation`.
        self._superseded: dict[str, RenderedFiles | None] = {}

    @staticmethod
    def _command(operation: PersistedOperation) -> RenderCommand:
        return RenderCommand.model_validate(operation.payload)

    def verify_sources(self, tx: ReadTransaction, operation: PersistedOperation) -> None:
        verify_document_hash(tx, self.documents, operation)
        if self.sources.knowledge_is_prepared(tx):
            raise KnowledgeRejected("Knowledge has an uncommitted prepared mutation")

    def verify_external_sources(self, operation: PersistedOperation) -> None:
        del operation

    def _fail(
        self,
        operation: PersistedOperation,
        code: OperationFailureCode,
        detail: str,
        reason: FailureReason | None,
    ) -> OperationExecutionError:
        error, recorded = _render_failure(code, detail, reason)
        command = self._command(operation)
        # Recorded only while the hash still matches; otherwise only the Operation
        # keeps the failure (§16).
        self.service.record_failure(
            command.application_id, command.expected_document_hash, recorded
        )
        return error

    def execute(self, operation, cancellation_requested) -> PreparedOperation:
        if cancellation_requested():
            return PreparedOperation()
        try:
            prepared = self.service.prepare(self._command(operation))
        except ValidationBlocked as exc:
            raise self._fail(
                operation,
                OperationFailureCode.RENDER_FAILED,
                "The document no longer passes its content check.",
                RenderCheckReason(code="render_validation"),
            ) from exc
        except (MissingFactRendering, StateConflict, PreconditionFailed) as exc:
            raise OperationExecutionError(
                failure_code_for(exc),
                safe_failure_detail_for(exc),
                reason=failure_reason_for(exc),
            ) from exc
        try:
            executed = self.service.execute(prepared)
        except InfrastructureFailure as exc:
            message = str(exc).casefold()
            code = (
                OperationFailureCode.BROWSER_START_FAILED
                if "browser" in message and "start" in message
                else OperationFailureCode.RENDER_FAILED
            )
            raise self._fail(operation, code, "Rendering failed.", None) from exc
        if not executed.report.passed:
            self.service.discard(executed.files)
            raise self._fail(
                operation,
                OperationFailureCode.RENDER_FAILED,
                _safe_render_failure_detail(executed.report),
                _render_failure_reason(executed.report),
            )
        return PreparedOperation(value=executed)

    def activate(self, tx: WriteTransaction, operation, prepared):
        if not isinstance(prepared.value, ExecutedRender):
            raise TypeError("render handler received an invalid executed value")
        knowledge = load_analysis_knowledge(self.knowledge)
        try:
            result, superseded = self.service.activate(tx, prepared.value, knowledge)
        except StateConflict as exc:
            raise SourceChanged(
                "The CV document changed or lost its approval before the render activated."
            ) from exc
        self._superseded[operation.id] = superseded
        return _document_output(result.document_id)

    def after_activation(self, operation, prepared):
        del prepared
        self.service.discard(self._superseded.pop(operation.id, None))

    def discard(self, operation: PersistedOperation, prepared: PreparedOperation) -> None:
        """An attempt that never activated leaves files nothing references: delete them."""
        self._superseded.pop(operation.id, None)
        if isinstance(prepared.value, ExecutedRender):
            self.service.discard(prepared.value.files)
