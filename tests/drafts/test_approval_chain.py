from __future__ import annotations

import json
from pathlib import Path

from cv_engine.runtime.composition import Services


def test_the_requirement_vocabulary_stales_an_analysis_and_nothing_after_it(
    services: Services, project_root: Path
) -> None:
    """A draft consumes the analysis, never the vocabulary that produced it.

    One hash covered every dependency, so editing `config/requirements.json`
    declared the inputs of a draft, its validation, its approval and a render
    changed - none of which read that file. A submitted draft then failed
    activation, and a recorded validation stopped describing its own draft,
    because a file they had never opened moved.
    """
    knowledge = services.knowledge.load()
    before_analysis = knowledge.context_hash()
    before_document = knowledge.document_context_hash()
    assert before_analysis != before_document, "the two scopes must not be the same hash"
    assert set(knowledge.versions()) - set(knowledge.document_versions()) == {
        "requirement_concepts"
    }

    concepts = project_root / "config" / "requirements.json"
    payload = json.loads(concepts.read_text(encoding="utf-8"))
    payload["policy_version"] = "changed-for-this-test"
    concepts.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    after = services.knowledge.load()
    assert after.context_hash() != before_analysis, "the analysis must see the vocabulary move"
    assert after.document_context_hash() == before_document

    # The exclusion is justified by consumption, so consumption is what is
    # checked. Derived from the package rather than from a list of stages: a
    # module that starts reading the vocabulary and is not registered here
    # fails, because the document scope would then be excluding a dependency
    # that stage really has.
    allowed = {
        # Where the store is defined, loaded, and reported.
        Path("cv_engine/domain/knowledge.py"),
        Path("cv_engine/infrastructure/knowledge.py"),
        Path("cv_engine/api/routers/health.py"),
        Path("cv_engine/api/schemas/health.py"),
        Path("cv_engine/application/commands/knowledge.py"),
        # Preparation and interpretation correction consume it.
        Path("cv_engine/application/services/analysis/preparation.py"),
        Path("cv_engine/application/services/analysis/correction.py"),
    }
    root = Path(__file__).resolve().parents[2]
    readers = {
        path.relative_to(root)
        for path in (root / "cv_engine").rglob("*.py")
        if "requirement_concepts" in path.read_text(encoding="utf-8")
    }
    assert readers <= allowed, (
        "these read the requirement vocabulary but are excluded from the document "
        f"knowledge scope: {sorted(str(path) for path in readers - allowed)}"
    )


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
