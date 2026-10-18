from __future__ import annotations

from pathlib import Path

import pytest
from helpers import actor_of, edit_document_claim, stored_document
from pydantic import ValidationError
from pypdf import PdfWriter

from cv_engine.application.commands import RenderCommand
from cv_engine.application.errors import DOCUMENT_NOT_APPROVED, PreconditionFailed
from cv_engine.domain.candidate import contact_href
from cv_engine.domain.contracts.knowledge import Profile, filing_role
from cv_engine.domain.date_display import displayed_claim_text
from cv_engine.domain.draft_markdown import serialize_markdown
from cv_engine.domain.render_validation import (
    RenderEvidence,
    RenderGeometry,
    validate_render_evidence,
)
from cv_engine.infrastructure.rendering import (
    _claim_recoverable,
    _launch_failure_message,
    compose_html,
    normalized_role_filename,
    validate_rendered,
)


def test_sandbox_blocked_browser_reports_cause_and_subset_command() -> None:
    message = _launch_failure_message(
        "TargetClosedError: BrowserType.launch\n"
        "bootstrap_check_in org.chromium.Chromium.rohitfork.1 failed: Permission denied (1100)"
    )
    assert "Mach port" in message
    assert "--no-sandbox" in message
    assert 'pytest -m "not browser"' in message


def test_missing_browser_install_is_not_reported_as_a_sandbox_block() -> None:
    message = _launch_failure_message("Executable doesn't exist at /path/headless_shell")
    assert "Mach port" not in message
    assert "playwright install chromium" in message
    assert 'pytest -m "not browser"' in message


def test_filename_normalization_does_not_add_seniority(candidate_context) -> None:
    assert normalized_role_filename("Senior Account Executive", candidate_context) == (
        "Matan Malka - Account Executive - CV.pdf"
    )
    assert normalized_role_filename("Full Stack Developer", candidate_context) == (
        "Matan Malka - Full Stack Developer - CV.pdf"
    )


def test_a_role_that_cleans_to_nothing_has_no_filename(candidate_context) -> None:
    # No fallback role: a Hebrew role is refused here, and by the Profile before it.
    with pytest.raises(ValueError):
        normalized_role_filename("מפתח פולסטאק", candidate_context)
    with pytest.raises(ValueError):
        normalized_role_filename("Senior", candidate_context)


def test_a_profile_refuses_a_role_that_cannot_name_its_pdf(profile_store) -> None:
    profile = next(iter(profile_store.profiles.values()))
    values = profile.model_dump()
    hebrew = "מפתח פולסטאק"
    with pytest.raises(ValidationError, match="plain ASCII role name"):
        Profile.model_validate(
            values
            | {"normalized_role": hebrew, "safe_headlines": [*profile.safe_headlines, hebrew]}
        )
    assert filing_role("Senior Account Executive") == "Account Executive"
    assert filing_role(profile.normalized_role)


def test_rtl_ats_comparison_accepts_bidi_token_reordering() -> None:
    source = "שיפור של כ-30% בביצועי הצוות ובהכנסות B2B לאורך התקופה"
    extracted = "בביצועי הצוות ובהכנסות 30% שיפור של כ B2B לאורך התקופה"
    assert _claim_recoverable(source, extracted.casefold(), rtl=True)
    assert not _claim_recoverable(source, "שיפור חלקי בלבד", rtl=True)


def _evidence(setup, extracted_text: str) -> RenderEvidence:
    """Render evidence that passes every check but the text the PDF yields."""
    links = [
        href
        for claim in setup.draft.contacts
        if (href := contact_href(setup.candidate, claim.fact_ids[0], claim.text)) is not None
    ]
    rtl = setup.draft.language == "he"
    return RenderEvidence(
        html_path="resume.html",
        html_exists=True,
        html_size=1,
        html_text='<bdi dir="ltr">B2B</bdi>' if rtl else "",
        pdf_path="resume.pdf",
        pdf_name=normalized_role_filename(setup.profile.normalized_role, setup.candidate),
        pdf_exists=True,
        pdf_size=1,
        pdf_error=None,
        page_count=1,
        extracted_text=extracted_text,
        pdf_sha256=None,
        geometry=RenderGeometry(
            scroll_width=100,
            client_width=100,
            scroll_height=100,
            client_height=100,
            offenders=[],
            direction="rtl" if rtl else "ltr",
            links=links,
            raw={},
        ),
    )


def _displayed_lines(draft) -> list[str]:
    return [
        draft.headline.text,
        *(claim.text for claim in draft.contacts),
        *(
            displayed_claim_text(claim.style, claim.text, draft.language)
            for section in draft.sections
            for claim in section.claims
        ),
    ]


def test_a_hebrew_date_renders_numerically_as_one_isolated_run(
    project_root: Path, draft_factory
) -> None:
    hebrew = draft_factory("Account Manager retention portfolio", language_override="he")
    dates = [
        claim.text
        for section in hebrew.draft.sections
        for claim in section.claims
        if claim.style == "date"
    ]
    assert "אוגוסט 2020 - ינואר 2025" in dates
    html = compose_html(hebrew.draft, project_root, hebrew.candidate)
    assert '<bdi dir="ltr">08/2020 – 01/2025</bdi>' in html
    assert "אוגוסט 2020" not in html
    # Presentation only: the claim and its Markdown export keep the fact's wording.
    assert "**אוגוסט 2020 - ינואר 2025**" in serialize_markdown(hebrew.draft)

    english = draft_factory("Account Manager retention portfolio")
    assert "August 2020 - January 2025" in compose_html(
        english.draft, project_root, english.candidate
    )


def test_text_coverage_looks_for_a_date_as_it_is_displayed(draft_factory) -> None:
    setup = draft_factory("Account Manager retention portfolio", language_override="he")
    report = validate_render_evidence(
        setup.draft,
        setup.profile,
        _evidence(setup, "\n".join(_displayed_lines(setup.draft))),
        setup.candidate,
    )
    assert report.passed, report.issues
    assert report.evidence["ats_claim_coverage"] == 1


def test_a_date_range_broken_apart_in_the_pdf_fails_the_ats_check(draft_factory) -> None:
    setup = draft_factory("Account Manager retention portfolio", language_override="he")
    lines = _displayed_lines(setup.draft)
    assert "08/2020 – 01/2025" in lines
    # The same tokens, reordered as an extractor scatters bidi runs: coverage alone,
    # which tolerates reordering, would still pass this.
    broken = ["01/2025 – 08/2020" if line == "08/2020 – 01/2025" else line for line in lines]
    report = validate_render_evidence(
        setup.draft, setup.profile, _evidence(setup, "\n".join(broken)), setup.candidate
    )
    assert not report.passed
    assert report.groups["ats"] is False
    assert [issue.code for issue in report.issues] == ["date-range"]
    assert "08/2020 – 01/2025" in report.issues[0].message
    assert "03/2019 – 08/2020" not in report.issues[0].message


def test_a_date_range_may_differ_only_in_whitespace(draft_factory) -> None:
    setup = draft_factory("Account Manager retention portfolio")
    lines = _displayed_lines(setup.draft)
    assert "August 2020 - January 2025" in lines
    spaced = [
        "August\n2020 -January  2025" if line == "August 2020 - January 2025" else line
        for line in lines
    ]
    report = validate_render_evidence(
        setup.draft, setup.profile, _evidence(setup, "\n".join(spaced)), setup.candidate
    )
    assert "date-range" not in {issue.code for issue in report.issues}

    reordered = [
        "2025 January - August 2020" if line == "August 2020 - January 2025" else line
        for line in lines
    ]
    report = validate_render_evidence(
        setup.draft, setup.profile, _evidence(setup, "\n".join(reordered)), setup.candidate
    )
    assert {issue.code for issue in report.issues} == {"date-range"}


def test_render_findings_keep_their_existing_failed_groups(
    tmp_path: Path,
    draft_factory,
) -> None:
    setup = draft_factory("Account Manager retention portfolio customer relationships")
    html = tmp_path / "resume.html"
    pdf = tmp_path / "resume.pdf"
    early = validate_rendered(
        setup.draft,
        setup.profile,
        html,
        pdf,
        {},
        setup.candidate,
    )
    assert {(issue.code, issue.group) for issue in early.issues} == {
        ("html-missing", "render"),
        ("pdf-missing", "pdf"),
    }
    assert not early.passed
    assert early.groups["render"] is False
    assert early.groups["pdf"] is False

    html.write_text('<html lang="en" dir="ltr"></html>', encoding="utf-8")
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    with pdf.open("wb") as handle:
        writer.write(handle)

    final = validate_rendered(
        setup.draft,
        setup.profile,
        html,
        pdf,
        {"dir": "ltr", "links": [], "scrollWidth": 100, "clientWidth": 100},
        setup.candidate,
    )
    assert not final.passed
    assert final.issues
    assert all(final.groups[issue.group] is False for issue in final.issues)


def test_render_refuses_a_document_edited_after_approval_before_browser(
    approved_application,
    monkeypatch,
) -> None:
    setup = approved_application("Edited Before Render")
    services, app_id = setup
    document = stored_document(services, app_id)
    assert document.content is not None
    claim = document.content.sections[0].claims[0]
    edited = edit_document_claim(
        services, app_id, claim.claim_id, list(claim.fact_ids), text="Unsupported claim"
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("an unapproved document reached the browser")

    monkeypatch.setattr("cv_engine.infrastructure.rendering.render_pdf", forbidden)
    with pytest.raises(PreconditionFailed) as refused:
        services.rendering.render(
            actor_of(services),
            RenderCommand(application_id=app_id, expected_document_hash=edited.document_hash),
        )
    assert refused.value.code == DOCUMENT_NOT_APPROVED
