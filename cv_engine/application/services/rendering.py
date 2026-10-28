"""§16 rendering of the approved CV document, its PDF export, and its preview.

A render validates the content, writes HTML and PDF to a unique per-attempt path,
and checks the output - all outside database scopes. Activation locks the document
row and requires `approved_basis == basis` and `document_hash == expected`; only
then are the files swapped in and `rendered_basis` stamped. Render activation is
the only writer of `rendered_basis`. A failure records `last_render_error` only
while the hash still matches, never touches the active files, and its own files
are deleted best-effort. No render output is registered as an Artifact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...domain.contracts.knowledge import Profile
from ...domain.contracts.validation import ValidationReport
from ...domain.document import DocumentState, document_state
from ...domain.knowledge import Knowledge
from ...domain.render_validation import page_limit
from ...domain.templates import SampleLanguage, preview_template, template_spec
from ...util import new_id, utc_now
from ..actor import Actor
from ..artifacts import DocumentPdfDelivery
from ..commands import RenderCommand, RenderResult
from ..errors import (
    DOCUMENT_NOT_APPROVED,
    DOCUMENT_NOT_READY,
    ApplicationError,
    InfrastructureFailure,
    LineageBroken,
    PreconditionFailed,
    StateConflict,
    ValidationBlocked,
)
from ..ports import PayloadVerifier, Renderer
from ..ports.analysis_plans import AnalysisContextSourceReader, AnalysisKnowledgeSource
from ..ports.documents import DocumentFileStore, DocumentStore, RenderedFiles
from ..ports.transactions import TransactionManager, WriteTransaction
from ..queries import DocumentPageCountView, DocumentPdfPreviewView, DocumentPreviewView
from ..transactions import assert_external_io_allowed
from .documents import (
    DocumentSource,
    current_basis,
    load_knowledge,
    lock_document_source,
    read_document_source,
    refuse_deleted,
    refuse_review_reasons,
    require_hash,
    validate_document,
)


@dataclass(frozen=True)
class PreparedRender:
    #: Whose document this is: activation resolves it for the same user.
    actor: Actor
    command: RenderCommand
    knowledge: Knowledge
    source: DocumentSource
    profile: Profile
    recruiter_pdf_filename: str


@dataclass(frozen=True)
class ExecutedRender:
    prepared: PreparedRender
    report: ValidationReport
    files: RenderedFiles


class RenderingService:
    """Rendering the approved document and delivering what it produced."""

    def __init__(
        self,
        *,
        transactions: TransactionManager,
        documents: DocumentStore,
        sources: AnalysisContextSourceReader,
        files: DocumentFileStore,
        knowledge: AnalysisKnowledgeSource,
        renderer: Renderer,
        payloads: PayloadVerifier,
    ):
        self._transactions = transactions
        self._documents = documents
        self._sources = sources
        self.files = files
        self._knowledge = knowledge
        self.renderer = renderer
        self.payloads = payloads

    def load_knowledge(self, actor: Actor) -> Knowledge:
        return load_knowledge(self._knowledge, actor)

    def _source(self, actor: Actor, application_id: str) -> DocumentSource:
        with self._transactions.read() as tx:
            return read_document_source(tx, self._documents, self._sources, application_id, actor)

    def admit(self, actor: Actor, command: RenderCommand) -> None:
        """§16 admission: the document is approved at its current basis, with no blocker."""
        source = self._source(actor, command.application_id)
        refuse_deleted(command.application_id, source.deleted_at)
        require_hash(source.document, command.expected_document_hash)
        knowledge = self.load_knowledge(actor)
        state = document_state(source.document, current_basis(source.document, knowledge))
        if state is not DocumentState.APPROVED:
            raise PreconditionFailed(
                f"only an approved document can be rendered; it is {state.value}",
                code=DOCUMENT_NOT_APPROVED,
            )
        refuse_review_reasons(source.document, knowledge)

    def prepare(self, actor: Actor, command: RenderCommand) -> PreparedRender:
        """Validate the content against the current context before any browser starts."""
        source = self._source(actor, command.application_id)
        refuse_deleted(command.application_id, source.deleted_at)
        require_hash(source.document, command.expected_document_hash)
        knowledge = self.load_knowledge(actor)
        report = validate_document(source, knowledge)
        if not report.passed:
            raise ValidationBlocked(
                "render blocked: the content no longer passes its check", report
            )
        content = source.document.content
        if content is None:
            raise PreconditionFailed("the document has no content to render")
        try:
            profile = knowledge.profiles.get(content.profile)
        except (KeyError, ValueError) as exc:
            raise LineageBroken(f"the document's Profile is unavailable: {exc}") from exc
        return PreparedRender(
            actor=actor,
            command=command,
            knowledge=knowledge,
            source=source,
            profile=profile,
            recruiter_pdf_filename=self.renderer.filename_for(
                profile.normalized_role, knowledge.candidate
            ),
        )

    def execute(self, prepared: PreparedRender) -> ExecutedRender:
        """Render to a unique per-attempt path and check the output.

        A failure while rendering deletes this attempt's files; the document's active
        files are never touched here.
        """
        content = prepared.source.document.content
        if content is None:
            raise PreconditionFailed("the document has no content to render")
        candidate = prepared.knowledge.candidate
        try:
            html_path, pdf_path = self.files.render_targets(
                prepared.command.application_id, new_id()
            )
        except (OSError, ValueError) as exc:
            raise InfrastructureFailure(f"rendering failed: {exc}") from exc
        files = RenderedFiles(
            html=self.files.reference_for(html_path), pdf=self.files.reference_for(pdf_path)
        )
        try:
            try:
                template = prepared.source.document.template
                self.renderer.render_html(content, html_path, candidate, template)
                geometry = self.renderer.render_pdf(html_path, pdf_path)
                report = self.renderer.validate_rendered(
                    content,
                    prepared.profile,
                    html_path,
                    pdf_path,
                    geometry,
                    candidate,
                    prepared.recruiter_pdf_filename,
                    template,
                )
            except ApplicationError:
                raise
            except (OSError, RuntimeError) as exc:
                raise InfrastructureFailure(f"rendering failed: {exc}") from exc
        except Exception:
            self.files.discard(files)
            raise
        return ExecutedRender(prepared=prepared, report=report, files=files)

    def activate(
        self, tx: WriteTransaction, executed: ExecutedRender, knowledge: Knowledge
    ) -> tuple[RenderResult, RenderedFiles | None]:
        """Swap the new files in under the row lock, while the approval still holds.

        Returns the superseded files for best-effort deletion after commit. A
        `StateConflict` here means the document changed or lost its approval while
        rendering; nothing is written and the caller discards this attempt's files.
        """
        command = executed.prepared.command
        source = lock_document_source(
            tx, self._documents, self._sources, command.application_id, executed.prepared.actor
        )
        document = source.document
        require_hash(document, command.expected_document_hash)
        rendered_basis = current_basis(document, knowledge)
        if document.approved_basis != rendered_basis:
            raise StateConflict("the document's approval no longer holds at activation")
        updated, superseded = self._documents.activate_render(
            tx,
            command.application_id,
            command.expected_document_hash,
            rendered_basis,
            executed.files,
            updated_at=utc_now(),
        )
        return (
            RenderResult(
                application_id=command.application_id,
                document_id=updated.id,
                document_hash=updated.document_hash,
                validation=executed.report,
            ),
            superseded,
        )

    def record_failure(
        self,
        actor: Actor,
        application_id: str,
        expected_document_hash: str,
        error: dict[str, Any],
    ) -> bool:
        """Record `last_render_error` only while the hash still matches (§16).

        The hash the render failed against travels inside the error, so a read can
        tell the failure no longer describes the document once it changes.
        """
        payload = {**error, "document_hash": expected_document_hash}
        with self._transactions.write() as tx:
            self._sources.require_owned(tx, application_id, actor.user_id)
            return self._documents.record_render_error(
                tx, application_id, expected_document_hash, payload, updated_at=utc_now()
            )

    def discard(self, files: RenderedFiles | None) -> None:
        """Best-effort deletion of files no document references."""
        if files is not None:
            self.files.discard(files)

    def render(self, actor: Actor, command: RenderCommand) -> RenderResult:
        """The same three phases without an Operation runner, for a direct caller."""
        self.admit(actor, command)
        prepared = self.prepare(actor, command)
        executed = self.execute(prepared)
        if not executed.report.passed:
            self.discard(executed.files)
            self.record_failure(
                actor,
                command.application_id,
                command.expected_document_hash,
                {"code": "render_validation", "failure_code": "RENDER_FAILED"},
            )
            raise ValidationBlocked("rendered output did not pass validation", executed.report)
        try:
            with self._transactions.write() as tx:
                result, superseded = self.activate(tx, executed, prepared.knowledge)
        except Exception:
            self.discard(executed.files)
            raise
        self.discard(superseded)
        return result

    def export_recruiter_pdf(self, actor: Actor, application_id: str) -> DocumentPdfDelivery:
        """§16: the Ready document's PDF, checked against the basis at request time.

        Exempt from the deleted-Application refusal, as every read of history is.
        """
        source = self._source(actor, application_id)
        document = source.document
        knowledge = self.load_knowledge(actor)
        state = document_state(document, current_basis(document, knowledge))
        if state is not DocumentState.READY or document.pdf_path is None:
            raise PreconditionFailed(
                f"the document is not Ready; it is {state.value}", code=DOCUMENT_NOT_READY
            )
        content = document.content
        if content is None:
            raise PreconditionFailed("the document has no content", code=DOCUMENT_NOT_READY)
        stream = self.files.open_rendered_pdf(document.pdf_path)
        profile = knowledge.profiles.get(content.profile)
        return DocumentPdfDelivery(
            application_id=application_id,
            document_id=document.id,
            document_hash=document.document_hash,
            filename=self.renderer.filename_for(profile.normalized_role, knowledge.candidate),
            size=stream.size,
            stream=stream,
        )

    def preview_document(
        self, actor: Actor, application_id: str, template: str | None = None
    ) -> DocumentPreviewView:
        """The current content as HTML, through the render composition; stored nowhere.

        No browser starts and nothing is written: no document field, Artifact, or
        Operation. No approval is needed. `template` previews the content in another
        template (`track` for the track's own) without choosing it; by default the
        document's own.
        """
        document, content, knowledge = self._previewable(actor, application_id)
        chosen = document.template if template is None else preview_template(template)
        return DocumentPreviewView(
            application_id=application_id,
            document_id=document.id,
            document_hash=document.document_hash,
            language=content.language,
            html=self.renderer.preview_html(content, knowledge.candidate, chosen),
        )

    def preview_document_pdf(self, actor: Actor, application_id: str) -> DocumentPdfPreviewView:
        """The current content as a PDF stamped as an unapproved draft; stored nowhere."""
        document, content, knowledge = self._previewable(actor, application_id)
        return DocumentPdfPreviewView(
            application_id=application_id,
            document_id=document.id,
            document_hash=document.document_hash,
            pdf=self.renderer.preview_pdf(content, knowledge.candidate, document.template),
        )

    def document_page_count(self, actor: Actor, application_id: str) -> DocumentPageCountView:
        """How many pages the current content takes in its own template; stored nowhere.

        The same measurement `create_draft` fits a new draft with (`measure_pages`: the
        render's composition and browser, no preview stamp, a temporary directory), so
        the editor can show an overflow before approval rather than at render. It starts
        a browser, so the client asks once per saved version, not per keystroke. A
        measurement that fails is `pages=None`, never an error: the count is a hint.
        """
        document, content, knowledge = self._previewable(actor, application_id)
        try:
            maximum: int | None = page_limit(knowledge.profiles.get(content.profile))
        except (KeyError, ValueError):
            maximum = None
        assert_external_io_allowed("document page measurement")
        try:
            pages: int | None = self.renderer.measure_pages(
                content, knowledge.candidate, document.template
            )
        except InfrastructureFailure:
            pages = None
        return DocumentPageCountView(
            application_id=application_id,
            document_id=document.id,
            document_hash=document.document_hash,
            template=document.template,
            pages=pages if pages is None or pages >= 1 else None,
            maximum=maximum,
        )

    def sample_template(self, template: str, language: SampleLanguage) -> str:
        """A fictional CV in one template, for choosing a template with no CV yet.

        It reads nothing of any user's: the content is the shipped sample.
        """
        template_spec(preview_template(template))
        return self.renderer.sample_html(preview_template(template), language)

    def _previewable(self, actor: Actor, application_id: str):
        document = self._source(actor, application_id).document
        if document.content is None:
            raise PreconditionFailed("the document has no content to preview yet")
        return document, document.content, self.load_knowledge(actor)
