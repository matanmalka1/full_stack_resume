from __future__ import annotations

from pathlib import Path

from cv_engine.drafts import (
    register_composite_claim,
    register_linked_claim,
    serialize_markdown,
    write_working_draft,
)
from cv_engine.util import sha256_text
from cv_engine.validation import validate_draft
from helpers import claim_by_id, exact_fact_claim


def test_generated_draft_has_exact_canonical_claim_links(draft_factory) -> None:
    facts, profile, analysis, draft, markdown = draft_factory("Account Manager retention portfolio customer relationships", write=True)
    report = validate_draft(draft, markdown, facts, profile, analysis)
    assert report.passed, report.model_dump()
    assert report.evidence["claim_count"] > 10


def test_manual_unlinked_change_blocks_approval(draft_factory) -> None:
    facts, profile, analysis, draft, markdown = draft_factory("Python backend developer API React", write=True)
    markdown.write_text(markdown.read_text(encoding="utf-8").replace("Python/FastAPI", "Python/FastAPI and Kubernetes", 1), encoding="utf-8")
    report = validate_draft(draft, markdown, facts, profile, analysis)
    assert not report.passed
    assert any(issue.code == "draft-manifest-mismatch" for issue in report.issues)


def test_stale_sales_claim_is_blocked(draft_factory) -> None:
    facts, profile, analysis, draft, markdown = draft_factory("Sales Manager team leader coaching forecast", write=True)
    text = markdown.read_text(encoding="utf-8") + "\n- Grew revenue 30% YoY.\n"
    markdown.write_text(text, encoding="utf-8")
    report = validate_draft(draft, markdown, facts, profile, analysis)
    assert not report.passed
    assert any(issue.code == "stale-annual-growth" for issue in report.issues)


def test_extractive_derived_wording_remains_supported(v1_repo: Path, draft_factory) -> None:
    facts, profile, analysis, draft, _markdown = draft_factory(
        "Account Manager retention portfolio customer relationships",
        write=True,
    )
    claim = exact_fact_claim(draft, ["sales.metric.performance"])
    updated = register_linked_claim(
        draft,
        claim.claim_id,
        facts.rendering("sales.metric.performance", "en").rstrip("."),
        claim.fact_ids,
        facts,
    )
    markdown, _manifest = write_working_draft(v1_repo, updated)

    report = validate_draft(updated, markdown, facts, profile, analysis)

    assert report.passed, report.model_dump()
    edited = claim_by_id(updated, claim.claim_id)
    assert edited.claim_type == "derived"
    assert edited.derivation_id == "extractive-clauses"


def test_negative_saas_boundary_cannot_be_inverted_into_derived_claim(v1_repo: Path, draft_factory) -> None:
    facts, profile, _analysis, draft, _markdown = draft_factory(
        "Tech Sales SaaS consultative software solutions",
        write=True,
    )
    claim = next(claim for section in draft.sections for claim in section.claims if claim.style == "bullet")
    updated = register_linked_claim(
        draft,
        claim.claim_id,
        "Delivered 30% improvement in direct SaaS Sales.",
        ["sales.metric.performance", "sales.tech_sales.boundary"],
        facts,
    )
    edited = claim_by_id(updated, claim.claim_id)
    assert edited.claim_type == "pending"
    markdown, _manifest = write_working_draft(v1_repo, updated)
    report = validate_draft(updated, markdown, facts, profile, _analysis)
    assert not report.passed
    assert any(issue.code == "pending-claim" for issue in report.issues)


def test_forged_derived_claim_manifest_blocks_approval(v1_repo: Path, draft_factory) -> None:
    facts, profile, analysis, draft, _markdown = draft_factory(
        "Account Manager retention portfolio customer relationships",
        write=True,
    )
    claim = next(claim for section in draft.sections for claim in section.claims if claim.style == "bullet")
    forged = claim.model_copy(update={
        "text": "Closed 999 billion dollars of direct SaaS sales.",
        "claim_type": "derived",
        "fact_ids": ["sales.metric.performance"],
        "text_hash": sha256_text("Closed 999 billion dollars of direct SaaS sales."),
        "derivation_id": "extractive-clauses",
        "derivation_version": "1.0.0",
    })
    for section in draft.sections:
        for index, item in enumerate(section.claims):
            if item.claim_id == claim.claim_id:
                section.claims[index] = forged
    draft.content_hash = sha256_text(serialize_markdown(draft))
    markdown, _manifest = write_working_draft(v1_repo, draft)

    report = validate_draft(draft, markdown, facts, profile, analysis)

    assert not report.passed
    assert any(issue.code == "unsupported-derived-claim" for issue in report.issues)


def test_known_composite_template_preserves_canonical_renderings(v1_repo: Path, draft_factory) -> None:
    facts, profile, analysis, draft, _markdown = draft_factory(
        "Account Manager retention portfolio customer relationships",
        write=True,
    )
    claim = exact_fact_claim(draft, ["sales.metric.recurring_customers"])
    claim_id = claim.claim_id
    updated = register_composite_claim(
        draft,
        claim_id,
        ["sales.metric.recurring_customers", "sales.metric.performance"],
        facts,
    )
    markdown, _manifest = write_working_draft(v1_repo, updated)

    report = validate_draft(updated, markdown, facts, profile, analysis)

    assert report.passed, report.model_dump()
    composite = claim_by_id(updated, claim_id)
    assert composite.template_id == "canonical-renderings"
    assert composite.template_version == "1.0.0"


def test_forged_composite_wording_blocks_approval(v1_repo: Path, draft_factory) -> None:
    facts, profile, analysis, draft, _markdown = draft_factory(
        "Account Manager retention portfolio customer relationships",
        write=True,
    )
    claim = exact_fact_claim(draft, ["sales.metric.performance"])
    updated = register_composite_claim(
        draft,
        claim.claim_id,
        ["sales.metric.performance", "sales.metric.portfolio_growth"],
        facts,
    )
    composite = claim_by_id(updated, claim.claim_id)
    composite.text = "Delivered 30% improvement in direct SaaS Sales."
    composite.text_hash = sha256_text(composite.text)
    updated.content_hash = sha256_text(serialize_markdown(updated))
    markdown, _manifest = write_working_draft(v1_repo, updated)

    report = validate_draft(updated, markdown, facts, profile, analysis)

    assert not report.passed
    assert any(issue.code == "composite-wording-mismatch" for issue in report.issues)


def test_composite_rejects_title_and_date_inputs_for_a_bullet(v1_repo: Path, draft_factory) -> None:
    facts, profile, analysis, draft, _markdown = draft_factory(
        "Account Manager retention portfolio customer relationships",
        write=True,
    )
    claim = exact_fact_claim(draft, ["sales.metric.performance"])
    forged = claim.model_copy(update={
        "text": "Team Leader / Sales Supervisor (B2B) August 2020 - January 2025",
        "fact_ids": ["sales.role.leader.title", "sales.role.leader.dates"],
        "claim_type": "composite",
        "template_id": "canonical-renderings",
        "template_version": "1.0.0",
        "text_hash": sha256_text("Team Leader / Sales Supervisor (B2B) August 2020 - January 2025"),
    })
    for section in draft.sections:
        for index, item in enumerate(section.claims):
            if item.claim_id == claim.claim_id:
                section.claims[index] = forged
    draft.selected_fact_ids = sorted({
        fact_id
        for item in [draft.headline, *draft.contacts, *(item for section in draft.sections for item in section.claims)]
        for fact_id in item.fact_ids
    })
    draft.content_hash = sha256_text(serialize_markdown(draft))
    markdown, _manifest = write_working_draft(v1_repo, draft)

    report = validate_draft(draft, markdown, facts, profile, analysis)

    assert not report.passed
    assert any(issue.code == "invalid-composite-claim" for issue in report.issues)
