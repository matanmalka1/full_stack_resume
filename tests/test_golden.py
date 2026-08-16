from __future__ import annotations

import json
from pathlib import Path

import pytest

from cv_engine.drafts import serialize_markdown
from cv_engine.rendering import normalized_role_filename, render_html


GOLDEN_DIR = Path(__file__).parent / "golden"


@pytest.mark.parametrize("fixture", sorted(GOLDEN_DIR.glob("*.json")), ids=lambda path: path.stem)
def test_golden_track_profile_language_and_fact_safe_draft(v1_repo: Path, fixture: Path, draft_factory) -> None:
    case = json.loads(fixture.read_text(encoding="utf-8"))
    overrides = case.get("overrides", {})
    facts, profile, analysis, draft, _markdown = draft_factory(
        case["job"],
        track_override=overrides.get("track"),
        profile_override=overrides.get("profile"),
        emphasis_override=overrides.get("emphasis"),
        application_id="00000000-0000-0000-0000-000000000001",
        job_snapshot_id="00000000-0000-0000-0000-000000000002",
    )
    assert analysis.track.value == case["track"]
    assert analysis.profile.value == case["profile"]
    assert analysis.emphasis.value == case["emphasis"]
    assert analysis.language == case["language"]
    markdown = serialize_markdown(draft)
    assert "30% YoY" not in markdown
    assert "3-4 Sales representatives" not in markdown
    assert all(facts.get(fact_id).status.value == "canonical" for fact_id in draft.selected_fact_ids)
    if case["language"] == "he":
        assert "תקציר מקצועי" in markdown
        assert "עברית: שפת אם" in markdown
    if case["track"] == "tech-sales":
        assert "Full-Stack Developer | PH.Digital" in markdown
        assert "direct SaaS Sales" not in markdown


@pytest.mark.parametrize("fixture", sorted(GOLDEN_DIR.glob("*.json")), ids=lambda path: f"{path.stem}-render")
def test_golden_profiles_render_to_ready_pdf(v1_repo: Path, tmp_path: Path, fixture: Path, draft_factory, render_validator) -> None:
    case = json.loads(fixture.read_text(encoding="utf-8"))
    overrides = case.get("overrides", {})
    facts, profile, analysis, draft, _markdown = draft_factory(
        case["job"],
        track_override=overrides.get("track"),
        profile_override=overrides.get("profile"),
        emphasis_override=overrides.get("emphasis"),
        application_id=f"golden-{fixture.stem}",
        job_snapshot_id="golden-snapshot",
    )
    target = tmp_path / fixture.stem
    target.mkdir()
    html = render_html(draft, v1_repo, target / "resume.html")
    pdf = target / normalized_role_filename(profile.normalized_role)
    screenshot = target / "visual.png"
    geometry, report = render_validator(draft, profile, html, pdf, screenshot)
    assert report.passed, report.model_dump()
    assert report.evidence["page_count"] in {1, 2}
