from __future__ import annotations

import re
from collections import Counter
from typing import cast

from ..facts import FactStore
from ..models import (
    Emphasis,
    Gap,
    JobAnalysis,
    Language,
    OverrideKey,
    ProfileName,
    Requirement,
    Track,
)
from .approval import CONFIDENCE_APPROVAL_THRESHOLD, unresolved_reasons
from .gaps import derive_fit, derive_gaps, gaps_from_requirements
from .requirements import (
    RequirementConceptStore,
    cover_requirements,
    extract_requirements,
    extraction_confidence,
    extraction_failed,
    normalize_span,
    requirement_id,
)

HEBREW = re.compile(r"[\u0590-\u05ff]")

PROFILE_TERMS: dict[ProfileName, tuple[str, ...]] = {
    ProfileName.DEVELOPMENT: (
        "developer",
        "software",
        "backend",
        "frontend",
        "full stack",
        "python",
        "react",
        "api",
    ),
    ProfileName.FIELD_SALES: ("field sales", "territory", "on-site", "travel", "route sales"),
    ProfileName.ACCOUNT_MANAGER: (
        "account manager",
        "retention",
        "portfolio",
        "renewal",
        "customer relationships",
    ),
    ProfileName.KEY_ACCOUNT_MANAGER: ("key account", "strategic account", "enterprise account"),
    ProfileName.SDR_BDR: ("sdr", "bdr", "sales development", "cold call", "outbound"),
    ProfileName.ACCOUNT_EXECUTIVE: ("account executive", "closing", "quota", "new business"),
    ProfileName.BUSINESS_DEVELOPMENT: ("business development", "market expansion", "new markets"),
    ProfileName.SALES_MANAGEMENT: (
        "sales manager",
        "team leader",
        "sales leadership",
        "coach",
        "forecast",
    ),
    ProfileName.TECH_SALES: ("tech sales", "technical sales", "saas sales", "technology sales"),
    ProfileName.PRE_SALES: (
        "pre-sales",
        "presales",
        "solutions consultant",
        "sales engineer",
        "solution consultant",
    ),
}

SALES_TERMS = (
    "sales",
    "revenue",
    "pipeline",
    "account",
    "prospect",
    "customer",
    "business development",
    "quota",
)
TECH_TERMS = (
    "software",
    "saas",
    "api",
    "cloud",
    "technical",
    "developer",
    "technology",
    "solution",
)

# Job language is normalized to the same tag vocabulary used by canonical facts.
# This keeps matching deterministic while allowing a posting's phrasing (for
# example "follow-up tasks in CRM") to select the corresponding pipeline fact.
SELECTION_CONCEPTS: dict[str, tuple[str, ...]] = {
    "new-business": ("new partner acquisition", "new customer acquisition", "new business"),
    "prospecting": ("outbound", "potential customers", "prospects", "leads"),
    "discovery": ("understanding their needs", "needs discovery", "tailored solutions"),
    "closing": ("closing", "close the deal", "closing the deal"),
    "communication": ("phone", "email", "online communication"),
    "pipeline": ("sales progress", "follow-up tasks", "multiple leads", "crm system"),
    "crm": ("crm",),
    "integrations": ("embed", "integrated", "integration"),
    "technical": ("software provider", "tech-related", "product knowledge", "platform"),
    "onboarding": ("onboarding", "onboard"),
}


def _identified(
    gaps: list[Gap], normalized_hash: str, concepts: RequirementConceptStore
) -> list[Gap]:
    """Give each rule-derived gap the same kind of identity a requirement has.

    A hard gap is cleared by accepting it, and acceptance is keyed on the
    requirement id the gap projects. A rule gap without one is therefore a
    blocker nothing can ever clear - the user is told a decision is required
    and given no way to record it.

    The id is built on the same scheme as a requirement's, from the immutable
    snapshot and the gap's own wording, so it is stable across re-analysis of
    the same posting and distinct between postings.
    """
    return [
        gap.model_copy(
            update={
                "requirement_id": requirement_id(
                    normalized_hash=normalized_hash,
                    extraction_version=concepts.extraction_version,
                    identity_span=normalize_span(gap.requirement),
                    ordinal=ordinal,
                )
            }
        )
        if gap.requirement_id is None
        else gap
        for ordinal, gap in enumerate(gaps)
    ]


def classification_confidence(top: int, second: int) -> float:
    """How clearly the profile vocabulary picked one Profile over the next.

    Separated from extraction confidence so a low stored `confidence` can be
    attributed: a strong score here with a weak one there means the job was
    recognised but its requirements were not read.
    """
    return min(0.98, 0.58 + 0.08 * top + 0.04 * max(0, top - second))


def detect_language(text: str) -> Language:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return "en"
    return (
        "he" if sum(bool(HEBREW.match(char)) for char in letters) / len(letters) >= 0.25 else "en"
    )


def classify_job(
    text: str,
    *,
    facts: FactStore,
    concepts: RequirementConceptStore,
    normalized_hash: str,
    track_override: str | None = None,
    profile_override: str | None = None,
    emphasis_override: str | None = None,
    language_override: str | None = None,
) -> JobAnalysis:
    lowered = text.casefold()
    scores = Counter(
        {
            profile: sum(lowered.count(term) for term in terms)
            for profile, terms in PROFILE_TERMS.items()
        }
    )
    has_sales = sum(term in lowered for term in SALES_TERMS)
    has_tech = sum(term in lowered for term in TECH_TERMS)

    if profile_override:
        profile = ProfileName(profile_override)
    elif max(scores.values(), default=0) == 0:
        profile = ProfileName.DEVELOPMENT if has_tech > has_sales else ProfileName.ACCOUNT_MANAGER
    else:
        profile = scores.most_common(1)[0][0]

    if track_override:
        track = Track(track_override)
        if not profile_override:
            if track is Track.DEVELOPMENT:
                profile = ProfileName.DEVELOPMENT
            elif track is Track.TECH_SALES:
                profile = (
                    ProfileName.PRE_SALES
                    if scores[ProfileName.PRE_SALES] > scores[ProfileName.TECH_SALES]
                    else ProfileName.TECH_SALES
                )
            elif profile in {
                ProfileName.DEVELOPMENT,
                ProfileName.TECH_SALES,
                ProfileName.PRE_SALES,
            }:
                sales_scores = {
                    key: value
                    for key, value in scores.items()
                    if key
                    not in {ProfileName.DEVELOPMENT, ProfileName.TECH_SALES, ProfileName.PRE_SALES}
                }
                profile = (
                    max(sales_scores, key=lambda name: sales_scores[name])
                    if max(sales_scores.values(), default=0)
                    else ProfileName.ACCOUNT_MANAGER
                )
    elif profile in {ProfileName.TECH_SALES, ProfileName.PRE_SALES} or (
        has_sales >= 2 and has_tech >= 2
    ):
        track = Track.TECH_SALES
        if profile not in {ProfileName.TECH_SALES, ProfileName.PRE_SALES}:
            profile = ProfileName.TECH_SALES
    elif profile is ProfileName.DEVELOPMENT:
        track = Track.DEVELOPMENT
    else:
        track = Track.SALES

    ranked = scores.most_common(2)
    top = ranked[0][1] if ranked else 0
    second = ranked[1][1] if len(ranked) > 1 else 0
    ambiguous = top == second and top > 0

    default_emphasis = {
        ProfileName.DEVELOPMENT: Emphasis.DEVELOPMENT_BACKEND
        if "backend" in lowered
        else Emphasis.DEVELOPMENT_BALANCED,
        ProfileName.FIELD_SALES: Emphasis.NEW_BUSINESS,
        ProfileName.ACCOUNT_MANAGER: Emphasis.ACCOUNT_GROWTH,
        ProfileName.KEY_ACCOUNT_MANAGER: Emphasis.ACCOUNT_GROWTH,
        ProfileName.SDR_BDR: Emphasis.NEW_BUSINESS,
        ProfileName.ACCOUNT_EXECUTIVE: Emphasis.NEW_BUSINESS,
        ProfileName.BUSINESS_DEVELOPMENT: Emphasis.NEW_BUSINESS,
        ProfileName.SALES_MANAGEMENT: Emphasis.LEADERSHIP,
        ProfileName.TECH_SALES: Emphasis.TECH_CONSULTATIVE,
        ProfileName.PRE_SALES: Emphasis.TECH_CONSULTATIVE,
    }[profile]
    emphasis = Emphasis(emphasis_override) if emphasis_override else default_emphasis

    # Requirements first, then coverage, then the gaps coverage implies.
    # Knowledge is required, not optional: a caller that could omit it would
    # silently produce an analysis with no requirements and `extraction_version`
    # "0" - indistinguishable from a legacy record, and trusted as one.
    #
    # The legacy rule-derived gaps are unioned rather than replaced, so a rule
    # that fires on wording no concept models yet is not lost.
    extracted = extract_requirements(text, normalized_hash=normalized_hash, concepts=concepts)
    requirements: list[Requirement] = cover_requirements(
        extracted, facts=facts, concepts=concepts
    )
    extraction_version = concepts.extraction_version

    # The rules are the other half of requirement understanding while they
    # still own the concepts they own, so they are computed before extraction
    # is judged. A posting the rules read is not one the engine failed to read.
    rule_gaps = _identified(derive_gaps(lowered, track), normalized_hash, concepts)
    failed_extraction = extraction_failed(
        text, extracted, concepts, understood_elsewhere=bool(rule_gaps)
    )

    # Two independently diagnosable scores, multiplied. A strong keyword
    # classification cannot carry an analysis whose requirements were not
    # understood, and the stored product alone would not say which half was
    # weak - so both remain callable on their own.
    extraction_score = extraction_confidence(
        text, extracted, concepts, understood_elsewhere=bool(rule_gaps)
    )
    classification_score = classification_confidence(top, second)
    confidence = round(extraction_score * classification_score, 4)
    boundary_meanings = {
        fact_id: facts.facts[fact_id].meaning
        for requirement in requirements
        for fact_id in requirement.boundary_fact_ids
        if fact_id in facts.facts
    }
    covered_text = {requirement.text for requirement in requirements}
    gaps = [
        *gaps_from_requirements(requirements, boundary_meanings=boundary_meanings),
        *(gap for gap in rule_gaps if gap.requirement not in covered_text),
    ]
    fit = derive_fit(gaps, extraction_failed=failed_extraction)
    candidate_overrides: dict[OverrideKey, str | None] = {
        "track": track_override,
        "profile": profile_override,
        "emphasis": emphasis_override,
        "language": language_override,
    }
    overrides: dict[OverrideKey, str] = {
        key: value for key, value in candidate_overrides.items() if value
    }
    keywords = {term for terms in PROFILE_TERMS.values() for term in terms if term in lowered}
    keywords.update(
        concept
        for concept, phrases in SELECTION_CONCEPTS.items()
        if any(phrase in lowered for phrase in phrases)
    )
    reasons = [
        *(["extraction-failed"] if failed_extraction else []),
        *(["ambiguous-signals"] if ambiguous else []),
        *(["low-confidence"] if confidence < CONFIDENCE_APPROVAL_THRESHOLD else []),
    ]
    return JobAnalysis(
        track=track,
        requirements=requirements,
        extraction_version=extraction_version,
        profile=profile,
        emphasis=emphasis,
        confidence=confidence,
        rationale=f"Matched {profile.value} signals; sales score {has_sales}, technology score {has_tech}.",
        fit=fit,
        gaps=gaps,
        mandatory_requirements=[gap.requirement for gap in gaps if gap.severity == "hard"],
        preferred_requirements=[gap.requirement for gap in gaps if gap.severity == "warning"],
        keywords=sorted(keywords),
        language=cast(Language, language_override) if language_override else detect_language(text),
        classification_requires_approval=bool(unresolved_reasons(reasons, overrides)),
        approval_reasons=reasons,
        user_override=overrides,
    )
