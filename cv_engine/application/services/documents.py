"""What every CV-document command shares, as pure functions over loaded values.

state-and-use-cases.md §3 and §14–§18. The basis is computed here, in the application
layer, from the document and the Knowledge loaded with it; stores never compute it.
Selection, composition and validation are the domain's; this module binds them to
the document so update_selection, apply_analysis_decisions, confirm_and_use_fact,
generation, check, approve, render and submit all make the same decision the same
way.

Nothing here opens a transaction or performs I/O except `load_knowledge`, which
reads Knowledge files and must therefore run outside a database scope.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ...domain.contracts.analysis import JobAnalysis
from ...domain.contracts.document import BuiltWith, CVDocument
from ...domain.contracts.drafts import DraftDocument
from ...domain.contracts.selection import SelectionManifest
from ...domain.contracts.taxonomy import Emphasis
from ...domain.contracts.validation import ValidationIssue, ValidationReport
from ...domain.document import basis
from ...domain.draft_markdown import serialize_markdown
from ...domain.drafts import build_draft, carries_authored_wording
from ...domain.knowledge import Knowledge
from ...domain.selection import MissingFactRendering as DomainMissingFactRendering
from ...domain.validation import validate_draft
from ..errors import (
    DOCUMENT_CHANGED,
    REGENERATION_REQUIRED,
    InfrastructureFailure,
    KnowledgeRejected,
    LineageBroken,
    MissingFactRendering,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
)
from ..ports.analysis_plans import AnalysisKnowledgeSource, AnalysisSelectionSourceReader
from ..ports.documents import DocumentBody, DocumentStore
from ..ports.transactions import ReadTransaction, WriteTransaction
from ..state import document_review_reasons
from .analysis.selection_policy import AnalysisSelection


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
    return BuiltWith(
        profile_version=knowledge.profiles.version,
        selection_policy_version=knowledge.policies.version,
    )


def refuse_review_reasons(
    document: CVDocument, knowledge: Knowledge, requested_fact_ids: Iterable[str] = ()
) -> None:
    """A review reason blocks approve, render and submit (§7); name the first."""
    reasons = document_review_reasons(document, knowledge, requested_fact_ids)
    if reasons:
        raise PreconditionFailed(
            f"blocked by {reasons[0].code}: {reasons[0].message}", code=reasons[0].code
        )


def build_document_selection(
    analysis: JobAnalysis,
    knowledge: Knowledge,
    *,
    current: SelectionManifest | None = None,
    pinned_fact_ids: Iterable[str] = (),
    excluded_fact_ids: Iterable[str] = (),
    emphasis_override: str | None = None,
    ai_rationale: str | None = None,
) -> SelectionManifest:
    """The deterministic selection for one analysis, with a user or AI overlay.

    The effective Emphasis is the explicit override when one is given, otherwise the
    one the current selection already carries, otherwise the analysis's. The
    selection records the effective `emphasis` separately from the nullable
    `emphasis_override` (§14). A rationale marks the selection as an activated AI
    proposal; it is provenance only and is never read back.
    """
    try:
        requested = Emphasis(emphasis_override) if emphasis_override is not None else None
    except ValueError as exc:
        raise PreconditionFailed(f"unknown Emphasis: {emphasis_override}") from exc
    effective = requested or (current.emphasis if current is not None else analysis.emphasis)
    explicit = requested or (current.emphasis_override if current is not None else None)
    selection_analysis = analysis.model_copy(update={"emphasis": effective})
    AnalysisSelection.profile(selection_analysis, knowledge.profiles)
    manifest = AnalysisSelection.manifest(
        selection_analysis,
        knowledge,
        pinned_fact_ids=frozenset(pinned_fact_ids),
        excluded_fact_ids=frozenset(excluded_fact_ids),
    )
    provenance = (
        {"proposed_by": "ai", "proposal_rationale": ai_rationale.strip() or None}
        if ai_rationale is not None
        else {}
    )
    return manifest.model_copy(update={"emphasis_override": explicit, **provenance})


def compose_content(
    application_id: str,
    analysis_id: str,
    job_snapshot_id: str,
    analysis: JobAnalysis,
    selection: SelectionManifest,
    knowledge: Knowledge,
) -> DraftDocument:
    """The deterministic content one analysis and one selection produce."""
    try:
        return build_draft(
            application_id=application_id,
            job_snapshot_id=job_snapshot_id,
            job_analysis_id=analysis_id,
            analysis=analysis,
            profile=knowledge.profiles.get(analysis.profile),
            facts=knowledge.facts,
            policies=knowledge.policies,
            candidate=knowledge.candidate,
            presentations=knowledge.presentations,
            selection=selection,
        )
    except DomainMissingFactRendering as exc:
        raise MissingFactRendering(exc.fact_id, exc.language) from exc
    except ValueError as exc:
        raise PreconditionFailed(f"document content could not be built: {exc}") from exc


def refuse_authored_wording(content: DraftDocument | None) -> None:
    """A selection change may rebuild only content the engine composed (§14).

    Content carrying manual or AI wording is refused with a pointer to regeneration,
    before anything is written - or, for `propose_selection`, before a paid call.
    """
    if content is not None and carries_authored_wording(content):
        raise PreconditionFailed(
            "the document carries wording a deterministic rebuild would discard; use "
            "regenerate_section or regenerate_claim to change its selection",
            code=REGENERATION_REQUIRED,
        )


def selection_change_body(
    source: DocumentSource,
    knowledge: Knowledge,
    *,
    pinned_fact_ids: Iterable[str],
    excluded_fact_ids: Iterable[str],
    emphasis_override: str | None,
    ai_rationale: str | None = None,
) -> DocumentBody:
    """§14 `update_selection`, as the body it would write.

    Without content only the selection changes. With content, the change is applied
    atomically when it is deterministic: content the engine composed is recomposed
    from the new selection. Content carrying wording a rebuild would discard is a
    change that needs wording judgment, refused with a pointer to regeneration.
    An activated `propose_selection` writes through the same rule, with its
    rationale recorded as provenance.
    """
    document = source.document
    selection = build_document_selection(
        source.analysis,
        knowledge,
        current=document.selection,
        pinned_fact_ids=pinned_fact_ids,
        excluded_fact_ids=excluded_fact_ids,
        emphasis_override=emphasis_override,
        ai_rationale=ai_rationale,
    )
    content = document.content
    refuse_authored_wording(content)
    if content is not None:
        content = compose_content(
            document.application_id,
            document.analysis_id,
            source.job_snapshot_id,
            source.analysis,
            selection,
            knowledge,
        )
    return DocumentBody(analysis_id=document.analysis_id, selection=selection, content=content)


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
        selection=document.selection,
        policies=knowledge.policies,
        presentations=knowledge.presentations,
    )
