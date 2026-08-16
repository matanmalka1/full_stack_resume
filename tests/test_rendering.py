from __future__ import annotations

from pathlib import Path

from cv_engine.analysis import classify_job
from cv_engine.drafts import build_draft
from cv_engine.facts import FactStore
from cv_engine.profiles import ProfileStore
from cv_engine.rendering import _claim_recoverable, normalized_role_filename, render_html, render_pdf, validate_rendered


def test_filename_normalization_does_not_add_seniority() -> None:
    assert normalized_role_filename("Senior Account Executive") == "Matan Malka - Account Executive - CV.pdf"
    assert normalized_role_filename("Full Stack Developer") == "Matan Malka - Full Stack Developer - CV.pdf"


def test_rtl_ats_comparison_accepts_bidi_token_reordering() -> None:
    source = "שיפור של כ-30% בביצועי הצוות ובהכנסות B2B לאורך התקופה"
    extracted = "בביצועי הצוות ובהכנסות 30% שיפור של כ B2B לאורך התקופה"
    assert _claim_recoverable(source, extracted.casefold(), rtl=True)
    assert not _claim_recoverable(source, "שיפור חלקי בלבד", rtl=True)


def test_rendered_claims_use_flat_bullet_structure(v1_repo: Path, tmp_path: Path) -> None:
    facts = FactStore.load(v1_repo / "base")
    profiles = ProfileStore.load(v1_repo, facts)
    analysis = classify_job("Account Manager retention portfolio customer relationships")
    profile = profiles.get(analysis.profile)
    draft = build_draft(
        application_id="flat-bullets",
        job_snapshot_id="snapshot",
        analysis=analysis,
        profile=profile,
        facts=facts,
    )
    path = render_html(draft, v1_repo, tmp_path / "flat.html")
    rendered = path.read_text(encoding="utf-8")
    assert "<ul>" not in rendered
    assert rendered.count('class="bullet claim"') == sum(
        claim.style == "bullet" for section in draft.sections for claim in section.claims
    )


def test_hebrew_rtl_html_and_pdf_ready_checks(v1_repo: Path, tmp_path: Path) -> None:
    facts = FactStore.load(v1_repo / "base")
    profiles = ProfileStore.load(v1_repo, facts)
    analysis = classify_job(
        "דרוש מנהל תיקי לקוחות B2B לניהול לקוחות, שימור והגדלת פעילות",
        track_override="sales",
        profile_override="account-manager",
        emphasis_override="account-growth",
    )
    profile = profiles.get(analysis.profile)
    draft = build_draft(
        application_id="render-app",
        job_snapshot_id="render-snapshot",
        analysis=analysis,
        profile=profile,
        facts=facts,
    )
    html_path = tmp_path / "resume.html"
    pdf_path = tmp_path / normalized_role_filename(profile.normalized_role)
    screenshot = tmp_path / "visual.png"
    render_html(draft, v1_repo, html_path)
    html = html_path.read_text(encoding="utf-8")
    assert '<html lang="he" dir="rtl">' in html
    assert '<bdi dir="ltr">B2B</bdi>' in html
    geometry = render_pdf(html_path, pdf_path, screenshot)
    report = validate_rendered(draft, profile, html_path, pdf_path, screenshot, geometry)
    assert report.passed, report.model_dump()
    assert report.evidence["page_count"] == 1
