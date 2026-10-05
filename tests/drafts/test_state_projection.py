"""The CV document's commands, driven through the application services and PostgreSQL.

state-and-use-cases.md §3–§9 and §13–§18; test-and-acceptance-plan §5.1, §5.3, §5.5,
§5.6 and §14. Each scenario asserts the projection a client would read after every
step, because the projection - not the stored stamps - is what the document's state is.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from helpers import (
    persisted_counts,
    seed_document,
    seed_draft,
    seed_existing_analysis,
    stored_document,
    stored_submissions,
)

from cv_engine.application.commands import (
    ApproveDocumentCommand,
    BuildFromAnalysisCommand,
    CheckDocumentCommand,
    ClaimAddition,
    IngestedApplication,
    RenderCommand,
    SubmissionCommand,
    UpdateDocumentCommand,
)
from cv_engine.application.errors import (
    DOCUMENT_CHANGED,
    StateConflict,
)
from cv_engine.domain.document import ContentCheck, PreparationState
from cv_engine.runtime.composition import Services
from cv_engine.util import sha256_file, utc_now


def _detail(services: Services, application_id: str):
    return services.queries.application_detail(application_id)


def _draft(services: Services, application_id: str) -> str:
    return seed_draft(services, application_id).document_hash


def _approve(services: Services, application_id: str, document_hash: str):
    return services.draft_review.approve_document(
        ApproveDocumentCommand(
            application_id=application_id, expected_document_hash=document_hash, client="web"
        )
    )


def _render(services: Services, application_id: str, document_hash: str):
    return services.rendering.render(
        RenderCommand(application_id=application_id, expected_document_hash=document_hash)
    )


def _submit(services: Services, application_id: str, document_hash: str):
    return services.submission.submit_application(
        SubmissionCommand(
            application_id=application_id,
            expected_document_hash=document_hash,
            submitted_at=utc_now(),
            client="web",
        )
    )


def _ready(services: Services, company: str) -> tuple[str, str]:
    ingested, _analysis = seed_document(services, company)
    application_id = ingested.application_id
    document_hash = _draft(services, application_id)
    assert _approve(services, application_id, document_hash).passed
    _render(services, application_id, document_hash)
    return application_id, document_hash


def test_document_journey_from_analysis_to_submission(
    services: Services, deterministic_renderer, database_engine
) -> None:
    """§5.1 and §14: analysis creates the document; each step moves exactly one stamp.

    The first analysis creates the document pinned to it with no content. Draft, check, approve and render then reach Ready;
    re-approving a current approval changes nothing; submitting copies what was sent
    with a checksum per file, transitions to `applied` once, and leaves the document
    exactly as it was.
    """
    ingested, analysis = seed_document(services, "Journey Co")
    application_id = ingested.application_id
    assert analysis.created_document and analysis.document_id is not None

    document = stored_document(services, application_id)
    assert document.analysis_id == analysis.analysis_id
    assert document.content is None
    detail = _detail(services, application_id)
    assert detail.preparation_state is PreparationState.READY_TO_DRAFT
    assert detail.recommended_action == "create_draft"
    assert "create_draft" in detail.available_actions

    document_hash = _draft(services, application_id)
    detail = _detail(services, application_id)
    assert detail.document_hash == document_hash
    assert detail.preparation_state is PreparationState.DRAFT_IN_PROGRESS
    assert detail.content_check is ContentCheck.NONE
    assert detail.recommended_action == "check"

    # The preview needs no approval and writes nothing anywhere.
    before = persisted_counts(database_engine)
    preview = services.rendering.preview_document(application_id)
    assert preview.document_hash == document_hash and preview.html
    assert services.rendering.preview_document_pdf(application_id).pdf.startswith(b"%PDF")
    assert persisted_counts(database_engine) == before

    checked = services.draft_review.check_document(
        CheckDocumentCommand(application_id=application_id, expected_document_hash=document_hash)
    )
    assert checked.passed and checked.content_check is ContentCheck.PASSED
    assert checked.document_hash == document_hash
    assert _detail(services, application_id).recommended_action == "approve"

    approved = _approve(services, application_id, document_hash)
    assert approved.passed and approved.preparation_state is PreparationState.APPROVED
    assert approved.approved_at is not None
    before = persisted_counts(database_engine)
    again = _approve(services, application_id, document_hash)
    assert again.approved_at == approved.approved_at
    assert persisted_counts(database_engine) == before
    detail = _detail(services, application_id)
    assert detail.preparation_state is PreparationState.APPROVED
    assert detail.recommended_action == "render"

    rendered = _render(services, application_id, document_hash)
    assert rendered.validation.passed and rendered.document_hash == document_hash
    document = stored_document(services, application_id)
    assert document.pdf_path is not None and document.html_path is not None
    pdf = services.paths.root / document.pdf_path
    assert pdf.is_file() and (services.paths.root / document.html_path).is_file()
    detail = _detail(services, application_id)
    assert detail.preparation_state is PreparationState.READY
    assert detail.recommended_action == "submit"
    assert "download_pdf" in detail.available_actions
    delivery = services.rendering.export_recruiter_pdf(application_id)
    assert delivery.document_hash == document_hash and delivery.size == pdf.stat().st_size

    first = _submit(services, application_id, document_hash)
    assert first.current_status == "applied" and first.event_id is not None
    assert first.document_hash == document_hash and first.warnings == []
    second = _submit(services, application_id, document_hash)
    assert second.current_status == "applied" and second.event_id is None

    sent = stored_submissions(services, application_id)
    assert [item.submission_type for item in sent] == ["internal", "internal"]
    for submission in sent:
        assert submission.document_hash == document_hash
        assert submission.content == document.content
        assert submission.job_text_hash == ingested.job_text_hash
        assert submission.pdf_path is not None and submission.pdf_sha256 is not None
        assert submission.html_path is not None and submission.html_sha256 is not None
        assert submission.pdf_sha256 == sha256_file(pdf)
        assert services.payloads.verify_payload(submission.pdf_path, submission.pdf_sha256) == "ok"
        assert (
            services.payloads.verify_payload(submission.html_path, submission.html_sha256) == "ok"
        )
    assert len({submission.pdf_path for submission in sent}) == 2
    assert stored_document(services, application_id) == document
    assert _detail(services, application_id).preparation_state is PreparationState.READY

    reconciled = services.maintenance.reconcile()
    assert reconciled.problems == []
    # Each immutable Submission file; AI calls are counted apart.
    # Mutable document render attempts are not part of this inventory.
    counts = persisted_counts(database_engine)
    submission_files = sum(
        path is not None for item in sent for path in (item.html_path, item.pdf_path)
    )
    assert reconciled.payloads_checked == submission_files
    assert reconciled.ai_calls_checked == counts["ai_calls"]


def test_edits_outdate_stamps_on_read_and_approval_follows_the_current_check(
    services: Services, database_engine
) -> None:
    """§5.3, §5.6 and §7 race rows: an edit changes the basis, so nothing is reopened.

    An unsupported free-text line is saved as pending, returns the approved document
    to draft and outdates its check without any invalidating write, and blocks
    approval through the fresh check approve runs itself. A stale token writes
    nothing. Removing the line lets the document be approved again.
    """
    ingested, _analysis = seed_document(services, "Editor Co")
    application_id = ingested.application_id
    document_hash = _draft(services, application_id)
    assert _approve(services, application_id, document_hash).passed
    content = stored_document(services, application_id).content
    assert content is not None
    section = content.sections[0].name

    edited = services.draft_editing.update_document(
        UpdateDocumentCommand(
            application_id=application_id,
            expected_document_hash=document_hash,
            claim_additions=[ClaimAddition(section=section, text="Invented a claim nobody made.")],
        )
    )
    assert edited.document_hash != document_hash
    assert edited.preparation_state is PreparationState.DRAFT_IN_PROGRESS
    assert edited.content_check is ContentCheck.OUTDATED
    assert len(edited.pending_claim_ids) == 1
    detail = _detail(services, application_id)
    assert detail.preparation_state is PreparationState.DRAFT_IN_PROGRESS
    assert detail.recommended_action == "check"

    before = persisted_counts(database_engine)
    stale = UpdateDocumentCommand(
        application_id=application_id,
        expected_document_hash=document_hash,
        claim_removals=edited.pending_claim_ids,
    )
    with pytest.raises(StateConflict) as conflict:
        services.draft_editing.update_document(stale)
    assert conflict.value.code == DOCUMENT_CHANGED
    current = stored_document(services, application_id)
    assert persisted_counts(database_engine) == before
    assert stored_document(services, application_id) == current

    blocked = _approve(services, application_id, edited.document_hash)
    assert not blocked.passed and blocked.approved_at is None
    assert blocked.preparation_state is PreparationState.DRAFT_IN_PROGRESS
    assert blocked.content_check is ContentCheck.FAILED
    detail = _detail(services, application_id)
    assert "approve" not in detail.available_actions
    assert detail.recommended_action is None

    resolved = services.draft_editing.update_document(
        stale.model_copy(update={"expected_document_hash": edited.document_hash})
    )
    assert resolved.content_check is ContentCheck.OUTDATED
    approved = _approve(services, application_id, resolved.document_hash)
    assert approved.passed and approved.preparation_state is PreparationState.APPROVED


def test_a_fact_edit_by_hand_moves_the_basis_without_a_write(
    services: Services, project_root: Path, database_engine
) -> None:
    """§3 and §6: a dependent fact changed in `base/` outdates every stamp on read.

    Nothing is written to the document; restoring the fact restores the approval,
    because the approval was only ever a stamp compared with a computed basis.
    """
    ingested, _analysis = seed_document(services, "Basis Co")
    application_id = ingested.application_id
    document_hash = _draft(services, application_id)
    assert _approve(services, application_id, document_hash).passed
    document = stored_document(services, application_id)
    assert document.content is not None
    fact_id = next(
        fact_id
        for section in document.content.sections
        for claim in section.claims
        for fact_id in claim.fact_ids
    )
    source = next(
        path
        for path in sorted((project_root / "base").glob("*.json"))
        if any(
            item.get("fact_id") == fact_id
            for item in json.loads(path.read_text(encoding="utf-8")).get("facts", [])
        )
    )
    original = source.read_text(encoding="utf-8")
    data = json.loads(original)
    fact = next(item for item in data["facts"] if item["fact_id"] == fact_id)
    fact["meaning"] = f"{fact['meaning']} (edited by hand)"
    before = persisted_counts(database_engine)

    source.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    detail = _detail(services, application_id)
    assert detail.preparation_state is PreparationState.DRAFT_IN_PROGRESS
    assert detail.content_check is ContentCheck.OUTDATED
    assert detail.document_hash == document_hash

    source.write_text(original, encoding="utf-8")
    assert _detail(services, application_id).preparation_state is PreparationState.APPROVED
    assert persisted_counts(database_engine) == before
    assert stored_document(services, application_id) == document


def test_a_deleted_fact_before_drafting_blocks_nothing(
    services: Services, project_root: Path
) -> None:
    """§3 and §7: a document without content depends on no fact.

    Deleting a fact its Profile offers raises no review reason before drafting; the
    next draft simply cannot choose it.
    """
    ingested, analysis = seed_document(services, "Deleted Early Co")
    application_id = ingested.application_id
    document = stored_document(services, application_id)
    assert document.content is None
    profile = services.knowledge.load().profiles.get(analysis.analysis.profile)
    pool = {fact_id for spec in profile.sections for fact_id in spec.fact_ids}
    source, data, fact = next(
        (path, data, item)
        for path in sorted((project_root / "base").glob("*.json"))
        for data in [json.loads(path.read_text(encoding="utf-8"))]
        for item in data.get("facts", [])
        if item.get("fact_id") in pool and item.get("resume_style") == "bullet"
    )
    fact["status"] = "deleted"
    source.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    detail = _detail(services, application_id)
    assert detail.review_reasons == []
    assert "create_draft" in detail.available_actions
    assert not {"edit", "regenerate_section", "regenerate_claim"} & set(detail.available_actions)


def test_a_newer_analysis_warns_until_build_from_analysis_repins(
    services: Services, deterministic_renderer
) -> None:
    """§5.5: a later analysis never touches the document; only the explicit re-pin does.

    The Ready document stays Ready and submittable with `DOCUMENT_ON_OLDER_ANALYSIS`.
    `build_from_analysis` then replaces the analysis, drops the content
    and every stamp, and deletes the old rendered files, while the Submission keeps
    its own copies.
    """
    application_id, document_hash = _ready(services, "Newer Co")
    ready = stored_document(services, application_id)
    job_text_hash = services.analysis.document_source(application_id).job_text_hash
    newer = seed_existing_analysis(
        services,
        IngestedApplication(application_id=application_id, job_text_hash=job_text_hash),
    )
    assert not newer.created_document and newer.document_id == ready.id

    assert stored_document(services, application_id) == ready
    detail = _detail(services, application_id)
    assert detail.preparation_state is PreparationState.READY
    assert detail.latest_analysis_id == newer.analysis_id
    assert detail.document_analysis_id == ready.analysis_id
    assert "DOCUMENT_ON_OLDER_ANALYSIS" in {warning.code for warning in detail.warnings}
    assert "build_from_analysis" in detail.available_actions

    submitted = _submit(services, application_id, document_hash)
    assert submitted.warnings == ["DOCUMENT_ON_OLDER_ANALYSIS"]

    rebuilt = services.draft_editing.build_from_analysis(
        BuildFromAnalysisCommand(
            application_id=application_id,
            analysis_id=newer.analysis_id,
            expected_document_hash=document_hash,
        )
    )
    assert rebuilt.preparation_state is PreparationState.READY_TO_DRAFT
    document = stored_document(services, application_id)
    assert document.analysis_id == newer.analysis_id and document.content is None
    assert (
        document.checked_basis,
        document.approved_basis,
        document.rendered_basis,
        document.html_path,
        document.pdf_path,
        document.last_render_error,
    ) == (None,) * 6
    assert ready.pdf_path is not None and ready.html_path is not None
    assert not (services.paths.root / ready.pdf_path).exists()
    assert not (services.paths.root / ready.html_path).exists()
    detail = _detail(services, application_id)
    assert detail.preparation_state is PreparationState.READY_TO_DRAFT
    assert "DOCUMENT_ON_OLDER_ANALYSIS" not in {warning.code for warning in detail.warnings}

    (sent,) = stored_submissions(services, application_id)
    assert sent.content == ready.content
    assert sent.pdf_path is not None and sent.pdf_sha256 is not None
    assert services.payloads.verify_payload(sent.pdf_path, sent.pdf_sha256) == "ok"


def test_profile_changes_warn_and_policy_changes_do_not(approved_application, project_root):
    """§3/§8: a Profile change is a warning; the basis is document plus facts.

    Emphasis policy is guidance the writer received, so a change to it warns about
    nothing.
    """
    from cv_engine.application.services.documents import current_basis

    setup = approved_application("Build Warnings")
    services, app_id = setup
    document = stored_document(services, app_id)
    before = current_basis(document, services.knowledge.load())
    profile = project_root / "profiles/sales/account-manager.yaml"
    payload = json.loads(profile.read_text())
    payload["version"] = "wave2-profile-change"
    profile.write_text(json.dumps(payload))
    knowledge = services.knowledge.load()
    assert current_basis(document, knowledge) == before
    detail = services.queries.application_detail(app_id)
    assert "PROFILE_CHANGED" in {w.code for w in detail.warnings}
    assert detail.preparation_state is PreparationState.APPROVED
    assert stored_document(services, app_id) == document
    policy = project_root / "config/emphasis.json"
    payload = json.loads(policy.read_text())
    payload["policy_version"] = "wave2-policy-change"
    policy.write_text(json.dumps(payload))
    assert current_basis(document, services.knowledge.load()) == before
    detail = services.queries.application_detail(app_id)
    codes = {w.code for w in detail.warnings}
    assert "PROFILE_CHANGED" in codes and "POLICY_CHANGED" not in codes
    assert detail.preparation_state is PreparationState.APPROVED
    assert stored_document(services, app_id) == document


def test_an_emphasis_decision_creates_an_analysis_and_keeps_manual_wording(
    drafted_application,
):
    """§13: Emphasis is classification, so the document and its wording stay as they are."""
    from helpers import edit_document_claim

    from cv_engine.application.commands import ApplyAnalysisDecisionsCommand

    setup = drafted_application("Decisions Preserve Wording")
    services, app_id = setup
    document = stored_document(services, app_id)
    assert document.content is not None
    claim = document.content.sections[0].claims[0]
    edited = edit_document_claim(
        services, app_id, claim.claim_id, list(claim.fact_ids), text="Unsupported wording"
    )
    before = stored_document(services, app_id)
    analysis = services.analysis.document_source(app_id).analysis
    profile = services.knowledge.load().profiles.get(analysis.profile)
    other = next(emphasis for emphasis in profile.allowed_emphases if emphasis != analysis.emphasis)

    result = services.analysis.apply_analysis_decisions(
        ApplyAnalysisDecisionsCommand(
            application_id=app_id,
            job_analysis_id=document.analysis_id,
            expected_analysis_id=document.analysis_id,
            expected_document_hash=edited.document_hash,
            emphasis_override=other.value,
        )
    )

    assert result.analysis.emphasis is other
    assert stored_document(services, app_id) == before
    detail = services.queries.application_detail(app_id)
    assert "DOCUMENT_ON_OLDER_ANALYSIS" in {w.code for w in detail.warnings}
