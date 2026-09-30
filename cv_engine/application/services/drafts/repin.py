"""§14 `build_from_analysis`: the only command that changes the document's `analysis_id`.

It re-pins, drops the content, and clears every stamp in the same write.
"""

from __future__ import annotations

from ....domain.document import content_check, preparation_state
from ....util import utc_now
from ...commands import BuildFromAnalysisCommand, DocumentMutationResult
from ...errors import LineageBroken, PreconditionFailed
from ...ports import TransactionManager
from ...ports.analysis_plans import AnalysisKnowledgeSource, AnalysisSelectionSourceReader
from ...ports.documents import DocumentBody, DocumentFileStore, DocumentStore
from ..documents import (
    built_with,
    current_basis,
    load_knowledge,
    read_document_source,
    refuse_deleted,
    require_hash,
)


class RepinService:
    """Own the synchronous re-pin transaction."""

    def __init__(
        self,
        *,
        transactions: TransactionManager,
        documents: DocumentStore,
        sources: AnalysisSelectionSourceReader,
        files: DocumentFileStore,
        knowledge: AnalysisKnowledgeSource,
    ):
        self.transactions = transactions
        self.documents = documents
        self.sources = sources
        self.files = files
        self.knowledge = knowledge

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
        with self.transactions.write() as tx:
            updated, released = self.documents.repin(
                tx,
                command.application_id,
                command.expected_document_hash,
                DocumentBody(analysis_id=command.analysis_id, content=None),
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
