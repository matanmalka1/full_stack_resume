from __future__ import annotations

import re
from pathlib import Path

from .analysis import unresolved_approval_reasons
from .drafts import render_composite_claim, serialize_markdown, validate_derived_wording
from .facts import FactStore, FactStoreError
from .models import DraftDocument, JobAnalysis, Profile, ValidationIssue, ValidationReport
from .presentations import PresentationError, PresentationStore
from .selection import STRUCTURAL_STYLES, EmphasisPolicyStore
from .util import sha256_text


STALE_OR_UNSUPPORTED = {
    r"\b3\s*[–-]\s*4\s+sales representatives\b": "stale-team-size",
    r"\b30%\s+(?:YoY|year[- ]over[- ]year)\b": "stale-annual-growth",
    r"\b(?:sold|selling|sales of)\s+(?:SaaS|software|subscriptions)\b": "unsupported-saas-sales",
}


def _dangling_heading(claims: list) -> str | None:
    """The last heading in a section that no evidence follows, if any."""
    heading: str | None = None
    supported = True
    for claim in claims:
        if claim.style == "heading":
            if heading is not None and not supported:
                return heading
            heading, supported = claim.text, False
        elif claim.style not in STRUCTURAL_STYLES:
            supported = True
    return None if supported else heading


def _uncovered_tags(tags: list[str], selected_fact_ids: list[str], facts: FactStore) -> list[str]:
    present = {
        tag
        for fact_id in selected_fact_ids
        if fact_id in facts.facts
        for tag in facts.get(fact_id).tags
    }
    return sorted(set(tags) - present)


def validate_draft(
    draft: DraftDocument,
    markdown_path: Path,
    facts: FactStore,
    profile: Profile,
    analysis: JobAnalysis,
    *,
    policies: EmphasisPolicyStore | None = None,
) -> ValidationReport:
    """Check a draft against the Profile, the facts, and the classification.

    `policies` enables the Emphasis coverage warning, which needs the authoritative
    tag policy rather than the draft's own selection manifest — the manifest travels
    in an editable working file and is not trusted here. Omitting it drops that
    warning only; every hard gate, the Profile's `required_tags` among them, is
    derived from arguments that are always present.
    """
    issues: list[ValidationIssue] = []
    groups = {"content": True, "profile": True, "structure": True, "filename": True}
    try:
        presentations = PresentationStore.for_facts(facts)
    except PresentationError as exc:
        presentations = None
        groups["content"] = False
        issues.append(ValidationIssue(
            group="content",
            code="invalid-presentation-rules",
            message=str(exc),
        ))
    expected = serialize_markdown(draft)
    actual = markdown_path.read_text(encoding="utf-8") if markdown_path.is_file() else ""
    if actual != expected or sha256_text(actual) != draft.content_hash:
        groups["content"] = False
        issues.append(ValidationIssue(
            group="content",
            code="draft-manifest-mismatch",
            message="Markdown differs from its exact claim manifest; run claim linkage before approval.",
        ))

    claims = [draft.headline, *draft.contacts]
    claims.extend(claim for section in draft.sections for claim in section.claims)
    seen_ids: set[str] = set()
    for index, claim in enumerate(claims):
        # Only the document headline itself may carry the headline claim type or style;
        # everywhere else they would be an unaudited exemption from fact linkage.
        is_headline = index == 0
        if not is_headline and (claim.claim_type == "headline" or claim.style == "headline"):
            groups["structure"] = False
            issues.append(ValidationIssue(
                group="structure",
                code="misplaced-headline-claim",
                message=f"claim {claim.claim_id} uses the headline claim type or style outside the document headline",
            ))
        if claim.claim_id in seen_ids:
            groups["content"] = False
            issues.append(ValidationIssue(group="content", code="duplicate-claim-id", message=claim.claim_id))
        seen_ids.add(claim.claim_id)
        if sha256_text(claim.text) != claim.text_hash:
            groups["content"] = False
            issues.append(ValidationIssue(group="content", code="claim-hash-mismatch", message=claim.claim_id))
        if not claim.fact_ids and not (is_headline and claim.claim_type == "headline"):
            groups["content"] = False
            issues.append(ValidationIssue(group="content", code="unlinked-claim", message=claim.text))
        if claim.claim_type == "derived":
            try:
                validate_derived_wording(
                    claim.text,
                    claim.fact_ids,
                    facts,
                    draft.language,
                    claim.style,
                    claim.derivation_id or "",
                    claim.derivation_version or "",
                    presentations,
                )
            except (FactStoreError, ValueError) as exc:
                groups["content"] = False
                issues.append(ValidationIssue(
                    group="content",
                    code="unsupported-derived-claim",
                    message=f"claim {claim.claim_id}: {exc}",
                ))
        if claim.claim_type == "pending":
            groups["content"] = False
            issues.append(ValidationIssue(
                group="content",
                code="pending-claim",
                message=f"claim {claim.claim_id}: {claim.pending_reason}",
            ))
        if claim.claim_type == "canonical" and len(claim.fact_ids) != 1:
            groups["content"] = False
            issues.append(ValidationIssue(
                group="content",
                code="canonical-claim-cardinality",
                message=f"claim {claim.claim_id} must link exactly one canonical fact",
            ))
        if claim.claim_type == "composite":
            try:
                expected_composite = render_composite_claim(
                    claim.fact_ids,
                    facts,
                    draft.language,
                    claim.style,
                    claim.template_id or "",
                    claim.template_version or "",
                    presentations,
                )
            except (FactStoreError, ValueError) as exc:
                groups["content"] = False
                issues.append(ValidationIssue(
                    group="content",
                    code="invalid-composite-claim",
                    message=f"claim {claim.claim_id}: {exc}",
                ))
            else:
                if claim.text != expected_composite:
                    groups["content"] = False
                    issues.append(ValidationIssue(
                        group="content",
                        code="composite-wording-mismatch",
                        message=f"claim {claim.claim_id} does not match its deterministic template",
                    ))
        for fact_id in claim.fact_ids:
            try:
                fact = facts.get(fact_id, canonical_only=True)
            except FactStoreError as exc:
                groups["content"] = False
                issues.append(ValidationIssue(group="content", code="invalid-fact-link", message=str(exc)))
                continue
            if claim.claim_type == "canonical":
                expected_rendering = facts.rendering(fact_id, draft.language)
                if claim.text != expected_rendering:
                    groups["content"] = False
                    issues.append(ValidationIssue(
                        group="content", code="canonical-wording-mismatch",
                        message=(
                            f"claim {claim.claim_id} does not equal the {draft.language} "
                            f"canonical rendering of {fact_id}"
                        ),
                    ))
                if claim.style != fact.resume_style:
                    groups["content"] = False
                    issues.append(ValidationIssue(
                        group="content", code="canonical-style-mismatch",
                        message=f"claim {claim.claim_id} changes the canonical style of {fact_id}",
                    ))

    if draft.fact_store_version != facts.version:
        groups["content"] = False
        issues.append(ValidationIssue(
            group="content", code="fact-store-version-mismatch",
            message="Draft was built from a different fact-store version.",
        ))
    for pattern, code in STALE_OR_UNSUPPORTED.items():
        if re.search(pattern, actual, re.IGNORECASE):
            groups["content"] = False
            issues.append(ValidationIssue(group="content", code=code, message=f"Prohibited claim matches {pattern}"))

    if draft.profile is not profile.profile or draft.track is not profile.track:
        groups["profile"] = False
        issues.append(ValidationIssue(group="profile", code="profile-mismatch", message="Draft and selected Profile disagree."))
    if draft.emphasis not in profile.allowed_emphases:
        groups["profile"] = False
        issues.append(ValidationIssue(group="profile", code="emphasis-not-allowed", message=draft.emphasis.value))
    if analysis.fit.value == "low" and analysis.user_override.get("fit") != "accepted-low-fit":
        groups["profile"] = False
        issues.append(ValidationIssue(group="profile", code="low-fit", message="Low fit requires an explicit recorded override."))
    unresolved = unresolved_approval_reasons(analysis)
    if unresolved:
        groups["profile"] = False
        issues.append(ValidationIssue(
            group="profile", code="classification-approval-required",
            message=f"Material classification ambiguity is unresolved: {', '.join(unresolved)}",
        ))

    expected_sections = [
        spec.name_he if draft.language == "he" else spec.name_en
        for spec in profile.sections if not spec.optional
    ]
    actual_sections = [section.name for section in draft.sections]
    if actual_sections != expected_sections:
        groups["structure"] = False
        issues.append(ValidationIssue(
            group="structure", code="section-order",
            message=f"expected {expected_sections}, got {actual_sections}",
        ))
    for section, spec in zip(draft.sections, profile.sections, strict=False):
        allowed_fact_ids = set(spec.fact_ids)
        for claim in section.claims:
            disallowed = sorted(set(claim.fact_ids) - allowed_fact_ids)
            if disallowed:
                groups["profile"] = False
                issues.append(ValidationIssue(
                    group="profile",
                    code="fact-outside-profile-section",
                    message=f"claim {claim.claim_id} links facts outside {section.name}: {disallowed}",
                ))
        if spec.max_claims is not None and len(section.claims) > spec.max_claims:
            groups["structure"] = False
            issues.append(ValidationIssue(
                group="structure",
                code="section-budget-exceeded",
                message=f"{section.name}: {len(section.claims)} claims over a budget of {spec.max_claims}",
            ))
        missing_pins = sorted(
            set(spec.pinned_fact_ids)
            - {fact_id for claim in section.claims for fact_id in claim.fact_ids}
        )
        if missing_pins:
            groups["structure"] = False
            issues.append(ValidationIssue(
                group="structure",
                code="pinned-fact-dropped",
                message=f"{section.name} lost pinned facts: {missing_pins}",
            ))
        # Selection may drop bullets but must never leave a role heading standing
        # on its own: a title and dates with no evidence under them reads as a
        # gap in the history rather than as a tailored CV.
        trailing_structural = _dangling_heading(section.claims)
        if trailing_structural:
            groups["structure"] = False
            issues.append(ValidationIssue(
                group="structure",
                code="role-block-empty",
                message=f"{section.name}: heading {trailing_structural} has no claims under it",
            ))

    # `Profile.required_tags` is what the Profile must be able to evidence at
    # all; failing it means the document no longer supports the role it claims.
    uncovered = _uncovered_tags(profile.required_tags, draft.selected_fact_ids, facts)
    if uncovered:
        groups["profile"] = False
        issues.append(ValidationIssue(
            group="profile",
            code="required-tag-uncovered",
            message=f"no selected fact evidences required tags: {uncovered}",
        ))

    # Emphasis coverage is a policy expectation, not a structural invariant, so
    # it is reported and does not block on its own.
    if policies is not None:
        policy = policies.get(draft.emphasis)
        covered = [
            tag for tag in policy.preferred_tags
            if tag not in _uncovered_tags([tag], draft.selected_fact_ids, facts)
        ]
        if len(covered) < policy.minimum_coverage:
            issues.append(ValidationIssue(
                group="profile",
                code="emphasis-coverage-low",
                message=(
                    f"{draft.emphasis.value} covers {len(covered)} of its preferred tags; "
                    f"policy expects {policy.minimum_coverage}"
                ),
                hard=False,
            ))
    linked_fact_ids = sorted({fact_id for claim in claims for fact_id in claim.fact_ids})
    if draft.selected_fact_ids != linked_fact_ids:
        groups["content"] = False
        issues.append(ValidationIssue(
            group="content",
            code="selected-fact-set-mismatch",
            message="selected_fact_ids does not exactly match the claims in the untrusted manifest",
        ))
    historical_title_ids = {
        fact_id for fact_id in draft.selected_fact_ids
        if fact_id in facts.facts and "historical-title" in facts.get(fact_id).tags
    }
    heading_ids = {
        fact_id for section in draft.sections for claim in section.claims
        if claim.style == "heading" for fact_id in claim.fact_ids
    }
    if historical_title_ids != heading_ids:
        groups["structure"] = False
        issues.append(ValidationIssue(group="structure", code="historical-title-placement", message="Historical titles must remain exact headings."))
    if draft.headline.text not in profile.safe_headlines:
        groups["filename"] = False
        issues.append(ValidationIssue(group="filename", code="unsafe-headline", message=draft.headline.text))

    return ValidationReport(
        passed=all(groups.values()) and not any(issue.hard for issue in issues),
        groups=groups,
        issues=issues,
        evidence={"claim_count": len(claims), "selected_fact_count": len(draft.selected_fact_ids)},
    )
