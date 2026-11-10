"""Derived Ready (§16)."""

from __future__ import annotations

import pytest
from helpers import actor_of, stored_document

from cv_engine.application.commands import ClaimAddition, RenderCommand, UpdateDocumentCommand
from cv_engine.application.errors import (
    DOCUMENT_NOT_APPROVED,
    DOCUMENT_NOT_READY,
    PreconditionFailed,
)
from cv_engine.domain.document import PreparationState


def test_render_refuses_unapproved_content(drafted_application):
    setup = drafted_application("Not Ready")
    services, app_id = setup
    with pytest.raises(PreconditionFailed) as error:
        services.rendering.render(
            actor_of(services),
            RenderCommand(application_id=app_id, expected_document_hash=setup.document_hash),
        )
    assert error.value.code == DOCUMENT_NOT_APPROVED


def test_an_edit_after_ready_withdraws_the_recruiter_pdf(ready_application):
    setup = ready_application("Edited After Ready")
    services, app_id = setup
    document = stored_document(services, app_id)
    assert document.content is not None
    services.draft_editing.update_document(
        actor_of(services),
        UpdateDocumentCommand(
            application_id=app_id,
            expected_document_hash=document.document_hash,
            claim_additions=[
                ClaimAddition(section=document.content.sections[0].name, text="unsupported")
            ],
        ),
    )
    assert (
        services.queries.application_detail(actor_of(services), app_id).preparation_state
        is PreparationState.DRAFT_IN_PROGRESS
    )
    with pytest.raises(PreconditionFailed) as error:
        services.rendering.export_recruiter_pdf(actor_of(services), app_id)
    assert error.value.code == DOCUMENT_NOT_READY
