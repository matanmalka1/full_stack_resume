from __future__ import annotations

from pathlib import Path

from helpers import PAYME_TECH_SALES_JOB, claim_by_id, store_draft

from cv_engine.domain.draft_markdown import serialize_markdown
from cv_engine.domain.drafts import register_linked_claim
from cv_engine.domain.models import ClaimLine
from cv_engine.domain.validation import validate_draft
from cv_engine.util import sha256_text


def test_generated_draft_has_exact_canonical_claim_links(draft_factory) -> None:
    facts, profile, analysis, draft, markdown = draft_factory(
        "Account Manager retention portfolio customer relationships", write=True
    )
    report = validate_draft(draft, markdown.read_text(encoding="utf-8"), facts, profile, analysis)
    assert report.passed, report.model_dump()
    assert report.evidence["claim_count"] > 10
    assert report.report_schema_version == "2.0"
    assert set(report.groups) == {"content", "profile", "structure", "headline_safety"}


def test_unsafe_headline_fails_only_the_draft_side_headline_group(
    workspace_root: Path,
    draft_factory,
) -> None:
    facts, profile, analysis, draft, _markdown = draft_factory(
        "Python backend developer API React",
        write=True,
    )
    draft.headline.text = "Invented Executive Seniority"
    draft.headline.text_hash = sha256_text(draft.headline.text)
    draft.content_hash = sha256_text(serialize_markdown(draft))
    markdown, _text = store_draft(workspace_root, draft)

    report = validate_draft(
        draft,
        markdown.read_text(encoding="utf-8"),
        facts,
        profile,
        analysis,
    )

    assert not report.passed
    assert not report.groups["headline_safety"]
    assert "filename" not in report.groups
    issue = next(issue for issue in report.issues if issue.code == "unsafe-headline")
    assert issue.group == "headline_safety"


def test_manual_unlinked_change_blocks_approval(draft_factory) -> None:
    facts, profile, analysis, draft, markdown = draft_factory(
        "Python backend developer API React", write=True
    )
    markdown.write_text(
        markdown.read_text(encoding="utf-8").replace(
            "Python/FastAPI", "Python/FastAPI and Kubernetes", 1
        ),
        encoding="utf-8",
    )
    report = validate_draft(draft, markdown.read_text(encoding="utf-8"), facts, profile, analysis)
    assert not report.passed
    assert any(issue.code == "draft-manifest-mismatch" for issue in report.issues)


def test_stale_sales_claim_is_blocked(draft_factory) -> None:
    facts, profile, analysis, draft, markdown = draft_factory(
        "Sales Manager team leader coaching forecast", write=True
    )
    text = markdown.read_text(encoding="utf-8") + "\n- Grew revenue 30% YoY.\n"
    markdown.write_text(text, encoding="utf-8")
    report = validate_draft(draft, markdown.read_text(encoding="utf-8"), facts, profile, analysis)
    assert not report.passed
    assert any(issue.code == "stale-annual-growth" for issue in report.issues)


def test_negative_saas_boundary_cannot_be_inverted_into_derived_claim(
    workspace_root: Path, draft_factory
) -> None:
    facts, profile, _analysis, draft, _markdown = draft_factory(
        "Tech Sales SaaS consultative software solutions",
        write=True,
    )
    claim = next(
        claim for section in draft.sections for claim in section.claims if claim.style == "bullet"
    )
    updated = register_linked_claim(
        draft,
        claim.claim_id,
        "Delivered 30% improvement in direct SaaS Sales.",
        ["sales.metric.performance", "sales.tech_sales.boundary"],
        facts,
    )
    edited = claim_by_id(updated, claim.claim_id)
    assert edited.claim_type == "pending"
    markdown, _text = store_draft(workspace_root, updated)
    report = validate_draft(
        updated, markdown.read_text(encoding="utf-8"), facts, profile, _analysis
    )
    assert not report.passed
    assert any(issue.code == "pending-claim" for issue in report.issues)


def test_forged_derived_claim_manifest_blocks_approval(workspace_root: Path, draft_factory) -> None:
    facts, profile, analysis, draft, _markdown = draft_factory(
        "Account Manager retention portfolio customer relationships",
        write=True,
    )
    claim = next(
        claim for section in draft.sections for claim in section.claims if claim.style == "bullet"
    )
    forged = claim.model_copy(
        update={
            "text": "Closed 999 billion dollars of direct SaaS sales.",
            "claim_type": "derived",
            "fact_ids": ["sales.metric.performance"],
            "text_hash": sha256_text("Closed 999 billion dollars of direct SaaS sales."),
            "derivation_id": "extractive-clauses",
            "derivation_version": "1.0.0",
        }
    )
    for section in draft.sections:
        for index, item in enumerate(section.claims):
            if item.claim_id == claim.claim_id:
                section.claims[index] = forged
    draft.content_hash = sha256_text(serialize_markdown(draft))
    markdown, _text = store_draft(workspace_root, draft)

    report = validate_draft(draft, markdown.read_text(encoding="utf-8"), facts, profile, analysis)

    assert not report.passed
    assert any(issue.code == "unsupported-derived-claim" for issue in report.issues)


def test_profile_presentation_wording_is_recomputed_during_validation(
    workspace_root: Path,
    draft_factory,
    presentation_store,
) -> None:
    facts, profile, analysis, draft, _markdown = draft_factory(
        PAYME_TECH_SALES_JOB,
        track_override="tech-sales",
        profile_override="tech-sales",
        emphasis_override="new-business",
        write=True,
    )
    summary = next(
        claim
        for section in draft.sections
        if section.name == "Professional Summary"
        for claim in section.claims
    )
    summary.text = "Sold SaaS through strategic channel partnerships."
    summary.text_hash = sha256_text(summary.text)
    draft.content_hash = sha256_text(serialize_markdown(draft))
    markdown, _text = store_draft(workspace_root, draft)

    report = validate_draft(
        draft,
        markdown.read_text(encoding="utf-8"),
        facts,
        profile,
        analysis,
        presentations=presentation_store,
    )

    assert not report.passed
    assert any(issue.code == "composite-wording-mismatch" for issue in report.issues)


FABRICATED_HEADLINE_CLAIM = "Closed a NIS 4.2M SaaS enterprise deal."


def _inject_headline_typed_claim(draft, text: str = FABRICATED_HEADLINE_CLAIM) -> ClaimLine:
    """Append an unlinked claim that abuses the headline exemption (bypass repro)."""
    injected = ClaimLine(
        claim_id="injected-fabrication",
        style="bullet",
        text=text,
        fact_ids=[],
        claim_type="headline",
        text_hash=sha256_text(text),
    )
    draft.sections[-1].claims.append(injected)
    return injected


def test_headline_claim_type_outside_the_headline_is_blocked(workspace_root: Path, draft_factory) -> None:
    facts, profile, analysis, draft, _markdown = draft_factory(
        "Account Manager retention portfolio customer relationships",
        write=True,
    )
    # list mutation deliberately bypasses the model-level guard, so this asserts the
    # deterministic validator blocks the injection on its own.
    _inject_headline_typed_claim(draft)
    tampered = draft.model_copy(update={"content_hash": sha256_text(serialize_markdown(draft))})
    markdown, _text = store_draft(workspace_root, tampered)

    report = validate_draft(
        tampered, markdown.read_text(encoding="utf-8"), facts, profile, analysis
    )

    assert not report.passed
    assert any(issue.code == "misplaced-headline-claim" for issue in report.issues)
    assert any(issue.code == "unlinked-claim" for issue in report.issues)
