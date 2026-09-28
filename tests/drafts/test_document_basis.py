"""The CV document's basis and derived states (state-and-use-cases.md §3–§5)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cv_engine.domain.contracts.document import BuiltWith, CVDocument, DocumentSubmission
from cv_engine.domain.contracts.drafts import (
    ClaimLine,
    ClaimStyle,
    ClaimType,
    DraftDocument,
    ResumeSection,
)
from cv_engine.domain.contracts.knowledge import Fact, FactStatus
from cv_engine.domain.contracts.selection import SelectionManifest
from cv_engine.domain.contracts.taxonomy import Emphasis, ProfileName, Track
from cv_engine.domain.contracts.validation import ValidationReport
from cv_engine.domain.document import (
    ContentCheck,
    DocumentState,
    PreparationState,
    basis,
    content_check,
    document_hash,
    document_state,
    preparation_state,
)


def _fact(fact_id: str, text: str = "Built APIs", **changes) -> Fact:
    values = {
        "fact_id": fact_id,
        "meaning": text,
        "renderings": {"en": text},
        "tags": [],
        "status": FactStatus.CANONICAL,
        "provenance": "cv_base.md",
        "resume_style": "bullet",
        "source_file": "base/facts.md",
    }
    return Fact(**(values | changes))


def _selection(*fact_ids: str) -> SelectionManifest:
    return SelectionManifest(
        policy_version="1",
        emphasis=Emphasis.DEVELOPMENT_BALANCED,
        emphasis_policy_version="1",
        selected_fact_ids=list(fact_ids),
    )


def _claim(
    claim_id: str, *fact_ids: str, style: ClaimStyle = "bullet", claim_type: ClaimType = "canonical"
) -> ClaimLine:
    return ClaimLine(
        claim_id=claim_id,
        style=style,
        text=claim_id,
        fact_ids=list(fact_ids),
        claim_type=claim_type,
        text_hash="h",
    )


def _content(*claim_fact_ids: str) -> DraftDocument:
    return DraftDocument(
        application_id="app",
        job_snapshot_id="snapshot",
        job_analysis_id="analysis",
        language="en",
        track=Track.DEVELOPMENT,
        profile=ProfileName.DEVELOPMENT,
        emphasis=Emphasis.DEVELOPMENT_BALANCED,
        name="Candidate",
        headline=_claim("headline", style="headline", claim_type="headline"),
        contacts=[],
        sections=[ResumeSection(name="Experience", claims=[_claim("c1", *claim_fact_ids)])],
        selected_fact_ids=[],
        fact_store_version="v1",
    )


def _document(content: DraftDocument | None = None, **stamps) -> CVDocument:
    selection = _selection("fact.selected")
    return CVDocument(
        id="doc",
        application_id="app",
        analysis_id="analysis",
        selection=selection,
        content=content,
        built_with=BuiltWith(profile_version="p1", selection_policy_version="s1"),
        document_hash=document_hash("analysis", selection, content),
        created_at="2026-09-28T00:00:00+00:00",
        updated_at="2026-09-28T00:00:00+00:00",
        **stamps,
    )


def test_document_hash_covers_analysis_selection_and_content() -> None:
    selection, content = _selection("a"), _content("b")
    reference = document_hash("analysis", selection, content)

    assert document_hash("analysis", _selection("a"), _content("b")) == reference
    assert document_hash("other-analysis", selection, content) != reference
    assert document_hash("analysis", _selection("a", "c"), content) != reference
    assert document_hash("analysis", selection, _content("c")) != reference
    assert document_hash("analysis", selection, None) != reference


def test_basis_moves_with_every_change_to_a_dependent_fact_and_no_other() -> None:
    document = _document(_content("fact.claimed"))
    facts = {
        "fact.selected": _fact("fact.selected"),
        "fact.claimed": _fact("fact.claimed"),
        "fact.unrelated": _fact("fact.unrelated"),
    }
    reference = basis(document, facts)

    unaffected = [
        facts | {"fact.unrelated": _fact("fact.unrelated", "Edited")},
        facts | {"fact.selected": _fact("fact.selected", source_file="base/moved.md")},
    ]
    for changed in unaffected:
        assert basis(document, changed) == reference

    affected = [
        facts | {"fact.selected": _fact("fact.selected", "Edited by hand")},
        facts | {"fact.claimed": _fact("fact.claimed", status=FactStatus.DELETED)},
        facts | {"fact.claimed": _fact("fact.claimed", status=FactStatus.PENDING)},
        {key: value for key, value in facts.items() if key != "fact.claimed"},
    ]
    for changed in affected:
        assert basis(document, changed) != reference


_B = "b" * 64
_OTHER = "0" * 64
_PASSED = ValidationReport(passed=True, groups={"content": True})
_FAILED = ValidationReport(passed=False, groups={"content": False})


@pytest.mark.parametrize(
    ("stamps", "expected"),
    [
        ({}, (DocumentState.DRAFT, PreparationState.DRAFT_IN_PROGRESS, ContentCheck.NONE)),
        (
            {"content_report": _FAILED, "checked_basis": _B, "passed": False},
            (DocumentState.DRAFT, PreparationState.DRAFT_IN_PROGRESS, ContentCheck.FAILED),
        ),
        (
            {"content_report": _PASSED, "checked_basis": _OTHER, "passed": True},
            (DocumentState.DRAFT, PreparationState.DRAFT_IN_PROGRESS, ContentCheck.OUTDATED),
        ),
        (
            {"approved_basis": _OTHER, "approved_at": "t"},
            (DocumentState.DRAFT, PreparationState.DRAFT_IN_PROGRESS, ContentCheck.NONE),
        ),
        (
            {
                "content_report": _PASSED,
                "checked_basis": _B,
                "passed": True,
                "approved_basis": _B,
                "approved_at": "t",
            },
            (DocumentState.APPROVED, PreparationState.APPROVED, ContentCheck.PASSED),
        ),
        (
            {
                "approved_basis": _B,
                "approved_at": "t",
                "rendered_basis": _OTHER,
                "html_path": "h",
                "pdf_path": "p",
            },
            (DocumentState.APPROVED, PreparationState.APPROVED, ContentCheck.NONE),
        ),
        (
            {
                "approved_basis": _B,
                "approved_at": "t",
                "rendered_basis": _B,
                "html_path": "h",
                "pdf_path": "p",
            },
            (DocumentState.READY, PreparationState.READY, ContentCheck.NONE),
        ),
        (
            # A render stamp equal to the basis does not make an outdated approval
            # ready: readiness needs all three stamps equal to the basis.
            {
                "approved_basis": _OTHER,
                "approved_at": "t",
                "rendered_basis": _B,
                "html_path": "h",
                "pdf_path": "p",
            },
            (DocumentState.DRAFT, PreparationState.DRAFT_IN_PROGRESS, ContentCheck.NONE),
        ),
    ],
)
def test_states_are_derived_from_stamps_against_the_current_basis(stamps, expected) -> None:
    document = _document(_content(), **stamps)

    derived = (
        document_state(document, _B),
        preparation_state(document, _B),
        content_check(document, _B),
    )

    assert derived == expected


def test_documents_without_content_or_without_existence_project_their_own_states() -> None:
    assert preparation_state(None, None) is PreparationState.NEEDS_ANALYSIS
    assert document_state(None, None) is DocumentState.NONE
    empty = _document()
    assert preparation_state(empty, _B) is PreparationState.READY_TO_DRAFT
    assert content_check(empty, _B) is ContentCheck.NONE


def test_the_contract_refuses_unpaired_stamps_and_stamps_on_an_empty_document() -> None:
    refused = [
        (_content(), {"checked_basis": _B}),
        (_content(), {"content_report": _PASSED, "checked_basis": _B, "passed": False}),
        (_content(), {"approved_basis": _B}),
        (_content(), {"rendered_basis": _B, "html_path": "h"}),
        (_content(), {"last_render_error": {"detail": "no code"}}),
        (None, {"approved_basis": _B, "approved_at": "t"}),
        (None, {"last_render_error": {"code": "RENDER_FAILED"}}),
    ]
    for content, stamps in refused:
        with pytest.raises(ValidationError):
            _document(content, **stamps)


def test_a_submission_carries_what_was_sent_only_when_internal() -> None:
    sent = {
        "job_snapshot_id": "snapshot",
        "document_hash": _B,
        "content": _content(),
        "html_path": "submissions/1.html",
        "html_sha256": _B,
        "pdf_path": "submissions/1.pdf",
        "pdf_sha256": _B,
    }
    base = {"id": "s", "application_id": "app", "submitted_at": "t"}

    DocumentSubmission.model_validate({"submission_type": "internal", **base, **sent})
    DocumentSubmission.model_validate({"submission_type": "external", **base})
    with pytest.raises(ValidationError, match="records the content"):
        DocumentSubmission.model_validate(
            {"submission_type": "internal", **base, **sent, "pdf_sha256": None}
        )
    with pytest.raises(ValidationError, match="carries no document"):
        DocumentSubmission.model_validate({"submission_type": "external", **base, "html_path": "x"})
