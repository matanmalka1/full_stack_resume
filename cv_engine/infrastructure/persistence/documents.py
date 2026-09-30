"""The one mutable CV document per Application, and the Submissions that freeze it.

state-and-use-cases.md §3, §14–§16 and §18. The store keeps what is stored and checks
only what it can check alone: `expected_document_hash` against the row it locked. It
never computes the basis and never decides a state; the application layer does both
from the document and the Knowledge it loads.

Every write naming `expected_document_hash` locks the row first, so the comparison and
the write see the same row, and a mismatch raises `StateConflict` before anything is
written - except `record_render_error`, whose mismatch is an expected outcome (§16) and
is reported by its return value.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from ...application.errors import DOCUMENT_CHANGED, LineageBroken, StateConflict, UnknownRecord
from ...application.ports.documents import DocumentBody, RenderedFiles
from ...application.ports.transactions import ReadTransaction, WriteTransaction
from ...domain.contracts.document import BuiltWith, CVDocument, DocumentSubmission
from ...domain.contracts.drafts import DraftDocument
from ...domain.contracts.validation import ValidationReport
from ...domain.document import document_hash
from ...util import new_id
from .connection import SqlAlchemyTransactionManager
from .tables import cv_documents, job_analyses, submissions


def _document_record(row: Any) -> CVDocument:
    record = dict(row)
    return CVDocument(
        id=record["id"],
        application_id=record["application_id"],
        analysis_id=record["analysis_id"],
        content=(
            None if record["content"] is None else DraftDocument.model_validate(record["content"])
        ),
        built_with=BuiltWith(profile_version=record["profile_version"]),
        document_hash=record["document_hash"],
        content_report=(
            None
            if record["content_report"] is None
            else ValidationReport.model_validate(record["content_report"])
        ),
        checked_basis=record["checked_basis"],
        passed=record["passed"],
        approved_basis=record["approved_basis"],
        approved_at=record["approved_at"],
        rendered_basis=record["rendered_basis"],
        html_path=record["html_path"],
        pdf_path=record["pdf_path"],
        last_render_error=record["last_render_error"],
        created_at=record["created_at"],
        updated_at=record["updated_at"],
    )


def _body_values(body: DocumentBody) -> dict[str, Any]:
    return {
        "analysis_id": body.analysis_id,
        "content": None if body.content is None else body.content.model_dump(mode="json"),
        "document_hash": document_hash(body.analysis_id, body.content),
    }


def _row(connection: Connection, application_id: str, *, lock: bool) -> Any:
    statement = select(cv_documents).where(cv_documents.c.application_id == application_id)
    if lock:
        statement = statement.with_for_update()
    return connection.execute(statement).mappings().one_or_none()


def _locked(connection: Connection, application_id: str, expected_document_hash: str) -> Any:
    """The document row under lock, refused unless it still holds the expected hash."""
    row = _row(connection, application_id, lock=True)
    if row is None:
        raise UnknownRecord(f"application {application_id} has no CV document")
    if row["document_hash"] != expected_document_hash:
        raise StateConflict(
            "the CV document changed since it was read (expected_document_hash): "
            f"expected {expected_document_hash}, found {row['document_hash']}",
            code=DOCUMENT_CHANGED,
        )
    return row


#: What a document without content carries: no check, approval, or render of any content.
_CLEARED_STAMPS: dict[str, Any] = {
    "content_report": None,
    "checked_basis": None,
    "passed": None,
    "approved_basis": None,
    "approved_at": None,
    "rendered_basis": None,
    "html_path": None,
    "pdf_path": None,
    "last_render_error": None,
}


def _rendered_files(row: Any) -> RenderedFiles | None:
    if row["html_path"] is None or row["pdf_path"] is None:
        return None
    return RenderedFiles(html=row["html_path"], pdf=row["pdf_path"])


def _require_owned_analysis(connection: Connection, application_id: str, analysis_id: str) -> None:
    owner = connection.execute(
        select(job_analyses.c.application_id).where(job_analyses.c.id == analysis_id)
    ).scalar_one_or_none()
    if owner is None:
        raise UnknownRecord(f"unknown job analysis: {analysis_id}")
    if owner != application_id:
        raise LineageBroken(
            f"job analysis {analysis_id} does not belong to application {application_id}"
        )


def _write(connection: Connection, document_id: str, values: dict[str, Any]) -> CVDocument:
    connection.execute(update(cv_documents).where(cv_documents.c.id == document_id).values(values))
    row = (
        connection.execute(select(cv_documents).where(cv_documents.c.id == document_id))
        .mappings()
        .one()
    )
    return _document_record(row)


class SqlAlchemyDocumentStore:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def document(self, tx: ReadTransaction, application_id: str) -> CVDocument | None:
        row = _row(self._transactions.connection_for(tx), application_id, lock=False)
        return None if row is None else _document_record(row)

    def lock_document(self, tx: WriteTransaction, application_id: str) -> CVDocument | None:
        connection = self._transactions.connection_for(tx, access="write")
        row = _row(connection, application_id, lock=True)
        return None if row is None else _document_record(row)

    def create_document(
        self,
        tx: WriteTransaction,
        application_id: str,
        body: DocumentBody,
        built_with: BuiltWith,
        *,
        created_at: str,
        document_id: str | None = None,
    ) -> CVDocument:
        connection = self._transactions.connection_for(tx, access="write")
        _require_owned_analysis(connection, application_id, body.analysis_id)
        identity = document_id or new_id()
        try:
            connection.execute(
                insert(cv_documents).values(
                    id=identity,
                    application_id=application_id,
                    **_body_values(body),
                    profile_version=built_with.profile_version,
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
        except IntegrityError as exc:
            raise StateConflict(f"application {application_id} already has a CV document") from exc
        row = (
            connection.execute(select(cv_documents).where(cv_documents.c.id == identity))
            .mappings()
            .one()
        )
        return _document_record(row)

    def update_body(
        self,
        tx: WriteTransaction,
        application_id: str,
        expected_document_hash: str,
        body: DocumentBody,
        *,
        updated_at: str,
    ) -> CVDocument:
        connection = self._transactions.connection_for(tx, access="write")
        row = _locked(connection, application_id, expected_document_hash)
        if body.analysis_id != row["analysis_id"]:
            raise LineageBroken(
                "a body update keeps the document's analysis; re-pinning is build_from_analysis"
            )
        if body.content is None and row["content"] is not None:
            raise LineageBroken("only build_from_analysis removes a document's content")
        return _write(connection, row["id"], {**_body_values(body), "updated_at": updated_at})

    def repin(
        self,
        tx: WriteTransaction,
        application_id: str,
        expected_document_hash: str,
        body: DocumentBody,
        built_with: BuiltWith,
        *,
        updated_at: str,
    ) -> tuple[CVDocument, RenderedFiles | None]:
        connection = self._transactions.connection_for(tx, access="write")
        row = _locked(connection, application_id, expected_document_hash)
        _require_owned_analysis(connection, application_id, body.analysis_id)
        if body.content is not None:
            raise LineageBroken("a re-pinned document starts without content")
        released = _rendered_files(row)
        document = _write(
            connection,
            row["id"],
            {
                **_body_values(body),
                "profile_version": built_with.profile_version,
                **_CLEARED_STAMPS,
                "updated_at": updated_at,
            },
        )
        return document, released

    def stamp_check(
        self,
        tx: WriteTransaction,
        application_id: str,
        expected_document_hash: str,
        report: ValidationReport,
        checked_basis: str,
        *,
        updated_at: str,
    ) -> CVDocument:
        connection = self._transactions.connection_for(tx, access="write")
        row = _locked(connection, application_id, expected_document_hash)
        return _write(
            connection,
            row["id"],
            {
                "content_report": report.model_dump(mode="json"),
                "checked_basis": checked_basis,
                "passed": report.passed,
                "updated_at": updated_at,
            },
        )

    def stamp_approval(
        self,
        tx: WriteTransaction,
        application_id: str,
        expected_document_hash: str,
        approved_basis: str,
        *,
        approved_at: str,
    ) -> CVDocument:
        connection = self._transactions.connection_for(tx, access="write")
        row = _locked(connection, application_id, expected_document_hash)
        return _write(
            connection,
            row["id"],
            {
                "approved_basis": approved_basis,
                "approved_at": approved_at,
                "updated_at": approved_at,
            },
        )

    def activate_render(
        self,
        tx: WriteTransaction,
        application_id: str,
        expected_document_hash: str,
        rendered_basis: str,
        files: RenderedFiles,
        *,
        updated_at: str,
    ) -> tuple[CVDocument, RenderedFiles | None]:
        connection = self._transactions.connection_for(tx, access="write")
        row = _locked(connection, application_id, expected_document_hash)
        superseded = _rendered_files(row)
        document = _write(
            connection,
            row["id"],
            {
                "rendered_basis": rendered_basis,
                "html_path": files.html,
                "pdf_path": files.pdf,
                "last_render_error": None,
                "updated_at": updated_at,
            },
        )
        if superseded == files:
            superseded = None
        return document, superseded

    def record_render_error(
        self,
        tx: WriteTransaction,
        application_id: str,
        expected_document_hash: str,
        error: dict[str, object],
        *,
        updated_at: str,
    ) -> bool:
        connection = self._transactions.connection_for(tx, access="write")
        row = _row(connection, application_id, lock=True)
        if row is None or row["document_hash"] != expected_document_hash:
            return False
        _write(connection, row["id"], {"last_render_error": error, "updated_at": updated_at})
        return True


def _submission_record(row: Any) -> DocumentSubmission:
    record = dict(row)
    return DocumentSubmission(
        id=record["id"],
        application_id=record["application_id"],
        submission_type=record["submission_type"],
        job_snapshot_id=record["job_snapshot_id"],
        document_hash=record["document_hash"],
        content=(
            None if record["content"] is None else DraftDocument.model_validate(record["content"])
        ),
        html_path=record["html_path"],
        html_sha256=record["html_sha256"],
        pdf_path=record["pdf_path"],
        pdf_sha256=record["pdf_sha256"],
        submitted_at=record["submitted_at"],
        metadata=record["metadata_json"] or {},
    )


class SqlAlchemyDocumentSubmissionStore:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def insert_submission(self, tx: WriteTransaction, submission: DocumentSubmission) -> None:
        connection = self._transactions.connection_for(tx, access="write")
        connection.execute(
            insert(submissions).values(
                id=submission.id,
                application_id=submission.application_id,
                submission_type=submission.submission_type,
                job_snapshot_id=submission.job_snapshot_id,
                document_hash=submission.document_hash,
                content=(
                    None
                    if submission.content is None
                    else submission.content.model_dump(mode="json")
                ),
                html_path=submission.html_path,
                html_sha256=submission.html_sha256,
                pdf_path=submission.pdf_path,
                pdf_sha256=submission.pdf_sha256,
                submitted_at=submission.submitted_at,
                metadata_json=submission.metadata,
            )
        )

    def submissions(self, tx: ReadTransaction, application_id: str) -> list[DocumentSubmission]:
        rows = (
            self._transactions.connection_for(tx)
            .execute(
                select(submissions)
                .where(submissions.c.application_id == application_id)
                .order_by(submissions.c.submitted_at, submissions.c.seq)
            )
            .mappings()
            .all()
        )
        return [_submission_record(row) for row in rows]
