"""§18: recording a send that already happened, and freezing what was sent.

An internal Submission copies the document's content and its rendered files to
submission-owned, immutable paths, with a SHA-256 per file. The copy happens
before the database transaction; the transaction then
re-checks the document under its row lock and inserts the Submission, the status
transition and the audit record together. It is not a validation gate: it requires
the document to be Ready at the basis computed now, and nothing else.
"""

from __future__ import annotations

from typing import Literal

from ....domain.contracts.document import DocumentSubmission
from ....domain.contracts.records import AuditRecord
from ....domain.contracts.recruitment import ApplicationStatus
from ....domain.document import DocumentState, document_state
from ....domain.recruitment import terminal_outcome_after
from ....util import new_id
from ...commands import ExternalSubmissionCommand, SubmissionCommand, SubmissionResult, WriteClient
from ...errors import (
    DOCUMENT_NOT_READY,
    ApplicationError,
    InfrastructureFailure,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
)
from ...ports.analysis_plans import AnalysisContextSourceReader, AnalysisKnowledgeSource
from ...ports.application_intake import AuditLogWriter
from ...ports.documents import (
    DocumentFileStore,
    DocumentStore,
    DocumentSubmissionStore,
    RenderedFiles,
)
from ...ports.recruitment import RecruitmentStore
from ...ports.transactions import TransactionManager, WriteTransaction
from ..documents import (
    current_basis,
    load_knowledge,
    read_document_source,
    refuse_deleted,
    refuse_review_reasons,
    require_hash,
)


class SubmissionService:
    def __init__(
        self,
        *,
        transactions: TransactionManager,
        documents: DocumentStore,
        sources: AnalysisContextSourceReader,
        submissions: DocumentSubmissionStore,
        files: DocumentFileStore,
        recruitment: RecruitmentStore,
        audit: AuditLogWriter,
        knowledge: AnalysisKnowledgeSource,
    ):
        self._transactions = transactions
        self._documents = documents
        self._sources = sources
        self._submissions = submissions
        self._files = files
        self._recruitment = recruitment
        self._audit = audit
        self._knowledge = knowledge

    def _active_application(self, application_id: str) -> dict:
        try:
            with self._transactions.read() as tx:
                application = self._recruitment.application(tx, application_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown application: {application_id}") from exc
        refuse_deleted(application_id, application.get("deleted_at"))
        return application

    def submit_application(self, command: SubmissionCommand) -> SubmissionResult:
        """§18: freeze the Ready document the client showed, and record that it was sent."""
        self._active_application(command.application_id)
        with self._transactions.read() as tx:
            source = read_document_source(
                tx, self._documents, self._sources, command.application_id
            )
        document = source.document
        require_hash(document, command.expected_document_hash)
        knowledge = load_knowledge(self._knowledge)
        submitted_basis = current_basis(document, knowledge)
        if (
            document_state(document, submitted_basis) is not DocumentState.READY
            or document.html_path is None
            or document.pdf_path is None
            or document.content is None
        ):
            raise PreconditionFailed(
                "only a Ready document can be recorded as submitted", code=DOCUMENT_NOT_READY
            )
        refuse_review_reasons(document, knowledge)
        submission_id = new_id()
        try:
            copied = self._files.copy_for_submission(
                command.application_id,
                submission_id,
                RenderedFiles(html=document.html_path, pdf=document.pdf_path),
            )
        except (ApplicationError, OSError, ValueError) as exc:
            if isinstance(exc, ApplicationError):
                raise
            raise InfrastructureFailure(f"could not copy the submitted files: {exc}") from exc
        warnings = ["DOCUMENT_ON_OLDER_ANALYSIS"] if source.on_older_analysis else []

        def insert(tx: WriteTransaction) -> None:
            locked = self._documents.lock_document(tx, command.application_id)
            if locked is None:
                raise StateConflict("the document no longer exists")
            require_hash(locked, command.expected_document_hash)
            if not (
                locked.rendered_basis == submitted_basis
                and locked.approved_basis == submitted_basis
                and locked.html_path == document.html_path
                and locked.pdf_path == document.pdf_path
            ):
                raise PreconditionFailed(
                    "the document stopped being Ready while it was submitted",
                    code=DOCUMENT_NOT_READY,
                )
            self._submissions.insert_submission(
                tx,
                DocumentSubmission(
                    id=submission_id,
                    application_id=command.application_id,
                    submission_type="internal",
                    job_snapshot_id=source.job_snapshot_id,
                    document_hash=locked.document_hash,
                    content=locked.content,
                    html_path=copied.html_path,
                    html_sha256=copied.html_sha256,
                    pdf_path=copied.pdf_path,
                    pdf_sha256=copied.pdf_sha256,
                    submitted_at=command.submitted_at,
                    metadata=command.metadata,
                ),
            )

        return self._record(
            command.application_id,
            submission_id,
            "internal",
            insert,
            command.submitted_at,
            command.actor_type,
            command.client,
            warnings,
            document_hash=document.document_hash,
        )

    def record_external_submission(self, command: ExternalSubmissionCommand) -> SubmissionResult:
        """§18: a submission made outside the system; it carries no content or files."""
        self._active_application(command.application_id)
        submission_id = new_id()

        def insert(tx: WriteTransaction) -> None:
            self._submissions.insert_submission(
                tx,
                DocumentSubmission(
                    id=submission_id,
                    application_id=command.application_id,
                    submission_type="external",
                    submitted_at=command.submitted_at,
                    metadata=command.metadata,
                ),
            )

        return self._record(
            command.application_id,
            submission_id,
            "external",
            insert,
            command.submitted_at,
            command.actor_type,
            command.client,
            [],
        )

    def _record(
        self,
        application_id: str,
        submission_id: str,
        submission_type: str,
        insert,
        submitted_at: str,
        actor_type: Literal["user", "system"],
        client: WriteClient,
        warnings: list[str],
        *,
        document_hash: str | None = None,
    ) -> SubmissionResult:
        """Insert the Submission, transition to `applied` once, and audit, atomically."""
        event_id = None
        with self._transactions.write() as tx:
            application = self._recruitment.application(tx, application_id)
            refuse_deleted(application_id, application.get("deleted_at"))
            current = ApplicationStatus(application["current_status"])
            insert(tx)
            if current is ApplicationStatus.SAVED:
                event_id = self._recruitment.insert_event(
                    tx,
                    application_id=application_id,
                    expected_current_status=current.value,
                    target_status="applied",
                    event_type="status_transition",
                    reason="submission recorded",
                    actor_type=actor_type,
                    client=client,
                    occurred_at=submitted_at,
                    terminal_outcome=terminal_outcome_after(
                        application.get("terminal_outcome"), ApplicationStatus.APPLIED
                    ),
                )
            self._audit.insert_audit(
                tx,
                AuditRecord(
                    id=new_id(),
                    application_id=application_id,
                    action="submit_application"
                    if submission_type == "internal"
                    else "record_external_submission",
                    entity_type="submission",
                    entity_id=submission_id,
                    actor_type=actor_type,
                    client=client,
                    occurred_at=submitted_at,
                    details={"submission_type": submission_type, "document_hash": document_hash},
                ),
            )
        with self._transactions.read() as tx:
            updated = self._recruitment.application(tx, application_id)
        return SubmissionResult(
            application_id=application_id,
            submission_id=submission_id,
            document_hash=document_hash,
            current_status=updated["current_status"],
            terminal_outcome=updated.get("terminal_outcome"),
            next_action=updated.get("next_action"),
            next_action_date=updated.get("next_action_date"),
            event_id=event_id,
            warnings=warnings,
        )
