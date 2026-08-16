from __future__ import annotations

import json
from pathlib import Path

import pytest

from cv_engine.analysis import classify_job
from cv_engine.drafts import build_draft, serialize_markdown
from cv_engine.facts import FactStore
from cv_engine.profiles import ProfileStore


GOLDEN_DIR = Path(__file__).parent / "golden"


@pytest.mark.parametrize("fixture", sorted(GOLDEN_DIR.glob("*.json")), ids=lambda path: path.stem)
def test_golden_track_profile_language_and_fact_safe_draft(v1_repo: Path, fixture: Path) -> None:
    case = json.loads(fixture.read_text(encoding="utf-8"))
    overrides = case.get("overrides", {})
    analysis = classify_job(
        case["job"],
        track_override=overrides.get("track"),
        profile_override=overrides.get("profile"),
        emphasis_override=overrides.get("emphasis"),
    )
    assert analysis.track.value == case["track"]
    assert analysis.profile.value == case["profile"]
    assert analysis.emphasis.value == case["emphasis"]
    assert analysis.language == case["language"]
    facts = FactStore.load(v1_repo / "base")
    profile = ProfileStore.load(v1_repo, facts).get(analysis.profile)
    draft = build_draft(
        application_id="00000000-0000-0000-0000-000000000001",
        job_snapshot_id="00000000-0000-0000-0000-000000000002",
        analysis=analysis,
        profile=profile,
        facts=facts,
    )
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
