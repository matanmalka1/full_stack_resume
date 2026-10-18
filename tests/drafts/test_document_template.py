"""Choosing the template a CV renders with (state-and-use-cases.md §14)."""

from __future__ import annotations

import pytest
from helpers import (
    actor_of,
    approve_active_draft,
    seed_document,
    seed_draft,
    stored_document,
)

from cv_engine.application.commands import RenderCommand, SetDocumentTemplateCommand
from cv_engine.application.errors import StateConflict
from cv_engine.application.settings import UpdateSettings
from cv_engine.domain.document import PreparationState, document_hash


def _set(services, application_id: str, template: str | None, expected: str | None = None):
    document = stored_document(services, application_id)
    return services.draft_editing.set_document_template(
        actor_of(services),
        SetDocumentTemplateCommand(
            application_id=application_id,
            template=template,
            expected_document_hash=expected or document.document_hash,
        ),
    )


def _default(services, template: str | None) -> None:
    actor = actor_of(services)
    current = services.settings.read(actor)
    services.settings.update(
        actor,
        current.edit_version,
        UpdateSettings(
            **current.model_dump(include=set(UpdateSettings.model_fields) - {"default_template"}),
            default_template=template,
        ),
    )


def test_the_track_template_adds_nothing_to_the_document_hash() -> None:
    assert document_hash("analysis", None) == document_hash("analysis", None, None)
    assert document_hash("analysis", None, "latex") != document_hash("analysis", None)
    assert document_hash("analysis", None, "latex") != document_hash("analysis", None, "clean")


def test_a_new_document_starts_with_the_users_default_and_keeps_it(services) -> None:
    _default(services, "vivid")
    ingested, _ = seed_document(services, "Default Co")
    document = stored_document(services, ingested.application_id)
    assert document.template == "vivid"
    assert document.document_hash == document_hash(document.analysis_id, None, "vivid")

    # A later default never reaches an existing document.
    _default(services, "latex")
    assert stored_document(services, ingested.application_id).template == "vivid"
    other, _ = seed_document(services, "Later Co")
    assert stored_document(services, other.application_id).template == "latex"


def test_a_content_write_keeps_the_template_in_the_hash(services) -> None:
    ingested, _ = seed_document(services, "Keep Co")
    _set(services, ingested.application_id, "clean")
    seed_draft(services, ingested.application_id)
    document = stored_document(services, ingested.application_id)
    assert document.template == "clean"
    assert document.document_hash == document_hash(document.analysis_id, document.content, "clean")


def test_choosing_a_template_outdates_the_approval_and_the_render(
    services, deterministic_renderer
) -> None:
    ingested, _ = seed_document(services, "Template Co")
    application_id = ingested.application_id
    seed_draft(services, application_id)
    assert approve_active_draft(services, application_id).passed
    approved = stored_document(services, application_id)

    changed = _set(services, application_id, "latex")
    assert changed.document_hash != approved.document_hash
    assert changed.preparation_state == PreparationState.DRAFT_IN_PROGRESS
    document = stored_document(services, application_id)
    assert document.template == "latex"
    assert document.content == approved.content
    assert document.approved_basis == approved.approved_basis

    # The same template again changes nothing.
    again = _set(services, application_id, "latex")
    assert again.document_hash == changed.document_hash

    # A stale hash is refused and writes nothing.
    with pytest.raises(StateConflict):
        _set(services, application_id, "clean", expected=approved.document_hash)
    assert stored_document(services, application_id).template == "latex"

    preview = services.rendering.preview_document(actor_of(services), application_id)
    assert 'class="page t-latex"' in preview.html

    assert approve_active_draft(services, application_id).passed
    rendered = services.rendering.render(
        actor_of(services),
        RenderCommand(
            application_id=application_id,
            expected_document_hash=stored_document(services, application_id).document_hash,
        ),
    )
    assert rendered.validation.passed, rendered.validation.issues
    document = stored_document(services, application_id)
    html = (services.paths.root / document.html_path).read_text(encoding="utf-8")
    assert 'class="page t-latex"' in html

    # Back to the track's own template: the hash it had before any choice.
    back = _set(services, application_id, None)
    assert back.document_hash == document_hash(document.analysis_id, document.content)
