"""Structured edits to the single document (§14); no revision replacement lifecycle."""

from __future__ import annotations

import pytest
from helpers import stored_document
from pydantic import ValidationError

from cv_engine.application.commands import UpdateDocumentCommand


def test_patches_require_changes_and_cannot_edit_and_remove_the_same_claim():
    base = dict(application_id="app", expected_document_hash="a" * 64)
    with pytest.raises(ValidationError):
        UpdateDocumentCommand.model_validate(base)
    with pytest.raises(ValidationError):
        UpdateDocumentCommand.model_validate(
            {**base, "claim_edits": [{"claim_id": "c"}], "claim_removals": ["c"]}
        )


def test_reorder_preserves_claims_and_exact_undo_restores_the_hash(drafted_application):
    setup = drafted_application("Ordering")
    services, app_id = setup
    before = stored_document(services, app_id)
    assert before.content is not None
    section = next(s for s in before.content.sections if len(s.claims) > 1)
    order = [c.claim_id for c in section.claims]
    changed = services.drafts.update_document(
        UpdateDocumentCommand(
            application_id=app_id,
            expected_document_hash=before.document_hash,
            claim_orders={section.name: list(reversed(order))},
        )
    )
    assert changed.document_hash != before.document_hash
    restored = services.drafts.update_document(
        UpdateDocumentCommand(
            application_id=app_id,
            expected_document_hash=changed.document_hash,
            claim_orders={section.name: order},
        )
    )
    assert restored.document_hash == before.document_hash
    assert stored_document(services, app_id).content == before.content
