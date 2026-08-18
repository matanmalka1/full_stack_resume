from __future__ import annotations

import json
from pathlib import Path

from cv_engine.domain.draft_markdown import serialize_markdown
from cv_engine.infrastructure.rendering import normalized_role_filename, render_html
from cv_engine.util import sha256_text


GOLDEN_DIR = Path(__file__).parent / "golden"


def _front_matter_and_body(markdown: str) -> tuple[str, str]:
    """Split the provenance header from the document itself.

    The header carries knowledge versions, which legitimately move whenever a
    fact is added anywhere in the store. Pinning the body separately keeps the
    golden comparison about content: a changed claim, contact, section, or name
    still fails, while a knowledge-version bump is asserted against the live
    store instead of being frozen into a hash nobody can interpret later.
    """
    front, _, body = markdown.partition("\n---\n")
    return front, body


def test_representative_profiles_match_their_golden_ready_outputs(
    v1_repo: Path,
    tmp_path: Path,
    draft_factory,
    render_validator,
) -> None:
    for fixture in sorted(GOLDEN_DIR.glob("*.json")):
        case = json.loads(fixture.read_text(encoding="utf-8"))
        overrides = case.get("overrides", {})
        setup = draft_factory(
            case["job"],
            track_override=overrides.get("track"),
            profile_override=overrides.get("profile"),
            emphasis_override=overrides.get("emphasis"),
            application_id="00000000-0000-0000-0000-000000000001",
            job_snapshot_id="00000000-0000-0000-0000-000000000002",
        )
        facts, profile, analysis, draft = setup.facts, setup.profile, setup.analysis, setup.draft
        candidate = setup.candidate
        assert analysis.track.value == case["track"], fixture.stem
        assert analysis.profile.value == case["profile"], fixture.stem
        assert analysis.emphasis.value == case["emphasis"], fixture.stem
        assert analysis.language == case["language"], fixture.stem
        markdown = serialize_markdown(draft)
        assert "30% YoY" not in markdown, fixture.stem
        assert "3-4 sales representatives" not in markdown.casefold(), fixture.stem
        assert all(
            facts.get(fact_id).status.value == "canonical" for fact_id in draft.selected_fact_ids
        ), fixture.stem
        if case["language"] == "he":
            assert "תקציר מקצועי" in markdown
            assert "עברית: שפת אם" in markdown
        if case["track"] == "tech-sales":
            assert "Full-Stack Developer | PH.Digital" in markdown
            assert "direct SaaS Sales" not in markdown

        target = tmp_path / fixture.stem
        target.mkdir()
        html = render_html(draft, v1_repo, target / "resume.html", candidate)
        html_text = html.read_text(encoding="utf-8")
        front_matter, markdown_body = _front_matter_and_body(markdown)
        assert f'fact_store_version: "{facts.version}"' in front_matter
        assert draft.fact_store_version == facts.version
        snapshot = {
            "markdown_body_sha256": sha256_text(markdown_body),
            "html_sha256": sha256_text(html_text),
            "selected_fact_ids": draft.selected_fact_ids,
            "sections": [section.name for section in draft.sections],
        }
        assert snapshot == case["snapshot"], fixture.stem
        assert "<ul>" not in html_text
        assert html_text.count('class="bullet claim"') == sum(
            claim.style == "bullet" for section in draft.sections for claim in section.claims
        )
        if case["language"] == "he":
            assert '<html lang="he" dir="rtl">' in html_text
            assert '<bdi dir="ltr">B2B</bdi>' in html_text

        pdf = target / normalized_role_filename(profile.normalized_role, candidate)
        screenshot = target / "visual.png"
        _geometry, report = render_validator(draft, profile, html, pdf, screenshot, candidate)
        assert report.passed, f"{fixture.stem}: {report.model_dump()}"
        assert report.evidence["page_count"] in {1, 2}


def test_persisted_plan_reproduces_the_computed_selection(
    v1_repo: Path,
    draft_factory,
    fact_store,
    profile_store,
    policy_store,
    candidate_context,
) -> None:
    """The plan path must render exactly what the computing path rendered.

    Production drafts from a persisted SelectionPlan, while the golden cases above
    build their selection by computing it. Without this, the parity evidence would
    cover a path the product no longer takes: the two could drift — in section
    assignment or claim order — and every golden hash would still match.
    """
    from cv_engine.domain.drafts import build_draft
    from cv_engine.infrastructure.knowledge import load_presentations

    differences: list[str] = []
    for fixture in sorted(GOLDEN_DIR.glob("*.json")):
        case = json.loads(fixture.read_text(encoding="utf-8"))
        overrides = case.get("overrides", {})
        computed = draft_factory(
            case["job"],
            track_override=overrides.get("track"),
            profile_override=overrides.get("profile"),
            emphasis_override=overrides.get("emphasis"),
        )
        rebuilt = build_draft(
            application_id=computed.draft.application_id,
            job_snapshot_id=computed.draft.job_snapshot_id,
            job_analysis_id=computed.draft.job_analysis_id,
            analysis=computed.analysis,
            profile=computed.profile,
            facts=fact_store,
            policies=policy_store,
            candidate=candidate_context,
            presentations=load_presentations(v1_repo, fact_store),
            selection=computed.draft.selection,
        )
        if serialize_markdown(computed.draft) != serialize_markdown(rebuilt):
            differences.append(f"{fixture.name}: Markdown differs")
        if computed.draft.selected_fact_ids != rebuilt.selected_fact_ids:
            differences.append(f"{fixture.name}: selected fact IDs differ")
        for original, replayed in zip(computed.draft.sections, rebuilt.sections):
            if [claim.fact_ids for claim in original.claims] != [
                claim.fact_ids for claim in replayed.claims
            ]:
                differences.append(f"{fixture.name}: {original.name} claim order differs")

    assert not differences, differences
