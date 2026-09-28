from __future__ import annotations

from helpers import stored_document
from helpers import working_claim as _working_claim

from cv_engine.application.commands import ClaimPatch, UpdateDocumentCommand


def test_style_safe_composite_edit_joins_two_canonical_facts(drafted_application) -> None:
    """Editing one claim onto two facts through a template makes it composite.

    The subject is the edit, not any one caller: `PATCH /applications/{id}/document`
    and the draft service reach the same method, so this drives the service.
    """
    services, app_id = drafted_application("Composite edit")
    claim = _working_claim(services, app_id, "sales.metric.recurring_customers")

    services.drafts.update_document(
        UpdateDocumentCommand(
            application_id=app_id,
            expected_document_hash=stored_document(services, app_id).document_hash,
            claim_edits=[
                ClaimPatch(
                    claim_id=claim.claim_id,
                    fact_ids=["sales.metric.recurring_customers", "sales.metric.performance"],
                    template_id="canonical-renderings",
                )
            ],
        )
    )

    assert (
        _working_claim(services, app_id, "sales.metric.recurring_customers").claim_type
        == "composite"
    )
