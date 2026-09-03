from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from typing import cast

from ..contracts.analysis import (
    Gap,
    JobAnalysis,
    Language,
    OverrideKey,
    Requirement,
)
from ..contracts.taxonomy import Emphasis, ProfileName, Track
from ..facts import FactStore
from ..profiles import ProfileStore
from .approval import CONFIDENCE_APPROVAL_THRESHOLD, unresolved_reasons
from .gaps import derive_fit, derive_gaps, gaps_from_requirements
from .requirements.concepts import RequirementConceptStore
from .requirements.confidence import extraction_confidence, extraction_failed
from .requirements.coverage import cover_requirements
from .requirements.extraction import extract_requirements, normalize_span, requirement_id

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

    It measures the vocabulary, which since requirement coverage began deciding
    the Profile is no longer always what chose it. It is left measuring the
    vocabulary rather than fed the coverage scores, because this scale was
    tuned for small term counts and a coverage separation saturates it: 12
    against 9 would report near-certainty for a two-fact margin. What a
    coverage-decided classification should report instead is an open question,
    not something to answer by handing the same formula a different unit.
    """
    return min(0.98, 0.58 + 0.08 * top + 0.04 * max(0, top - second))


def detect_language(text: str) -> Language:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return "en"
    return (
        "he" if sum(bool(HEBREW.match(char)) for char in letters) / len(letters) >= 0.25 else "en"
    )


#: What a mandatory requirement is worth against a preferred one when ranking
#: Profiles. A Profile that can evidence what the employer demands outranks one
#: that can evidence what the employer would merely like.
MANDATORY_WEIGHT = 3

#: Declaration order, which is the tie-break the vocabulary has always used.
_DECLARED = {profile: index for index, profile in enumerate(PROFILE_TERMS)}


def allowed_fact_pool(profile) -> set[str]:
    """Every fact this Profile is allowed to say, across all its sections."""
    return {fact_id for section in profile.sections for fact_id in section.fact_ids}


def requirement_profile_scores(
    requirements: list[Requirement], profiles: ProfileStore
) -> Counter[ProfileName]:
    """How much of the evidence this posting calls for each Profile may present.

    Coverage is decided against the whole fact store before any Profile is
    chosen, so this reads an answer that already exists rather than asking each
    Profile to re-decide what the posting requires. That ordering is the whole
    point: scoring a Profile by requirements derived from that Profile's own
    facts would let the choice justify itself.

    Evidence is counted whatever the coverage verdict. A requirement the
    candidate only partly meets is still one the CV has to speak to, and the
    Profile that cannot say anything about it is the weaker fit, not the safer
    one.
    """
    scores: Counter[ProfileName] = Counter()
    for name in ProfileName:
        pool = allowed_fact_pool(profiles.get(name))
        scores[name] = sum(
            (MANDATORY_WEIGHT if requirement.mandatory else 1)
            * len(set(requirement.supporting_fact_ids) & pool)
            for requirement in requirements
        )
    return scores


def classify_job(
    text: str,
    *,
    facts: FactStore,
    profiles: ProfileStore,
    concepts: RequirementConceptStore,
    normalized_hash: str,
    track_override: str | None = None,
    profile_override: str | None = None,
    emphasis_override: str | None = None,
    language_override: str | None = None,
) -> JobAnalysis:
    lowered = text.casefold()

    # Requirements and their coverage are decided first, against the whole fact
    # store, because the Profile decision now reads them. Nothing here depends
    # on Track or Profile: `extract_requirements` sees only the posting and
    # `cover_requirements` only the facts, which is what keeps the ordering
    # honest rather than circular. The rule-derived gaps still come later -
    # those do depend on Track.
    #
    # Knowledge is required, not optional: a caller that could omit it would
    # silently produce an analysis with no requirements and `extraction_version`
    # "0" - indistinguishable from a legacy record, and trusted as one.
    extracted = extract_requirements(text, normalized_hash=normalized_hash, concepts=concepts)
    requirements: list[Requirement] = cover_requirements(extracted, facts=facts, concepts=concepts)
    extraction_version = concepts.extraction_version

    term_scores = Counter(
        {
            profile: sum(lowered.count(term) for term in terms)
            for profile, terms in PROFILE_TERMS.items()
        }
    )
    coverage_scores = requirement_profile_scores(requirements, profiles)
    # What the posting asks for outranks how it is titled. The vocabulary is
    # kept as the tie-breaker rather than dropped: for a posting whose
    # requirements the model cannot read, coverage is zero everywhere and the
    # title terms are the only signal there is - which is exactly the case this
    # ordering leaves untouched.
    ranking = {profile: (coverage_scores[profile], term_scores[profile]) for profile in ProfileName}

    def best(candidates: Iterable[ProfileName]) -> ProfileName | None:
        # Ties fall to declaration order, which is what `Counter.most_common`
        # did when the vocabulary decided alone. Any other tie-break would
        # silently reclassify every posting whose requirements are unread, where
        # the vocabulary is still the only signal and nothing has changed.
        ranked = sorted(
            candidates, key=lambda name: (ranking[name], -_DECLARED[name]), reverse=True
        )
        return next((name for name in ranked if ranking[name] != (0, 0)), None)

    has_sales = sum(term in lowered for term in SALES_TERMS)
    has_tech = sum(term in lowered for term in TECH_TERMS)

    if profile_override:
        profile = ProfileName(profile_override)
    else:
        chosen = best(ProfileName)
        profile = chosen or (
            ProfileName.DEVELOPMENT if has_tech > has_sales else ProfileName.ACCOUNT_MANAGER
        )

    if track_override:
        track = Track(track_override)
        if not profile_override:
            if track is Track.DEVELOPMENT:
                profile = ProfileName.DEVELOPMENT
            elif track is Track.TECH_SALES:
                profile = (
                    ProfileName.PRE_SALES
                    if ranking[ProfileName.PRE_SALES] > ranking[ProfileName.TECH_SALES]
                    else ProfileName.TECH_SALES
                )
            elif profile in {
                ProfileName.DEVELOPMENT,
                ProfileName.TECH_SALES,
                ProfileName.PRE_SALES,
            }:
                profile = (
                    best(
                        name
                        for name in ProfileName
                        if name
                        not in {
                            ProfileName.DEVELOPMENT,
                            ProfileName.TECH_SALES,
                            ProfileName.PRE_SALES,
                        }
                    )
                    or ProfileName.ACCOUNT_MANAGER
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

    # Ambiguity is a tie in the ranking that actually decided, not in the
    # vocabulary alone. With no requirements read the ranking is the vocabulary,
    # so this is the same question it always asked for those postings.
    ordered = sorted(ranking.values(), reverse=True)
    ambiguous = len(ordered) > 1 and ordered[0] == ordered[1] and ordered[0] != (0, 0)
    term_ranked = term_scores.most_common(2)
    top = term_ranked[0][1] if term_ranked else 0
    second = term_ranked[1][1] if len(term_ranked) > 1 else 0

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

    # The legacy rule-derived gaps are unioned rather than replaced, so a rule
    # that fires on wording no concept models yet is not lost.
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
