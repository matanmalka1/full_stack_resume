from __future__ import annotations


def test_exact_undo_restores_approval_and_reapproval_refreshes_only_the_check(approved_application):
    """§3/§15: returning to identical content restores the stamp, not a new approval."""
    from helpers import approve_active_draft, stored_document, validate_active_draft

    from cv_engine.application.commands import UpdateDocumentCommand
    from cv_engine.domain.document import ContentCheck, PreparationState

    setup = approved_application("Undo Approval")
    services, app_id = setup
    original = stored_document(services, app_id)
    assert original.content is not None
    section = next(s for s in original.content.sections if len(s.claims) > 1)
    order = [c.claim_id for c in section.claims]
    changed = services.drafts.update_document(
        UpdateDocumentCommand(
            application_id=app_id,
            expected_document_hash=original.document_hash,
            claim_orders={section.name: list(reversed(order))},
        )
    )
    assert changed.preparation_state is PreparationState.DRAFT_IN_PROGRESS
    validate_active_draft(services, app_id)
    restored = services.drafts.update_document(
        UpdateDocumentCommand(
            application_id=app_id,
            expected_document_hash=changed.document_hash,
            claim_orders={section.name: order},
        )
    )
    assert restored.document_hash == original.document_hash
    assert restored.preparation_state is PreparationState.APPROVED
    assert restored.content_check is ContentCheck.OUTDATED
    approved = approve_active_draft(services, app_id)
    assert approved.passed and approved.approved_at == original.approved_at
    checked = stored_document(services, app_id)
    assert checked.checked_basis == original.approved_basis == checked.approved_basis
