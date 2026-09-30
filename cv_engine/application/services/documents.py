"""What every CV-document command shares, as pure functions over loaded values.

state-and-use-cases.md §3 and §14–§18. The basis is computed here, in the application
layer, from the document and the Knowledge loaded with it; stores never compute it.
Composition and validation are the domain's; this module binds them to the document
so generation, check, approve, render and submit all make the same decision the same
way.

Nothing here opens a transaction or performs I/O except `load_knowledge`, which
reads Knowledge files and must therefore run outside a database scope.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from ...domain.contracts.analysis import JobAnalysis
from ...domain.contracts.document import BuiltWith, CVDocument
from ...domain.contracts.drafts import DraftDocument
from ...domain.contracts.validation import ValidationIssue, ValidationReport
from ...domain.document import basis
from ...domain.draft_markdown import serialize_markdown
from ...domain.drafts import build_draft
from ...domain.frame import MissingFactRendering as DomainMissingFactRendering
from ...domain.knowledge import Knowledge
from ...domain.validation import validate_draft
from ..errors import (
    DOCUMENT_CHANGED,
    InfrastructureFailure,
    KnowledgeRejected,
    LineageBroken,
    MissingFactRendering,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
)
from ..ports.analysis_plans import AnalysisKnowledgeSource, AnalysisSelectionSourceReader
from ..ports.documents import DocumentStore
from ..ports.transactions import ReadTransaction, WriteTransaction
from ..state import document_review_reasons


def load_knowledge(source: AnalysisKnowledgeSource) -> Knowledge:
    try:
        return source.load()
    except OSError as exc:
        raise InfrastructureFailure(f"could not read Knowledge: {exc}") from exc
    except ValueError as exc:
        raise KnowledgeRejected(str(exc)) from exc


@dataclass(frozen=True)
class DocumentSource:
    """The document and the analysis it is pinned to, read in one transaction."""

    document: CVDocument
    analysis: JobAnalysis
    #: The JobSnapshot the document's analysis was made of.
    job_snapshot_id: str
    #: The newest analysis of the Application and the active JobSnapshot.
    latest_analysis_id: str | None
    active_snapshot_id: str
    deleted_at: str | None

    @property
    def on_older_analysis(self) -> bool:
        """§8 `DOCUMENT_ON_OLDER_ANALYSIS`."""
        return (
            self.latest_analysis_id != self.document.analysis_id
            or self.job_snapshot_id != self.active_snapshot_id
        )


def _source(
    tx: ReadTransaction,
    document: CVDocument | None,
    sources: AnalysisSelectionSourceReader,
    application_id: str,
) -> DocumentSource:
    if document is None:
        raise UnknownRecord(f"application {application_id} has no CV document yet; analyze first")
    selection = sources.selection_source(tx, document.analysis_id)
    return DocumentSource(
        document=document,
        analysis=selection.analysis,
        job_snapshot_id=selection.job_snapshot_id,
        latest_analysis_id=selection.active_analysis_id,
        active_snapshot_id=selection.active_snapshot_id,
        deleted_at=selection.deleted_at,
    )


def read_document_source(
    tx: ReadTransaction,
    documents: DocumentStore,
    sources: AnalysisSelectionSourceReader,
    application_id: str,
) -> DocumentSource:
    return _source(tx, documents.document(tx, application_id), sources, application_id)


def lock_document_source(
    tx: WriteTransaction,
    documents: DocumentStore,
    sources: AnalysisSelectionSourceReader,
    application_id: str,
) -> DocumentSource:
    """The same read, with the document row locked until the transaction ends."""
    return _source(tx, documents.lock_document(tx, application_id), sources, application_id)


def refuse_deleted(application_id: str, deleted_at: str | None) -> None:
    if deleted_at is not None:
        raise StateConflict(f"application is deleted: {application_id}")


def require_hash(document: CVDocument, expected_document_hash: str) -> None:
    """The optimistic check every document command makes before it does any work."""
    if document.document_hash != expected_document_hash:
        raise StateConflict(
            "the CV document changed since it was read (expected_document_hash): "
            f"expected {expected_document_hash}, found {document.document_hash}",
            code=DOCUMENT_CHANGED,
        )


def current_basis(document: CVDocument, knowledge: Knowledge) -> str:
    return basis(document, knowledge.facts.facts)


def built_with(knowledge: Knowledge) -> BuiltWith:
    return BuiltWith(profile_version=knowledge.profiles.version)


def refuse_review_reasons(document: CVDocument, knowledge: Knowledge) -> None:
    """A review reason blocks approve, render and submit (§7); name the first."""
    reasons = document_review_reasons(document, knowledge)
    if reasons:
        raise PreconditionFailed(
            f"blocked by {reasons[0].code}: {reasons[0].message}", code=reasons[0].code
        )


def compose_content(
    application_id: str,
    analysis_id: str,
    job_snapshot_id: str,
    analysis: JobAnalysis,
    knowledge: Knowledge,
    chosen: Mapping[str, Iterable[str]] | None = None,
) -> DraftDocument:
    """The canonical content one analysis and one choice of facts produce.

    `chosen` maps each section's English name to its chosen facts; `None` lays out
    every section's whole pool, the frame `draft_resume` chooses from.
    """
    try:
        return build_draft(
            application_id=application_id,
            job_snapshot_id=job_snapshot_id,
            job_analysis_id=analysis_id,
            analysis=analysis,
            profile=knowledge.profiles.get(analysis.profile),
            facts=knowledge.facts,
            candidate=knowledge.candidate,
            presentations=knowledge.presentations,
            chosen=chosen,
        )
    except DomainMissingFactRendering as exc:
        raise MissingFactRendering(exc.fact_id, exc.language) from exc
    except ValueError as exc:
        raise PreconditionFailed(f"document content could not be built: {exc}") from exc


def validate_document(source: DocumentSource, knowledge: Knowledge) -> ValidationReport:
    """§15: the validation contract against the current content and current Knowledge.

    The content's own binding is checked first: content that names another
    Application, analysis or snapshot than the document it sits in is not evidence of
    anything, and fails as a hard content finding rather than being validated.
    """
    document = source.document
    content = document.content
    if content is None:
        raise PreconditionFailed("the document has no content to check")
    mismatched = [
        name
        for name, actual, expected in (
            ("application", content.application_id, document.application_id),
            ("job analysis", content.job_analysis_id, document.analysis_id),
            ("job snapshot", content.job_snapshot_id, source.job_snapshot_id),
        )
        if actual != expected
    ]
    if mismatched:
        return ValidationReport.from_findings(
            {"content": False},
            [
                ValidationIssue(
                    group="content",
                    code="document-binding-mismatch",
                    message=f"content is bound to another {', '.join(mismatched)}",
                )
            ],
        )
    try:
        profile = knowledge.profiles.get(content.profile)
    except (KeyError, ValueError) as exc:
        raise LineageBroken(f"the document's Profile is unavailable: {exc}") from exc
    return validate_draft(
        content,
        serialize_markdown(content),
        knowledge.facts,
        profile,
        source.analysis,
        presentations=knowledge.presentations,
    )
