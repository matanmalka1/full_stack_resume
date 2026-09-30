"""§14: synchronous changes to the document's selection and its pin.

`update_selection` changes the selection in place and drops the content with it:
content is composed only by `create_draft`. `build_from_analysis` is the only command that changes the
document's `analysis_id`: it re-pins, rebuilds the selection, drops the content, and
clears every stamp in the same write.
"""

from __future__ import annotations

from ....domain.document import content_check, preparation_state
from ....util import utc_now
from ...commands import BuildFromAnalysisCommand, DocumentMutationResult, UpdateSelectionCommand
from ...errors import LineageBroken, PreconditionFailed
from ...ports import TransactionManager
from ...ports.analysis_plans import (
    AnalysisKnowledgeSource,
    AnalysisSelectionSourceReader,
    AnalysisStore,
)
from ...ports.documents import DocumentBody, DocumentFileStore, DocumentStore
from ..documents import (
    build_document_selection,
    built_with,
    changed_selection,
    current_basis,
    load_knowledge,
    read_document_source,
    refuse_deleted,
    require_hash,
)


class SelectionChangeService:
    """Own the synchronous selection and re-pin transactions."""

    def __init__(
        self,
        *,
        transactions: TransactionManager,
        documents: DocumentStore,
        sources: AnalysisSelectionSourceReader,
        analyses: AnalysisStore,
        files: DocumentFileStore,
        knowledge: AnalysisKnowledgeSource,
    ):
        self.transactions = transactions
        self.documents = documents
        self.sources = sources
        self.analyses = analyses
        self.files = files
        self.knowledge = knowledge

    def update_selection(self, command: UpdateSelectionCommand) -> DocumentMutationResult:
        """§14 `update_selection`: pin, exclude, or set the Emphasis override.

        Validated against the document's analysis and the current Knowledge. Content
        nobody has worded is dropped with the change, and the document is drafted
        again; content carrying wording is refused with `REGENERATION_REQUIRED`
        (writing nothing). Rendered files the document no longer references are
        discarded after commit.
        """
        with self.transactions.read() as tx:
            source = read_document_source(tx, self.documents, self.sources, command.application_id)
        refuse_deleted(command.application_id, source.deleted_at)
        require_hash(source.document, command.expected_document_hash)
        knowledge = load_knowledge(self.knowledge)
        selection = changed_selection(
            source,
            knowledge,
            pinned_fact_ids=command.pinned_fact_ids,
            excluded_fact_ids=command.excluded_fact_ids,
            emphasis_override=command.emphasis_override,
        )
        emphasis_changed = (
            command.emphasis_override is not None
            and selection.emphasis_override != source.document.selection.emphasis_override
        )
        with self.transactions.write() as tx:
            updated, released = self.documents.replace_selection(
                tx,
                command.application_id,
                command.expected_document_hash,
                selection,
                updated_at=utc_now(),
            )
            if emphasis_changed:
                self.analyses.set_matching_emphasis(
                    tx, command.application_id, selection.emphasis.value
                )
        if released is not None:
            self.files.discard(released)
        new_basis = current_basis(updated, knowledge)
        return DocumentMutationResult(
            application_id=command.application_id,
            document_id=updated.id,
            document_hash=updated.document_hash,
            preparation_state=preparation_state(updated, new_basis),
            content_check=content_check(updated, new_basis),
        )

    def build_from_analysis(self, command: BuildFromAnalysisCommand) -> DocumentMutationResult:
        """§14 `build_from_analysis`: re-pin the document to a named analysis.

        The previous rendered files are released by the same write and deleted
        best-effort after commit: nothing references them any more.
        """
        with self.transactions.read() as tx:
            source = read_document_source(tx, self.documents, self.sources, command.application_id)
            target = self.sources.selection_source(tx, command.analysis_id)
        refuse_deleted(command.application_id, source.deleted_at)
        require_hash(source.document, command.expected_document_hash)
        if target.application_id != command.application_id:
            raise LineageBroken(
                f"job analysis {command.analysis_id} does not belong to application "
                f"{command.application_id}"
            )
        if target.job_analysis_id == source.document.analysis_id:
            raise PreconditionFailed("the document is already built on this analysis")
        knowledge = load_knowledge(self.knowledge)
        selection = build_document_selection(target.analysis, knowledge)
        with self.transactions.write() as tx:
            updated, released = self.documents.repin(
                tx,
                command.application_id,
                command.expected_document_hash,
                DocumentBody(analysis_id=command.analysis_id, selection=selection, content=None),
                built_with(knowledge),
                updated_at=utc_now(),
            )
        if released is not None:
            self.files.discard(released)
        new_basis = current_basis(updated, knowledge)
        return DocumentMutationResult(
            application_id=command.application_id,
            document_id=updated.id,
            document_hash=updated.document_hash,
            preparation_state=preparation_state(updated, new_basis),
            content_check=content_check(updated, new_basis),
        )
