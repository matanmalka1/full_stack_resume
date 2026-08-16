from __future__ import annotations

from pathlib import Path

import pytest

from cv_engine.analysis import classify_job
from cv_engine.drafts import build_draft, register_linked_claim, serialize_markdown, write_working_draft
from cv_engine.facts import FactStore
from cv_engine.profiles import ProfileStore
from cv_engine.util import sha256_text
from cv_engine.validation import validate_draft


def _draft(v1_repo: Path, job: str, **overrides):
    facts = FactStore.load(v1_repo / "base")
    profiles = ProfileStore.load(v1_repo, facts)
    analysis = classify_job(job, **overrides)
    profile = profiles.get(analysis.profile)
    draft = build_draft(
        application_id="app-golden",
        job_snapshot_id="snapshot-golden",
        analysis=analysis,
        profile=profile,
        facts=facts,
    )
    markdown, _ = write_working_draft(v1_repo, draft)
    return facts, profile, analysis, draft, markdown


def test_generated_draft_has_exact_canonical_claim_links(v1_repo: Path) -> None:
    facts, profile, analysis, draft, markdown = _draft(v1_repo, "Account Manager retention portfolio customer relationships")
    report = validate_draft(draft, markdown, facts, profile, analysis)
    assert report.passed, report.model_dump()
    assert report.evidence["claim_count"] > 10


def test_manual_unlinked_change_blocks_approval(v1_repo: Path) -> None:
    facts, profile, analysis, draft, markdown = _draft(v1_repo, "Python backend developer API React")
    markdown.write_text(markdown.read_text(encoding="utf-8").replace("Python/FastAPI", "Python/FastAPI and Kubernetes", 1), encoding="utf-8")
    report = validate_draft(draft, markdown, facts, profile, analysis)
    assert not report.passed
    assert any(issue.code == "draft-manifest-mismatch" for issue in report.issues)


def test_stale_sales_claim_is_blocked(v1_repo: Path) -> None:
    facts, profile, analysis, draft, markdown = _draft(v1_repo, "Sales Manager team leader coaching forecast")
    text = markdown.read_text(encoding="utf-8") + "\n- Grew revenue 30% YoY.\n"
    markdown.write_text(text, encoding="utf-8")
    report = validate_draft(draft, markdown, facts, profile, analysis)
    assert not report.passed
    assert any(issue.code == "stale-annual-growth" for issue in report.issues)


def test_free_form_claim_linkage_is_disabled(v1_repo: Path) -> None:
    facts, _profile, _analysis, draft, _markdown = _draft(v1_repo, "Python backend developer API React")
    claim = next(claim for section in draft.sections for claim in section.claims if claim.style == "bullet")
    with pytest.raises(ValueError, match="free-form derived statements are disabled"):
        register_linked_claim(
            draft,
            claim.claim_id,
            "Built Kubernetes production clusters",
            claim.fact_ids,
            facts,
        )


def test_negative_saas_boundary_cannot_be_inverted_into_derived_claim(v1_repo: Path) -> None:
    facts, _profile, _analysis, draft, _markdown = _draft(
        v1_repo,
        "Tech Sales SaaS consultative software solutions",
    )
    claim = next(claim for section in draft.sections for claim in section.claims if claim.style == "bullet")
    with pytest.raises(ValueError, match="free-form derived statements are disabled"):
        register_linked_claim(
            draft,
            claim.claim_id,
            "Delivered 30% improvement in direct SaaS Sales.",
            ["sales.metric.performance", "sales.tech_sales.boundary"],
            facts,
        )


def test_forged_derived_claim_manifest_blocks_approval(v1_repo: Path) -> None:
    facts, profile, analysis, draft, _markdown = _draft(
        v1_repo,
        "Account Manager retention portfolio customer relationships",
    )
    claim = next(claim for section in draft.sections for claim in section.claims if claim.style == "bullet")
    claim.text = "Closed 999 billion dollars of direct SaaS sales."
    claim.claim_type = "derived"
    claim.fact_ids = ["sales.metric.performance", "sales.tech_sales.boundary"]
    claim.text_hash = sha256_text(claim.text)
    draft.content_hash = sha256_text(serialize_markdown(draft))
    markdown, _manifest = write_working_draft(v1_repo, draft)

    report = validate_draft(draft, markdown, facts, profile, analysis)

    assert not report.passed
    assert any(issue.code == "free-form-derived-claim" for issue in report.issues)
