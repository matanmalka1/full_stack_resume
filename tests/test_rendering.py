from __future__ import annotations

from pathlib import Path

from cv_engine.drafts import serialize_markdown
from cv_engine.rendering import (
    _claim_html,
    _claim_recoverable,
    _emphasis_config,
    _layout_class,
    _launch_failure_message,
    _material_bottom_whitespace,
    normalized_role_filename,
    render_html,
)
from cv_engine.util import sha256_text


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


def test_filename_normalization_does_not_add_seniority() -> None:
    assert normalized_role_filename("Senior Account Executive") == "Matan Malka - Account Executive - CV.pdf"
    assert normalized_role_filename("Full Stack Developer") == "Matan Malka - Full Stack Developer - CV.pdf"


def test_rtl_ats_comparison_accepts_bidi_token_reordering() -> None:
    source = "שיפור של כ-30% בביצועי הצוות ובהכנסות B2B לאורך התקופה"
    extracted = "בביצועי הצוות ובהכנסות 30% שיפור של כ B2B לאורך התקופה"
    assert _claim_recoverable(source, extracted.casefold(), rtl=True)
    assert not _claim_recoverable(source, "שיפור חלקי בלבד", rtl=True)


def test_material_bottom_whitespace_is_a_one_page_visual_defect() -> None:
    assert _material_bottom_whitespace(1, {"bottomWhitespaceRatio": 0.24}) == 0.24
    assert _material_bottom_whitespace(1, {"bottomWhitespaceRatio": 0.16}) is None
    assert _material_bottom_whitespace(2, {"bottomWhitespaceRatio": 0.40}) is None


class _Claim:
    def __init__(self, text: str, style: str = "bullet") -> None:
        self.text = text
        self.style = style


def _dev_emphasis(v1_repo: Path) -> dict:
    return _emphasis_config(v1_repo, "development")


def test_keyword_emphasis_marks_the_stack_and_keeps_the_original_casing(v1_repo: Path) -> None:
    config = _dev_emphasis(v1_repo)
    claim = _Claim("Rebuilt the typescript, REACT layer on mongodb.")
    rendered = str(_claim_html(claim, False, "Work Experience", config))
    # Terms separated only by punctuation read as one thing, so they merge.
    # Matching is case-insensitive; the page still shows what the fact says.
    assert "<strong>typescript, REACT</strong>" in rendered
    assert "TypeScript" not in rendered
    # A wider gap is a separate group rather than a merge across prose.
    spaced = _Claim("Rebuilt the React and PostgreSQL layers.")
    assert "<strong>React</strong> and <strong>PostgreSQL</strong>" in str(
        _claim_html(spaced, False, "Work Experience", config)
    )


def test_keyword_emphasis_is_capped_per_line(v1_repo: Path) -> None:
    config = _dev_emphasis(v1_repo)
    claim = _Claim("Used React then PostgreSQL then MongoDB then TypeScript separately.")
    rendered = str(_claim_html(claim, False, "Work Experience", config))
    assert rendered.count("<strong>") == config["max_groups"] == 2


def test_keyword_emphasis_skips_summary_and_skills(v1_repo: Path) -> None:
    config = _dev_emphasis(v1_repo)
    paragraph = _Claim("Full-Stack Developer working across React and PostgreSQL.", style="paragraph")
    item = _Claim("Frontend: React, Next.js, TypeScript", style="item")
    assert "<strong>" not in str(_claim_html(paragraph, False, "Professional Summary", config))
    assert "<strong>" not in str(_claim_html(item, False, "Core Skills", config))
    # A bullet outside the configured sections is left alone too.
    bullet = _Claim("Managed a team using React.")
    assert "<strong>" not in str(_claim_html(bullet, False, "Education", config))


def test_keyword_emphasis_escapes_before_it_emphasizes(v1_repo: Path) -> None:
    config = _dev_emphasis(v1_repo)
    claim = _Claim('Shipped <script>alert("x")</script> beside React & PostgreSQL.')
    rendered = str(_claim_html(claim, False, "Work Experience", config))
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered
    assert "&amp;" in rendered
    # The only markup introduced is the emphasis itself, balanced and capped.
    assert rendered.count("<strong>") == rendered.count("</strong>") == 2
    assert rendered.count("<") == rendered.count("<strong>") + rendered.count("</strong>")


def test_keyword_emphasis_leaves_facts_and_content_hash_untouched(
    v1_repo: Path, tmp_path: Path, draft_factory
) -> None:
    facts, _profile, _analysis, draft, _md = draft_factory(
        "Full-Stack Developer TypeScript React Node.js PostgreSQL"
    )
    before = {fact_id: facts.get(fact_id).renderings["en"] for fact_id in draft.selected_fact_ids}
    markdown = serialize_markdown(draft)

    html_path = render_html(draft, v1_repo, tmp_path / "resume.html")
    assert "<strong>" in html_path.read_text(encoding="utf-8")

    after = {fact_id: facts.get(fact_id).renderings["en"] for fact_id in draft.selected_fact_ids}
    assert after == before
    assert "<strong>" not in markdown
    assert serialize_markdown(draft) == markdown
    assert sha256_text(markdown) == draft.content_hash


def test_tech_sales_uses_sales_keyword_emphasis(v1_repo: Path) -> None:
    config = _emphasis_config(v1_repo, "tech-sales")
    claim = _Claim("Led needs discovery, negotiation, and closing.")
    rendered = str(_claim_html(claim, False, "Sales Experience", config))
    assert rendered == (
        "Led <strong>needs discovery, negotiation</strong>, and <strong>closing</strong>."
    )


def test_short_tech_sales_draft_uses_spacious_layout(draft_factory) -> None:
    setup = draft_factory(
        "Technical Sales role for software customers, discovery, closing, and CRM",
        profile_override="tech-sales",
    )
    short = setup.draft.model_copy(deep=True)
    for section in short.sections:
        section.claims = section.claims[:2]
    assert _layout_class(short) == "spacious"

    dense = setup.draft.model_copy(deep=True)
    for section in dense.sections:
        for claim in section.claims:
            claim.text += " Detailed verified context." * 12
    assert _layout_class(dense) == "compact"
