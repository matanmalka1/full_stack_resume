from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from ..util import sha256_text
from .analysis.approval import ANALYSIS_INCOMPLETE, approval_reason, unresolved_approval_reasons
from .analysis.gaps import unaccepted_hard_gaps
from .contracts.analysis import JobAnalysis
from .contracts.drafts import ClaimLine, DraftDocument
from .contracts.knowledge import Profile
from .contracts.selection import SelectionPlan
from .contracts.validation import ValidationIssue, ValidationReport
from .draft_markdown import serialize_markdown
from .drafts import render_composite_claim, validate_derived_wording
from .facts import FactStore, FactStoreError
from .presentations import PresentationStore
from .selection import STRUCTURAL_STYLES, EmphasisPolicyStore

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


@dataclass
class _ValidationContext:
    draft: DraftDocument
    markdown: str
    facts: FactStore
    profile: Profile
    analysis: JobAnalysis
    #: The plan the draft was built from, so validation can see the decisions
    #: recorded against it. Optional only so a caller with no plan in hand -
    #: none in the product today - degrades to reporting the gap rather than
    #: crashing.
    plan: SelectionPlan | None
    policies: EmphasisPolicyStore | None
    presentations: PresentationStore | None
    issues: list[ValidationIssue] = field(default_factory=list)
    groups: dict[str, bool] = field(
        default_factory=lambda: {
            "content": True,
            "profile": True,
            "structure": True,
            "headline_safety": True,
        }
    )

    @property
    def claims(self) -> list[ClaimLine]:
        claims = [self.draft.headline, *self.draft.contacts]
        claims.extend(claim for section in self.draft.sections for claim in section.claims)
        return claims

    def add_issue(
        self,
        group: str,
        code: str,
        message: str,
        *,
        hard: bool = True,
    ) -> None:
        if hard:
            self.groups[group] = False
        self.issues.append(ValidationIssue(group=group, code=code, message=message, hard=hard))


@dataclass
class _ClaimContext:
    validation: _ValidationContext
    claim: ClaimLine
    index: int
    seen_ids: set[str]

    @property
    def is_headline(self) -> bool:
        return self.index == 0


DraftRule = Callable[[_ValidationContext], None]
ClaimRule = Callable[[_ClaimContext], None]


def _manifest_matches(context: _ValidationContext) -> None:
    expected = serialize_markdown(context.draft)
    if context.markdown != expected or sha256_text(context.markdown) != context.draft.content_hash:
        context.add_issue(
            "content",
            "draft-manifest-mismatch",
            "Markdown differs from its exact claim manifest; run claim linkage before approval.",
        )


def _headline_claim_is_placed(context: _ClaimContext) -> None:
    claim = context.claim
    if not context.is_headline and (claim.claim_type == "headline" or claim.style == "headline"):
        context.validation.add_issue(
            "structure",
            "misplaced-headline-claim",
            f"claim {claim.claim_id} uses the headline claim type or style outside the document headline",
        )


def _claim_id_is_unique(context: _ClaimContext) -> None:
    claim_id = context.claim.claim_id
    if claim_id in context.seen_ids:
        context.validation.add_issue("content", "duplicate-claim-id", claim_id)
    context.seen_ids.add(claim_id)


def _claim_hash_matches(context: _ClaimContext) -> None:
    claim = context.claim
    if sha256_text(claim.text) != claim.text_hash:
        context.validation.add_issue("content", "claim-hash-mismatch", claim.claim_id)


def _claim_is_linked(context: _ClaimContext) -> None:
    claim = context.claim
    if not claim.fact_ids and not (context.is_headline and claim.claim_type == "headline"):
        context.validation.add_issue("content", "unlinked-claim", claim.text)


def _derived_claim_is_supported(context: _ClaimContext) -> None:
    claim = context.claim
    validation = context.validation
    if claim.claim_type != "derived":
        return
    try:
        validate_derived_wording(
            claim.text,
            claim.fact_ids,
            validation.facts,
            validation.draft.language,
            claim.style,
            claim.derivation_id or "",
            claim.derivation_version or "",
            validation.presentations,
        )
    except (FactStoreError, ValueError) as exc:
        validation.add_issue(
            "content",
            "unsupported-derived-claim",
            f"claim {claim.claim_id}: {exc}",
        )


def _claim_is_not_pending(context: _ClaimContext) -> None:
    claim = context.claim
    if claim.claim_type == "pending":
        context.validation.add_issue(
            "content", "pending-claim", f"claim {claim.claim_id}: {claim.pending_reason}"
        )


def _canonical_claim_has_one_fact(context: _ClaimContext) -> None:
    claim = context.claim
    if claim.claim_type == "canonical" and len(claim.fact_ids) != 1:
        context.validation.add_issue(
            "content",
            "canonical-claim-cardinality",
            f"claim {claim.claim_id} must link exactly one canonical fact",
        )


def _composite_claim_matches_template(context: _ClaimContext) -> None:
    claim = context.claim
    validation = context.validation
    if claim.claim_type != "composite":
        return
    try:
        expected = render_composite_claim(
            claim.fact_ids,
            validation.facts,
            validation.draft.language,
            claim.style,
            claim.template_id or "",
            claim.template_version or "",
            validation.presentations,
        )
    except (FactStoreError, ValueError) as exc:
        validation.add_issue("content", "invalid-composite-claim", f"claim {claim.claim_id}: {exc}")
    else:
        if claim.text != expected:
            validation.add_issue(
                "content",
                "composite-wording-mismatch",
                f"claim {claim.claim_id} does not match its deterministic template",
            )


def _fact_links_are_canonical(context: _ClaimContext) -> None:
    claim = context.claim
    validation = context.validation
    for fact_id in claim.fact_ids:
        try:
            fact = validation.facts.get(fact_id, canonical_only=True)
        except FactStoreError as exc:
            validation.add_issue("content", "invalid-fact-link", str(exc))
            continue
        if claim.claim_type != "canonical":
            continue
        expected = validation.facts.rendering(fact_id, validation.draft.language)
        if claim.text != expected:
            validation.add_issue(
                "content",
                "canonical-wording-mismatch",
                (
                    f"claim {claim.claim_id} does not equal the {validation.draft.language} "
                    f"canonical rendering of {fact_id}"
                ),
            )
        if claim.style != fact.resume_style:
            validation.add_issue(
                "content",
                "canonical-style-mismatch",
                f"claim {claim.claim_id} changes the canonical style of {fact_id}",
            )


CLAIM_RULES: tuple[ClaimRule, ...] = (
    _headline_claim_is_placed,
    _claim_id_is_unique,
    _claim_hash_matches,
    _claim_is_linked,
    _derived_claim_is_supported,
    _claim_is_not_pending,
    _canonical_claim_has_one_fact,
    _composite_claim_matches_template,
    _fact_links_are_canonical,
)


def _claims_are_valid(context: _ValidationContext) -> None:
    seen_ids: set[str] = set()
    for index, claim in enumerate(context.claims):
        claim_context = _ClaimContext(context, claim, index, seen_ids)
        for rule in CLAIM_RULES:
            rule(claim_context)


def _fact_store_version_matches(context: _ValidationContext) -> None:
    if context.draft.fact_store_version != context.facts.version:
        context.add_issue(
            "content",
            "fact-store-version-mismatch",
            "Draft was built from a different fact-store version.",
        )


def _claims_avoid_prohibited_wording(context: _ValidationContext) -> None:
    for pattern, code in STALE_OR_UNSUPPORTED.items():
        if re.search(pattern, context.markdown, re.IGNORECASE):
            context.add_issue("content", code, f"Prohibited claim matches {pattern}")


def _profile_matches(context: _ValidationContext) -> None:
    draft = context.draft
    profile = context.profile
    if draft.profile is not profile.profile or draft.track is not profile.track:
        context.add_issue("profile", "profile-mismatch", "Draft and selected Profile disagree.")
    if draft.emphasis not in profile.allowed_emphases:
        context.add_issue("profile", "emphasis-not-allowed", draft.emphasis.value)
    if (
        context.analysis.fit.value == "low"
        and context.analysis.user_override.get("fit") != "accepted-low-fit"
    ):
        context.add_issue("profile", "low-fit", "Low fit requires an explicit recorded override.")
    # The draft names the analysis it was built from, so that is what the plan
    # has to match. Passing the plan's own id compared it with itself and proved
    # nothing.
    blocking = unaccepted_hard_gaps(
        context.analysis,
        context.plan,
        job_analysis_id=context.draft.job_analysis_id,
    )
    if blocking:
        context.add_issue(
            "profile",
            "hard-gap-not-accepted",
            f"Each hard requirement gap requires an explicit acceptance: "
            f"{[gap.requirement for gap in blocking]}",
        )
    # Two different findings, because two different decisions answer them. A
    # posting the engine could not read was reported as a classification
    # ambiguity, which named a decision that cannot resolve it - and the wrong
    # name was written into an immutable validation report.
    unresolved = unresolved_approval_reasons(context.analysis)
    incomplete = [
        reason
        for reason in unresolved
        if approval_reason(reason).review_code == ANALYSIS_INCOMPLETE
    ]
    ambiguous = [reason for reason in unresolved if reason not in incomplete]
    if incomplete:
        context.add_issue(
            "profile",
            "incomplete-analysis-not-accepted",
            "The analysis did not read this posting's requirements "
            f"({', '.join(incomplete)}); proceeding requires accepting an incomplete "
            "analysis.",
        )
    if ambiguous:
        context.add_issue(
            "profile",
            "classification-approval-required",
            f"Material classification ambiguity is unresolved: {', '.join(ambiguous)}",
        )


def _sections_match_profile(context: _ValidationContext) -> None:
    draft = context.draft
    profile = context.profile
    expected_sections = [
        spec.name_he if draft.language == "he" else spec.name_en
        for spec in profile.sections
        if not spec.optional
    ]
    actual_sections = [section.name for section in draft.sections]
    if actual_sections != expected_sections:
        context.add_issue(
            "structure", "section-order", f"expected {expected_sections}, got {actual_sections}"
        )
    for section, spec in zip(draft.sections, profile.sections, strict=False):
        allowed_fact_ids = set(spec.fact_ids)
        for claim in section.claims:
            disallowed = sorted(set(claim.fact_ids) - allowed_fact_ids)
            if disallowed:
                context.add_issue(
                    "profile",
                    "fact-outside-profile-section",
                    f"claim {claim.claim_id} links facts outside {section.name}: {disallowed}",
                )
        if spec.max_claims is not None and len(section.claims) > spec.max_claims:
            context.add_issue(
                "structure",
                "section-budget-exceeded",
                f"{section.name}: {len(section.claims)} claims over a budget of {spec.max_claims}",
            )
        missing_pins = sorted(
            set(spec.pinned_fact_ids)
            - {fact_id for claim in section.claims for fact_id in claim.fact_ids}
        )
        if missing_pins:
            context.add_issue(
                "structure",
                "pinned-fact-dropped",
                f"{section.name} lost pinned facts: {missing_pins}",
            )
        trailing_structural = _dangling_heading(section.claims)
        if trailing_structural:
            context.add_issue(
                "structure",
                "role-block-empty",
                f"{section.name}: heading {trailing_structural} has no claims under it",
            )


def _required_tags_are_covered(context: _ValidationContext) -> None:
    uncovered = _uncovered_tags(
        context.profile.required_tags, context.draft.selected_fact_ids, context.facts
    )
    if uncovered:
        context.add_issue(
            "profile",
            "required-tag-uncovered",
            f"no selected fact evidences required tags: {uncovered}",
        )


def _emphasis_tags_are_covered(context: _ValidationContext) -> None:
    if context.policies is None:
        return
    policy = context.policies.get(context.draft.emphasis)
    covered = [
        tag
        for tag in policy.preferred_tags
        if tag not in _uncovered_tags([tag], context.draft.selected_fact_ids, context.facts)
    ]
    if len(covered) < policy.minimum_coverage:
        context.add_issue(
            "profile",
            "emphasis-coverage-low",
            (
                f"{context.draft.emphasis.value} covers {len(covered)} of its preferred tags; "
                f"policy expects {policy.minimum_coverage}"
            ),
            hard=False,
        )


def _selected_fact_set_matches(context: _ValidationContext) -> None:
    linked_fact_ids = sorted({fact_id for claim in context.claims for fact_id in claim.fact_ids})
    if context.draft.selected_fact_ids != linked_fact_ids:
        context.add_issue(
            "content",
            "selected-fact-set-mismatch",
            "selected_fact_ids does not exactly match the claims in the untrusted manifest",
        )


def _historical_titles_are_headings(context: _ValidationContext) -> None:
    draft = context.draft
    historical_title_ids = {
        fact_id
        for fact_id in draft.selected_fact_ids
        if fact_id in context.facts.facts and "historical-title" in context.facts.get(fact_id).tags
    }
    heading_ids = {
        fact_id
        for section in draft.sections
        for claim in section.claims
        if claim.style == "heading"
        for fact_id in claim.fact_ids
    }
    # Containment, not equality. The rule exists so a historical job title can
    # never be demoted out of a heading, where it would lose the prominence a
    # recruiter reads it by. It was written as equality because at the time the
    # only headings in any track were job titles. A Projects section broke that
    # assumption: a project title is a heading and is deliberately not tagged
    # `historical-title`, because it is not a role the candidate held. Equality
    # would force the choice between mislabelling a project as employment and
    # dropping it from the document - so it checks the direction that protects
    # the fact, and stays silent on headings that were never job titles.
    demoted = historical_title_ids - heading_ids
    if demoted:
        context.add_issue(
            "structure",
            "historical-title-placement",
            "Historical titles must remain exact headings: " + ", ".join(sorted(demoted)),
        )


def _headline_is_safe(context: _ValidationContext) -> None:
    if context.draft.headline.text not in context.profile.safe_headlines:
        context.add_issue("headline_safety", "unsafe-headline", context.draft.headline.text)


VALIDATION_RULES: tuple[DraftRule, ...] = (
    _manifest_matches,
    _claims_are_valid,
    _fact_store_version_matches,
    _claims_avoid_prohibited_wording,
    _profile_matches,
    _sections_match_profile,
    _required_tags_are_covered,
    _emphasis_tags_are_covered,
    _selected_fact_set_matches,
    _historical_titles_are_headings,
    _headline_is_safe,
)


def validate_draft(
    draft: DraftDocument,
    markdown: str,
    facts: FactStore,
    profile: Profile,
    analysis: JobAnalysis,
    *,
    plan: SelectionPlan | None = None,
    policies: EmphasisPolicyStore | None = None,
    presentations: PresentationStore | None = None,
) -> ValidationReport:
    """Check a draft against the Profile, the facts, and the classification.

    `markdown` is the stored document's exact text, read by the caller, so this
    stays a decision about content rather than about files. A document that does
    not exist is an empty string, which fails the manifest check as it should.

    `policies` enables the Emphasis coverage warning, which needs the authoritative
    tag policy rather than the draft's own selection manifest — the manifest travels
    in an editable working file and is not trusted here. Omitting it drops that
    warning only; every hard gate, the Profile's `required_tags` among them, is
    derived from arguments that are always present.
    """
    context = _ValidationContext(
        draft=draft,
        markdown=markdown,
        facts=facts,
        profile=profile,
        analysis=analysis,
        plan=plan,
        policies=policies,
        presentations=presentations,
    )
    for rule in VALIDATION_RULES:
        rule(context)
    return ValidationReport.from_findings(
        groups=context.groups,
        issues=context.issues,
        evidence={
            "claim_count": len(context.claims),
            "selected_fact_count": len(draft.selected_fact_ids),
        },
    )
