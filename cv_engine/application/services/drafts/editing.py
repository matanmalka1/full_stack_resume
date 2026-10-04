"""§14 autosave: the user's own edits to the CV document, applied as one patch.

Kept apart from authoring because nothing here reaches a provider: a manual edit is a
deterministic patch against one exact hash, while authoring is the AI's generation and
regeneration. Free text the facts do not support is saved `pending`; reviewing it is the
`regenerate_claim` Operation with `keep_text`, never part of the save.
"""

from __future__ import annotations

from ....domain.document import content_check, preparation_state
from ....domain.drafts import add_claim, apply_claim_edit, draft_claims, remove_claim, reorder_draft
from ....util import utc_now
from ...commands import DocumentMutationResult, UpdateDocumentCommand
from ...errors import PreconditionFailed, UnknownRecord
from ...ports import TransactionManager
from ...ports.analysis_plans import AnalysisContextSourceReader, AnalysisKnowledgeSource
from ...ports.documents import DocumentBody, DocumentStore
from ..documents import (
    current_basis,
    load_knowledge,
    read_document_source,
    refuse_deleted,
    require_hash,
)


class DraftEditingService:
    def __init__(
        self,
        *,
        transactions: TransactionManager,
        documents: DocumentStore,
        sources: AnalysisContextSourceReader,
        knowledge: AnalysisKnowledgeSource,
    ):
        self.transactions = transactions
        self.documents = documents
        self.sources = sources
        self._knowledge = knowledge

    def update_document(self, command: UpdateDocumentCommand) -> DocumentMutationResult:
        """§14 autosave: apply one structured patch against one exact hash.

        The whole patch commits as a single write. Nothing here validates: §15 owns
        the content report, and a check on every keystroke would make a passed report
        mean "recently saved" instead of "recently checked". Editing an approved or
        ready document is allowed; it changes the basis, so the document returns to
        draft on the next read.
        """
        with self.transactions.read() as tx:
            source = read_document_source(tx, self.documents, self.sources, command.application_id)
        refuse_deleted(command.application_id, source.deleted_at)
        require_hash(source.document, command.expected_document_hash)
        document = source.document
        if document.content is None:
            raise PreconditionFailed("the document has no content to edit yet; create a draft")
        knowledge = load_knowledge(self._knowledge)
        facts = knowledge.facts
        patched = document.content
        for edit in command.claim_edits:
            try:
                patched = apply_claim_edit(
                    patched,
                    edit.claim_id,
                    list(edit.fact_ids),
                    facts,
                    text=edit.text,
                    template_id=edit.template_id,
                    template_version=edit.template_version,
                )
            except KeyError as exc:
                raise UnknownRecord(f"unknown claim in the document: {edit.claim_id}") from exc
            except ValueError as exc:
                raise PreconditionFailed(f"claim edit rejected: {exc}") from exc
        for claim_id in command.claim_removals:
            try:
                patched = remove_claim(patched, claim_id)
            except KeyError as exc:
                raise UnknownRecord(f"unknown claim in the document: {claim_id}") from exc
            except ValueError as exc:
                raise PreconditionFailed(f"claim removal rejected: {exc}") from exc
        added_claim_ids: set[str] = set()
        for addition in command.claim_additions:
            try:
                patched, new_claim_id = add_claim(patched, addition.section, addition.text)
            except KeyError as exc:
                raise UnknownRecord(f"unknown section in the document: {addition.section}") from exc
            except ValueError as exc:
                raise PreconditionFailed(f"claim addition rejected: {exc}") from exc
            added_claim_ids.add(new_claim_id)
        try:
            patched = reorder_draft(patched, claim_orders=command.claim_orders)
        except KeyError as exc:
            raise UnknownRecord(f"unknown section in the document: {exc.args[0]}") from exc
        except ValueError as exc:
            raise PreconditionFailed(f"document reorder rejected: {exc}") from exc
        with self.transactions.write() as tx:
            updated = self.documents.update_body(
                tx,
                command.application_id,
                command.expected_document_hash,
                DocumentBody(analysis_id=document.analysis_id, content=patched),
                updated_at=utc_now(),
            )
        edited = {edit.claim_id for edit in command.claim_edits} | added_claim_ids
        new_basis = current_basis(updated, knowledge)
        return DocumentMutationResult(
            application_id=command.application_id,
            document_id=updated.id,
            document_hash=updated.document_hash,
            preparation_state=preparation_state(updated, new_basis),
            content_check=content_check(updated, new_basis),
            pending_claim_ids=sorted(
                claim.claim_id
                for claim in draft_claims(patched)
                if claim.claim_type == "pending" and claim.claim_id in edited
            ),
        )
