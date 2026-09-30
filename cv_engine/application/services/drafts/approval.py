"""§15 `approve_document`: check and approve in one synchronous action."""

from __future__ import annotations

from ....domain.contracts.document import CVDocument
from ....domain.contracts.records import AuditRecord
from ....domain.contracts.validation import ValidationReport
from ....domain.document import content_check, preparation_state
from ....domain.knowledge import Knowledge
from ....util import new_id, utc_now
from ...commands import ApproveDocumentCommand, DocumentCheckResult
from ...errors import KNOWLEDGE_RECONCILIATION_REQUIRED, PreconditionFailed
from ...ports import TransactionManager
from ...ports.analysis_plans import AnalysisContextSourceReader, AnalysisKnowledgeSource
from ...ports.application_intake import AuditLogWriter
from ...ports.documents import DocumentStore
from ...ports.knowledge_lifecycle import KnowledgeLifecycleStore
from ..documents import (
    current_basis,
    load_knowledge,
    read_document_source,
    refuse_deleted,
    refuse_review_reasons,
    require_hash,
    validate_document,
)


class DraftApprovalService:
    """The approval boundary: the report, then the stamp, under the document row lock."""

    def __init__(
        self,
        *,
        transactions: TransactionManager,
        documents: DocumentStore,
        sources: AnalysisContextSourceReader,
        knowledge: AnalysisKnowledgeSource,
        journal: KnowledgeLifecycleStore,
        audit: AuditLogWriter,
    ):
        self.transactions = transactions
        self.documents = documents
        self.sources = sources
        self.knowledge = knowledge
        self.journal = journal
        self.audit = audit

    @staticmethod
    def _result(
        document: CVDocument, knowledge_basis: str, report: ValidationReport
    ) -> DocumentCheckResult:
        return DocumentCheckResult(
            application_id=document.application_id,
            document_id=document.id,
            document_hash=document.document_hash,
            preparation_state=preparation_state(document, knowledge_basis),
            content_check=content_check(document, knowledge_basis),
            passed=report.passed,
            report=report,
            approved_at=(
                document.approved_at if document.approved_basis == knowledge_basis else None
            ),
        )

    @classmethod
    def _existing_approval(
        cls, document: CVDocument, approval_basis: str
    ) -> DocumentCheckResult | None:
        """The existing approval is the answer only while its report is current too.

        A document can return to an approved basis with a report checked at another
        one - an edit and its exact undo. The stored report then describes other
        content, so approval re-checks and stores the report, and keeps the existing
        approval stamp rather than rewriting `approved_at`.
        """
        report = document.content_report
        if (
            report is None
            or document.approved_basis != approval_basis
            or document.checked_basis != approval_basis
        ):
            return None
        return cls._result(document, approval_basis, report)

    def _refuse_quarantined_knowledge(self) -> None:
        with self.transactions.read() as tx:
            quarantined = self.journal.quarantined_mutations(tx)
        if quarantined:
            raise PreconditionFailed(
                f"approval blocked by quarantined Knowledge mutation {quarantined[0].id}",
                code=KNOWLEDGE_RECONCILIATION_REQUIRED,
            )

    def approve_document(self, command: ApproveDocumentCommand) -> DocumentCheckResult:
        """§15: run `check_document`'s validation and approve in one action.

        The report and `checked_basis` are always stored when the check runs;
        `approved_basis` and `approved_at` only when the report passed. A review
        reason or other blocker is refused with a precondition naming it, before
        anything is written. Approving a document already approved at its current
        basis returns that approval: `approved_at` is not rewritten and no audit
        record is appended.
        """
        with self.transactions.read() as tx:
            source = read_document_source(tx, self.documents, self.sources, command.application_id)
        refuse_deleted(command.application_id, source.deleted_at)
        document = source.document
        require_hash(document, command.expected_document_hash)
        if document.content is None:
            raise PreconditionFailed("the document has no content to approve yet")
        knowledge: Knowledge = load_knowledge(self.knowledge)
        approval_basis = current_basis(document, knowledge)
        existing = self._existing_approval(document, approval_basis)
        if existing is not None:
            return existing
        self._refuse_quarantined_knowledge()
        refuse_review_reasons(document, knowledge)
        report = validate_document(source, knowledge)
        now = utc_now()
        with self.transactions.write() as tx:
            locked = self.documents.lock_document(tx, command.application_id)
            if locked is None:
                raise PreconditionFailed("the document no longer exists")
            require_hash(locked, command.expected_document_hash)
            existing = self._existing_approval(locked, approval_basis)
            if existing is not None:
                # Approved by a concurrent request at this same basis: same answer.
                return existing
            updated = self.documents.stamp_check(
                tx,
                command.application_id,
                command.expected_document_hash,
                report,
                approval_basis,
                updated_at=now,
            )
            if report.passed and locked.approved_basis != approval_basis:
                updated = self.documents.stamp_approval(
                    tx,
                    command.application_id,
                    command.expected_document_hash,
                    approval_basis,
                    approved_at=now,
                )
                self.audit.insert_audit(
                    tx,
                    AuditRecord(
                        id=new_id(),
                        application_id=command.application_id,
                        action="approve_document",
                        entity_type="cv_document",
                        entity_id=updated.id,
                        actor_type=command.actor_type,
                        client=command.client,
                        occurred_at=now,
                        details={
                            "document_hash": updated.document_hash,
                            "approved_basis": approval_basis,
                        },
                    ),
                )
        return self._result(updated, approval_basis, report)
