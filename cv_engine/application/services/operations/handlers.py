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
from typing import Any

from ....domain.contracts.validation import ValidationReport
from ....util import new_id
from ...commands import (
    AnalysisResult,
    AnalyzeCommand,
    DraftCommand,
    RegenerateClaimCommand,
    RegenerateSectionCommand,
    RenderCommand,
)
from ...errors import (
    ApplicationError,
    InfrastructureFailure,
    KnowledgeRejected,
    StateConflict,
    UnknownRecord,
    ValidationBlocked,
)
from ...operation_runner import OperationExecutionError, PreparedOperation, SourceChanged
from ...operations import (
    FailureReason,
    OperationFailureCode,
    OperationOutputReference,
    OperationSources,
    PdfPageLimitReason,
    PersistedOperation,
    RenderCheckCode,
    RenderCheckReason,
)
from ...ports.analysis_plans import AnalysisContextSourceReader, AnalysisKnowledgeSource
from ...ports.documents import DocumentStore, RenderedFiles
from ...ports.operation_client import OperationContinuationStore
from ...ports.transactions import ReadTransaction, WriteTransaction
from ..analysis.activation import AnalysisActivation
from ..analysis.preparation import PreparedAnalysis
from ..analysis.service import AnalysisService
from ..documents import load_knowledge
from ..drafts import DraftAuthoringService, PreparedDraft, PreparedRegeneration
from ..drafts.activation import DraftActivation
from ..rendering import ExecutedRender, RenderingService
from .failures import failure_code_for, failure_reason_for, safe_failure_detail_for
from .service import draft_operation_request


def _document_output(document_id: str) -> tuple[OperationOutputReference, ...]:
    return (OperationOutputReference(output_type="cv_document", output_id=document_id),)


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
    """What the three AI-only handlers share: classification.

    Written once because the alternative is three copies of the same
    `except` ladder, and a fourth task added later would get whichever copy its
    author happened to read. Logging provider calls is no concern of a handler:
    every attempt is already in the AI call log before the service returns or raises.
    """

    service: Any

    def after_activation(self, operation: PersistedOperation, prepared: PreparedOperation) -> None:
        pass

    def discard(self, operation: PersistedOperation, prepared: PreparedOperation) -> None:
        """Nothing to clean up: the AI call log is immutable and outlives the result."""
        del operation, prepared

    def prepared(self, value: Any) -> PreparedOperation:
        return PreparedOperation(
            value=value, withheld_claims=getattr(value, "withheld_claims", None)
        )

    def _classified(
        self, operation: PersistedOperation, error: ApplicationError
    ) -> OperationExecutionError:
        del operation
        return OperationExecutionError(
            failure_code_for(error),
            safe_failure_detail_for(error),
            reason=failure_reason_for(error),
        )


class AnalysisOperationHandler(AITaskHandler):
    """`analyze_job`, bound to the exact job text it read rather than to a document."""

    def __init__(
        self,
        service: AnalysisService,
        sources: AnalysisContextSourceReader,
        activation: AnalysisActivation,
        knowledge: AnalysisKnowledgeSource,
        documents: DocumentStore,
        continuations: OperationContinuationStore,
    ):
        self.service = service
        self.sources = sources
        self.activation = activation
        self.knowledge = knowledge
        self.documents = documents
        self.continuations = continuations

    @staticmethod
    def _command(operation: PersistedOperation) -> AnalyzeCommand:
        return AnalyzeCommand.model_validate(operation.payload)

    def verify_sources(self, tx: ReadTransaction, operation: PersistedOperation) -> None:
        sources = operation.sources
        if sources.job_text_hash is None:
            raise SourceChanged("Analysis Operation has no frozen job text identity.")
        try:
            source = self.sources.job_text_source(tx, operation.application_id)
        except UnknownRecord as exc:
            raise SourceChanged("The Application no longer exists.") from exc
        if source.deleted_at is not None:
            raise SourceChanged("The Application was deleted before analysis activation.")
        if source.job_text_hash != sources.job_text_hash:
            raise SourceChanged("The job text changed before analysis activation.")

        if self.sources.knowledge_is_prepared(tx):
            raise KnowledgeRejected("Knowledge has an uncommitted prepared mutation")
        if (
            operation.sources.knowledge_context_hash
            != load_knowledge(self.knowledge).context_hash()
        ):
            raise SourceChanged("Knowledge changed before analysis activation.")

    def execute(self, operation, still_owned) -> PreparedOperation:
        if not still_owned():
            return PreparedOperation()
        try:
            return self.prepared(
                self.service.prepare(
                    self._command(operation), operation_id=operation.id, still_owned=still_owned
                )
            )
        except ApplicationError as exc:
            raise self._classified(operation, exc) from exc

    def activate(self, tx: WriteTransaction, operation, prepared):
        if not isinstance(prepared.value, PreparedAnalysis):
            raise TypeError("analysis handler received an invalid prepared value")
        try:
            result = self.activation.activate(tx, self._command(operation), prepared.value)
        except StateConflict as exc:
            raise SourceChanged("The analysis context changed before activation.") from exc
        outputs = [
            OperationOutputReference(output_type="job_analysis", output_id=result.analysis_id)
        ]
        if result.created_document and result.document_id is not None:
            outputs.extend(_document_output(result.document_id))
            self._continue_to_draft(tx, operation, result)
        return tuple(outputs)

    def _continue_to_draft(
        self, tx: WriteTransaction, operation: PersistedOperation, result: AnalysisResult
    ) -> None:
        """§9 automatic generation: queue `create_draft` for the document just created.

        In the activation scope, so the analysis and the queued draft commit together
        or not at all, addressed to the exact hash the new document was created with.
        A new document has no content, no stamps, and no review reason, and no
        Operation can name its hash yet, so `create_draft` is available by
        construction. The key is derived from this Operation: a repeated activation
        of the same run cannot queue a second draft.
        """
        continuation = self._command(operation).draft_continuation
        if continuation is None:
            return
        document = self.documents.document(tx, operation.application_id)
        if document is None:
            raise RuntimeError("the analysis created a document that cannot be read back")
        command = DraftCommand(
            application_id=operation.application_id,
            expected_document_hash=document.document_hash,
            model=continuation.model,
            reasoning_effort=continuation.reasoning_effort,
        )
        sources = OperationSources(
            job_analysis_id=result.analysis_id,
            expected_document_hash=document.document_hash,
        )
        self.continuations.enqueue(
            tx,
            draft_operation_request(command, sources, f"draft-continuation:{operation.id}"),
            operation_id=new_id(),
        )


class DraftTaskHandler(AITaskHandler):
    service: DraftAuthoringService
    documents: DocumentStore

    def verify_sources(self, tx: ReadTransaction, operation: PersistedOperation) -> None:
        verify_document_hash(tx, self.documents, operation)


class DraftOperationHandler(DraftTaskHandler):
    """`create_draft`: AI content, written only at the frozen hash."""

    def __init__(
        self,
        service: DraftAuthoringService,
        documents: DocumentStore,
        activation: DraftActivation,
    ):
        self.service = service
        self.documents = documents
        self.activation = activation

    @staticmethod
    def _command(operation: PersistedOperation) -> DraftCommand:
        return DraftCommand.model_validate(operation.payload)

    def execute(self, operation, still_owned) -> PreparedOperation:
        if not still_owned():
            return PreparedOperation()
        try:
            return self.prepared(
                self.service.prepare(
                    self._command(operation), operation_id=operation.id, still_owned=still_owned
                )
            )
        except ApplicationError as exc:
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
        *,
        command_type: type[RegenerateSectionCommand] | type[RegenerateClaimCommand],
    ):
        self.service = service
        self.documents = documents
        self.activation = activation
        self._command_type = command_type

    def _command(self, operation: PersistedOperation):
        return self._command_type.model_validate(operation.payload)

    def execute(self, operation, still_owned) -> PreparedOperation:
        if not still_owned():
            return PreparedOperation()
        try:
            command = self._command(operation)
            if isinstance(command, RegenerateSectionCommand):
                result = self.service.prepare_section_regeneration(
                    command, operation_id=operation.id, still_owned=still_owned
                )
            elif isinstance(command, RegenerateClaimCommand):
                result = self.service.prepare_claim_regeneration(
                    command, operation_id=operation.id, still_owned=still_owned
                )
            else:
                raise TypeError("regeneration handler parsed an invalid command")
            return self.prepared(result)
        except ApplicationError as exc:
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
        sources: AnalysisContextSourceReader,
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

    def execute(self, operation, still_owned) -> PreparedOperation:
        if not still_owned():
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
        except ApplicationError as exc:
            raise OperationExecutionError(
                failure_code_for(exc),
                safe_failure_detail_for(exc),
                reason=failure_reason_for(exc),
            ) from exc
        # A browser that fails to start rendered nothing, so it is started once more
        # while the Operation is still this runner's; every other failure is final.
        for attempt in (1, 2):
            try:
                executed = self.service.execute(prepared)
                break
            except InfrastructureFailure as exc:
                message = str(exc).casefold()
                code = (
                    OperationFailureCode.BROWSER_START_FAILED
                    if "browser" in message and "start" in message
                    else OperationFailureCode.RENDER_FAILED
                )
                if code is OperationFailureCode.BROWSER_START_FAILED and attempt == 1:
                    if still_owned():
                        continue
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
        knowledge = load_knowledge(self.knowledge)
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
