"""Ports for the one mutable CV document, its rendered files, and its Submissions.

state-and-use-cases.md §3, §14–§16 and §18. The store keeps what is stored and checks
only what it can check alone: `expected_document_hash` against the row it locked. It
never computes the basis — that needs the Knowledge, which the application layer loads
and compares under the same lock — and it never decides a state.

Every write that names `expected_document_hash` raises `StateConflict` when the row
holds another hash and writes nothing, except `record_render_error`, whose mismatch is
an expected outcome (§16) and is reported by its return value.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ...domain.contracts.document import BuiltWith, CVDocument, DocumentSubmission
from ...domain.contracts.drafts import DraftDocument
from ...domain.contracts.selection import SelectionManifest
from ...domain.contracts.validation import ValidationReport
from .transactions import ReadTransaction, WriteTransaction
from .values import ArtifactStream


@dataclass(frozen=True)
class DocumentBody:
    """The hashed part of the document. The store derives `document_hash` from it."""

    analysis_id: str
    selection: SelectionManifest
    content: DraftDocument | None


@dataclass(frozen=True)
class RenderedFiles:
    """References to one render's two files, as the file store names them."""

    html: str
    pdf: str


@dataclass(frozen=True)
class SubmittedFiles:
    html_path: str
    html_sha256: str
    pdf_path: str
    pdf_sha256: str


class DocumentStore(Protocol):
    def document(self, tx: ReadTransaction, application_id: str) -> CVDocument | None: ...

    def lock_document(self, tx: WriteTransaction, application_id: str) -> CVDocument | None:
        """Read the row under a lock held until the transaction ends."""
        ...

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
        """Create the Application's only document; a second one is a `StateConflict`."""
        ...

    def update_body(
        self,
        tx: WriteTransaction,
        application_id: str,
        expected_document_hash: str,
        body: DocumentBody,
        *,
        updated_at: str,
    ) -> CVDocument:
        """Replace selection and/or content under the same analysis; stamps are kept.

        A kept stamp is simply outdated from here on, because the basis moved.
        `body.analysis_id` must equal the stored one; re-pinning is `repin`.
        """
        ...

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
        """`build_from_analysis`: new analysis and selection, no content, no stamps.

        Returns the rendered files the document no longer references, for the caller to
        discard after commit.
        """
        ...

    def stamp_check(
        self,
        tx: WriteTransaction,
        application_id: str,
        expected_document_hash: str,
        report: ValidationReport,
        checked_basis: str,
        *,
        updated_at: str,
    ) -> CVDocument: ...

    def stamp_approval(
        self,
        tx: WriteTransaction,
        application_id: str,
        expected_document_hash: str,
        approved_basis: str,
        *,
        approved_at: str,
    ) -> CVDocument: ...

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
        """Swap in the new files, stamp `rendered_basis`, clear `last_render_error`.

        The only writer of `rendered_basis`. Returns the superseded files, if any, for
        best-effort deletion after commit.
        """
        ...

    def record_render_error(
        self,
        tx: WriteTransaction,
        application_id: str,
        expected_document_hash: str,
        error: dict[str, object],
        *,
        updated_at: str,
    ) -> bool:
        """Record the failure only while the hash still matches; False when it did not."""
        ...


class DocumentFileStore(Protocol):
    """The document's mutable rendered files and the immutable copies a Submission owns."""

    def render_targets(self, application_id: str, attempt_id: str) -> tuple[Path, Path]:
        """Unique per-attempt HTML and PDF paths for one render."""
        ...

    def reference_for(self, path: Path) -> str: ...

    def discard(self, files: RenderedFiles) -> None:
        """Best-effort deletion; a file already gone is not an error."""
        ...

    def open_rendered_pdf(self, reference: str) -> ArtifactStream:
        """Contained read of a document's current PDF; a missing file is an error."""
        ...

    def copy_for_submission(
        self, application_id: str, submission_id: str, files: RenderedFiles
    ) -> SubmittedFiles:
        """Copy under a payload write lease and hash what was copied."""
        ...


class DocumentSubmissionStore(Protocol):
    def insert_submission(self, tx: WriteTransaction, submission: DocumentSubmission) -> None: ...

    def submissions(self, tx: ReadTransaction, application_id: str) -> list[DocumentSubmission]: ...
