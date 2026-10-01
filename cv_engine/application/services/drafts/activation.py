"""Content activation in a caller-owned transaction, with no external effects."""

from __future__ import annotations

from ....util import utc_now
from ...commands import DraftResult, RegenerationResult
from ...errors import StateConflict
from ...ports.documents import DocumentBody, DocumentStore
from ...ports.transactions import WriteTransaction
from .inputs import PreparedDraft, PreparedRegeneration


class DraftActivation:
    def __init__(self, documents: DocumentStore):
        self.documents = documents

    def _current(self, tx: WriteTransaction, application_id: str, expected_document_hash: str):
        document = self.documents.lock_document(tx, application_id)
        if document is None:
            raise StateConflict(f"application {application_id} has no CV document")
        if document.document_hash != expected_document_hash:
            raise StateConflict("the CV document changed while its content was generated")
        return document

    def activate_generation(self, tx: WriteTransaction, prepared: PreparedDraft) -> DraftResult:
        """Write generated content while the document still holds the expected hash.

        Draft-producing activation does not recheck input freshness (§11): its output
        is unapproved, and check/approve/render validate against the current context.
        """
        document = self._current(tx, prepared.application_id, prepared.expected_document_hash)
        if document.content is not None:
            raise StateConflict("the document already has content")
        updated = self.documents.update_body(
            tx,
            prepared.application_id,
            prepared.expected_document_hash,
            DocumentBody(analysis_id=document.analysis_id, content=prepared.content),
            updated_at=utc_now(),
        )
        return DraftResult(
            application_id=prepared.application_id,
            document_id=updated.id,
            document_hash=updated.document_hash,
        )

    def activate_regeneration(
        self, tx: WriteTransaction, prepared: PreparedRegeneration
    ) -> RegenerationResult:
        """Commit regenerated wording against the exact hash that was read.

        Every provider call is already in the AI call log; the runner completes the
        Operation in this same transaction, together with the wording it produced.
        """
        document = self._current(tx, prepared.application_id, prepared.expected_document_hash)
        updated = self.documents.update_body(
            tx,
            prepared.application_id,
            prepared.expected_document_hash,
            DocumentBody(analysis_id=document.analysis_id, content=prepared.content),
            updated_at=utc_now(),
        )
        return RegenerationResult(
            application_id=prepared.application_id,
            document_id=updated.id,
            document_hash=updated.document_hash,
            regenerated_claim_ids=list(prepared.claim_ids),
            ai_call_id=prepared.ai_call_id,
        )
