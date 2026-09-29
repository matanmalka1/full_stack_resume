"""§15 `check_document`: validate the content and store the report with its basis."""

from __future__ import annotations

from ....domain.document import content_check, preparation_state
from ....util import utc_now
from ...commands import CheckDocumentCommand, DocumentCheckResult
from ...errors import PreconditionFailed
from ...ports import TransactionManager
from ...ports.analysis_plans import AnalysisKnowledgeSource, AnalysisSelectionSourceReader
from ...ports.documents import DocumentStore
from ..documents import (
    current_basis,
    load_knowledge,
    read_document_source,
    refuse_deleted,
    require_hash,
    validate_document,
)


class DraftValidationService:
    """The content check, stored whether or not it passed."""

    def __init__(
        self,
        *,
        transactions: TransactionManager,
        documents: DocumentStore,
        sources: AnalysisSelectionSourceReader,
        knowledge: AnalysisKnowledgeSource,
    ):
        self.transactions = transactions
        self.documents = documents
        self.sources = sources
        self.knowledge = knowledge

    def check_document(self, command: CheckDocumentCommand) -> DocumentCheckResult:
        """§15: run the validation contract and store `content_report`, `passed`, basis.

        `passed=false` is an outcome, not an error: the report is stored either way,
        because a failed check is exactly the evidence the user needs. A validator
        that could not execute is an application/infrastructure error and stores
        nothing. No provider is called.
        """
        with self.transactions.read() as tx:
            source = read_document_source(tx, self.documents, self.sources, command.application_id)
        refuse_deleted(command.application_id, source.deleted_at)
        require_hash(source.document, command.expected_document_hash)
        if source.document.content is None:
            raise PreconditionFailed("the document has no content to check yet")
        knowledge = load_knowledge(self.knowledge)
        report = validate_document(source, knowledge)
        checked = current_basis(source.document, knowledge)
        with self.transactions.write() as tx:
            updated = self.documents.stamp_check(
                tx,
                command.application_id,
                command.expected_document_hash,
                report,
                checked,
                updated_at=utc_now(),
            )
        return DocumentCheckResult(
            application_id=command.application_id,
            document_id=updated.id,
            document_hash=updated.document_hash,
            preparation_state=preparation_state(updated, checked),
            content_check=content_check(updated, checked),
            passed=report.passed,
            report=report,
            approved_at=updated.approved_at if updated.approved_basis == checked else None,
        )
