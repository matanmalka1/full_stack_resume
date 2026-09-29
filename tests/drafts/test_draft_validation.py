from __future__ import annotations

from pathlib import Path

import pytest
from helpers import PAYME_TECH_SALES_JOB, claim_by_id, store_draft

from cv_engine.domain.claim_review import REVIEW_POLICY_VERSION
from cv_engine.domain.contracts.drafts import ClaimLine, ClaimReviewAssertion, ClaimReviewEvidence
from cv_engine.domain.drafts import apply_claim_edit, authorize_reviewed_claim, draft_content_hash
from cv_engine.domain.validation import validate_draft
from cv_engine.util import sha256_text


def test_generated_draft_has_exact_canonical_claim_links(draft_factory) -> None:
    facts, profile, analysis, draft, markdown = draft_factory(
        "Account Manager retention portfolio customer relationships\n\n"
        "Requirements:\n"
        "- Experience owning the full sales cycle.\n"
        "- Fluent English.",
        write=True,
    )
    report = validate_draft(draft, markdown.read_text(encoding="utf-8"), facts, profile, analysis)
    assert report.passed, report.model_dump()
    assert report.evidence["claim_count"] > 10
    assert report.report_schema_version == "2.0"
    assert set(report.groups) == {"content", "profile", "structure", "headline_safety"}

    # A section out of place is one finding. Each section is still checked against its own
    # spec, so its facts are not all reported as misplaced against its neighbour's.
    draft.sections[0], draft.sections[1] = draft.sections[1], draft.sections[0]
    moved = validate_draft(draft, markdown.read_text(encoding="utf-8"), facts, profile, analysis)
    codes = {issue.code for issue in moved.issues}
    assert "section-order" in codes
    assert not codes & {
        "fact-outside-profile-section",
        "section-budget-exceeded",
        "pinned-fact-dropped",
    }


def test_an_unsafe_or_misplaced_headline_is_blocked(
    project_root: Path,
    draft_factory,
    presentation_store,
) -> None:
    """Both headline failures, each on its own draft.

    Unsafe headline text fails only the draft-side headline group. A
    headline-typed claim injected outside the headline is blocked by the
    deterministic validator on its own: the list mutation deliberately bypasses
    the model-level guard.
    """
    facts, profile, analysis, draft, _markdown = draft_factory(
        "Python backend developer API React",
        profile_override="development",
        write=True,
    )
    draft.headline.text = "Invented Executive Seniority"
    draft.headline.text_hash = sha256_text(draft.headline.text)
    draft.content_hash = draft_content_hash(draft)
    markdown, _text = store_draft(project_root, draft)

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

    # An edit keeps the headline a headline - the safe-headline list decides it, not a
    # fact derivation - so retyping an allowed wording clears the finding instead of
    # leaving a pending claim nothing can resolve.
    restored = apply_claim_edit(
        draft,
        draft.headline.claim_id,
        list(draft.headline.fact_ids),
        facts,
        text=profile.safe_headlines[0],
    )
    assert restored.headline.claim_type == "headline"
    restored.content_hash = draft_content_hash(restored)
    markdown, _text = store_draft(project_root, restored)
    report = validate_draft(
        restored,
        markdown.read_text(encoding="utf-8"),
        facts,
        profile,
        analysis,
        presentations=presentation_store,
    )
    assert report.passed, report.model_dump()

    facts, profile, analysis, draft, _markdown = draft_factory(
        "Account Manager retention portfolio customer relationships",
        write=True,
    )
    _inject_headline_typed_claim(draft)
    tampered = draft.model_copy(update={"content_hash": draft_content_hash(draft)})
    markdown, _text = store_draft(project_root, tampered)

    report = validate_draft(
        tampered, markdown.read_text(encoding="utf-8"), facts, profile, analysis
    )

    assert not report.passed
    assert any(issue.code == "misplaced-headline-claim" for issue in report.issues)
    assert any(issue.code == "unlinked-claim" for issue in report.issues)


def test_manual_unlinked_change_blocks_approval(draft_factory) -> None:
    facts, profile, analysis, draft, markdown = draft_factory(
        "Python backend developer API React", profile_override="development", write=True
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
    project_root: Path, draft_factory
) -> None:
    facts, profile, _analysis, draft, _markdown = draft_factory(
        "Tech Sales SaaS consultative software solutions",
        write=True,
    )
    claim = next(
        claim for section in draft.sections for claim in section.claims if claim.style == "bullet"
    )
    updated = apply_claim_edit(
        draft,
        claim.claim_id,
        ["sales.metric.performance", "sales.tech_sales.boundary"],
        facts,
        text="Delivered 30% improvement in direct SaaS Sales.",
    )
    edited = claim_by_id(updated, claim.claim_id)
    assert edited.claim_type == "pending"
    markdown, _text = store_draft(project_root, updated)
    report = validate_draft(
        updated, markdown.read_text(encoding="utf-8"), facts, profile, _analysis
    )
    assert not report.passed
    assert any(issue.code == "pending-claim" for issue in report.issues)


def test_forged_derived_claim_manifest_blocks_approval(project_root: Path, draft_factory) -> None:
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
    draft.content_hash = draft_content_hash(draft)
    markdown, _text = store_draft(project_root, draft)

    report = validate_draft(draft, markdown.read_text(encoding="utf-8"), facts, profile, analysis)

    assert not report.passed
    assert any(issue.code == "unsupported-derived-claim" for issue in report.issues)


def _reviewed_draft(draft_factory):
    """A draft whose first bullet is a paraphrase promoted through semantic review."""
    facts, profile, analysis, draft, _markdown = draft_factory(
        "Account Manager retention portfolio customer relationships",
        write=True,
    )
    claim = next(
        claim
        for section in draft.sections
        for claim in section.claims
        if claim.claim_type == "canonical" and claim.style == "bullet"
    )
    wording = f"Proven experience: {claim.text}"
    pending = apply_claim_edit(draft, claim.claim_id, list(claim.fact_ids), facts, text=wording)
    reviewed = authorize_reviewed_claim(
        pending,
        claim.claim_id,
        facts,
        ClaimReviewEvidence(
            policy_version=REVIEW_POLICY_VERSION,
            provider_artifact_version_id="artifact-review",
            input_hash="input-review",
            assertions=[
                ClaimReviewAssertion(
                    claim_quote=wording,
                    fact_ids=list(claim.fact_ids),
                    source_quotes=[claim.text],
                )
            ],
        ),
    )
    return facts, profile, analysis, reviewed, claim.claim_id


def _tampered_evidence(claim: ClaimLine, facts, tamper: str) -> ClaimReviewEvidence:
    evidence = claim.review_evidence
    assert evidence is not None
    assertion = evidence.assertions[0]
    other_fact = next(fact_id for fact_id in facts.facts if fact_id not in claim.fact_ids)
    changed = {
        "policy": {"policy_version": "semantic-claim-support-v0"},
        "partial-coverage": {
            "assertions": [assertion.model_copy(update={"claim_quote": claim.text[:10]})]
        },
        # Same letters, different punctuation: whole-claim coverage holds, but the quote
        # is not wording the claim actually contains.
        "paraphrased-claim-quote": {
            "assertions": [
                assertion.model_copy(
                    update={"claim_quote": assertion.claim_quote.replace(" ", " - ")}
                )
            ]
        },
        "fabricated-source-quote": {
            "assertions": [assertion.model_copy(update={"source_quotes": ["Invented source"]})]
        },
        "unpaired-source-quote": {
            "assertions": [assertion.model_copy(update={"source_quotes": []})]
        },
        "extra-fact": {
            "assertions": [
                assertion.model_copy(
                    update={
                        "fact_ids": [*assertion.fact_ids, other_fact],
                        "source_quotes": [*assertion.source_quotes, "anything"],
                    }
                )
            ]
        },
        "no-assertions": {"assertions": []},
    }[tamper]
    return evidence.model_copy(update=changed)


@pytest.mark.parametrize(
    ("tamper", "code"),
    [
        ("policy", "invalid-review-evidence"),
        ("partial-coverage", "incomplete-review-coverage"),
        ("paraphrased-claim-quote", "invalid-review-claim-quote"),
        ("fabricated-source-quote", "invalid-review-source-quote"),
        ("unpaired-source-quote", "invalid-review-source-quote"),
        ("extra-fact", "review-fact-coverage-mismatch"),
        ("no-assertions", "invalid-review-evidence"),
    ],
)
def test_reviewed_wording_keeps_approval_only_while_its_evidence_attests_it(
    project_root: Path, draft_factory, tamper: str, code: str
) -> None:
    """Validation re-runs the activation check on stored review evidence.

    Evidence is data in an editable document, so the gate that admitted the line
    must hold again at approval: any evidence that no longer attests the exact
    wording against its canonical facts blocks.
    """
    facts, profile, analysis, draft, claim_id = _reviewed_draft(draft_factory)
    markdown, _text = store_draft(project_root, draft)
    report = validate_draft(draft, markdown.read_text(encoding="utf-8"), facts, profile, analysis)
    assert report.passed, report.model_dump()

    claim = claim_by_id(draft, claim_id)
    tampered = claim.model_copy(
        update={"review_evidence": _tampered_evidence(claim, facts, tamper)}
    )
    for section in draft.sections:
        section.claims = [
            tampered if item.claim_id == claim_id else item for item in section.claims
        ]
    draft.content_hash = draft_content_hash(draft)
    markdown, _text = store_draft(project_root, draft)

    report = validate_draft(draft, markdown.read_text(encoding="utf-8"), facts, profile, analysis)

    assert not report.passed
    assert code in {issue.code for issue in report.issues}


def test_reviewed_wording_cannot_carry_a_number_its_facts_lack(
    project_root: Path, draft_factory
) -> None:
    facts, profile, analysis, draft, claim_id = _reviewed_draft(draft_factory)
    claim = claim_by_id(draft, claim_id)
    evidence = claim.review_evidence
    assert evidence is not None
    text = f"{claim.text} across 47 accounts"
    inflated = claim.model_copy(
        update={
            "text": text,
            "text_hash": sha256_text(text),
            "review_evidence": evidence.model_copy(
                update={
                    "assertions": [evidence.assertions[0].model_copy(update={"claim_quote": text})]
                }
            ),
        }
    )
    for section in draft.sections:
        section.claims = [
            inflated if item.claim_id == claim_id else item for item in section.claims
        ]
    draft.content_hash = draft_content_hash(draft)
    markdown, _text = store_draft(project_root, draft)

    report = validate_draft(draft, markdown.read_text(encoding="utf-8"), facts, profile, analysis)

    assert not report.passed
    assert "unsupported-review-number" in {issue.code for issue in report.issues}


def test_profile_presentation_wording_is_recomputed_during_validation(
    project_root: Path,
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
    draft.content_hash = draft_content_hash(draft)
    markdown, _text = store_draft(project_root, draft)

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


def test_historical_title_placement_blocks_a_demoted_title_and_spares_a_project_heading(
    draft_factory,
) -> None:
    """A job title that stops being a heading loses the prominence it is read by.

    This is the direction `historical-title-placement` exists to catch, and it
    had no test: the rule only ever failed incidentally, through a fixture.

    The Projects section renders project names as headings. They carry no
    `historical-title` tag on purpose - a project is not employment - so an
    equality check would have forced them out of the document.
    """
    facts, profile, analysis, draft, markdown = draft_factory(
        "Sales Manager team leader coaching forecast", write=True
    )
    demoted = None
    for section in draft.sections:
        for index, claim in enumerate(section.claims):
            if claim.style == "heading" and any(
                "historical-title" in facts.get(fact_id).tags for fact_id in claim.fact_ids
            ):
                demoted = claim.fact_ids[0]
                section.claims[index] = claim.model_copy(update={"style": "bullet"})
                break
        if demoted:
            break
    assert demoted is not None, "fixture carries no historical title to demote"

    report = validate_draft(draft, markdown.read_text(encoding="utf-8"), facts, profile, analysis)
    assert not report.passed
    issue = next(i for i in report.issues if i.code == "historical-title-placement")
    assert demoted in issue.message

    facts, profile, analysis, draft, markdown = draft_factory(
        "Python backend developer API React", profile_override="development", write=True
    )
    headings = [
        fact_id
        for section in draft.sections
        for claim in section.claims
        if claim.style == "heading"
        for fact_id in claim.fact_ids
    ]
    untagged = [f for f in headings if "historical-title" not in facts.get(f).tags]
    assert untagged, "fixture carries no non-title heading to protect"

    report = validate_draft(draft, markdown.read_text(encoding="utf-8"), facts, profile, analysis)
    assert not any(i.code == "historical-title-placement" for i in report.issues)
