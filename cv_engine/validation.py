from __future__ import annotations

import re
from pathlib import Path

from .drafts import serialize_markdown
from .facts import FactStore, FactStoreError
from .models import DraftDocument, JobAnalysis, Profile, ValidationIssue, ValidationReport
from .util import sha256_text


STALE_OR_UNSUPPORTED = {
    r"\b3\s*[–-]\s*4\s+sales representatives\b": "stale-team-size",
    r"\b30%\s+(?:YoY|year[- ]over[- ]year)\b": "stale-annual-growth",
    r"\b(?:sold|selling|sales of)\s+(?:SaaS|software|subscriptions)\b": "unsupported-saas-sales",
}


def validate_draft(
    draft: DraftDocument,
    markdown_path: Path,
    facts: FactStore,
    profile: Profile,
    analysis: JobAnalysis,
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    groups = {"content": True, "profile": True, "structure": True, "filename": True}
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
    for claim in claims:
        if claim.claim_id in seen_ids:
            groups["content"] = False
            issues.append(ValidationIssue(group="content", code="duplicate-claim-id", message=claim.claim_id))
        seen_ids.add(claim.claim_id)
        if sha256_text(claim.text) != claim.text_hash:
            groups["content"] = False
            issues.append(ValidationIssue(group="content", code="claim-hash-mismatch", message=claim.claim_id))
        if claim.claim_type != "headline" and not claim.fact_ids:
            groups["content"] = False
            issues.append(ValidationIssue(group="content", code="unlinked-claim", message=claim.text))
        for fact_id in claim.fact_ids:
            try:
                fact = facts.get(fact_id, canonical_only=True)
            except FactStoreError as exc:
                groups["content"] = False
                issues.append(ValidationIssue(group="content", code="invalid-fact-link", message=str(exc)))
                continue
            if claim.claim_type == "canonical" and claim.text not in fact.renderings.values():
                groups["content"] = False
                issues.append(ValidationIssue(
                    group="content", code="canonical-wording-mismatch",
                    message=f"claim {claim.claim_id} does not equal an approved rendering of {fact_id}",
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
    classification_overridden = any(
        key in analysis.user_override for key in ("track", "profile", "emphasis")
    )
    if analysis.classification_requires_approval and not classification_overridden:
        groups["profile"] = False
        issues.append(ValidationIssue(group="profile", code="classification-approval-required", message="Material classification ambiguity is unresolved."))

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
    historical_title_ids = {
        fact_id for fact_id in draft.selected_fact_ids
        if "historical-title" in facts.get(fact_id).tags
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
