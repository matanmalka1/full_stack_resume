from __future__ import annotations

import re
from collections import Counter

from ..models import Emphasis, JobAnalysis, ProfileName, Track
from .approval import CONFIDENCE_APPROVAL_THRESHOLD, unresolved_reasons
from .gaps import derive_fit, derive_gaps

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


def detect_language(text: str) -> str:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return "en"
    return (
        "he" if sum(bool(HEBREW.match(char)) for char in letters) / len(letters) >= 0.25 else "en"
    )


def classify_job(
    text: str,
    *,
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
                    max(sales_scores, key=sales_scores.get)
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
    confidence = min(0.98, 0.58 + 0.08 * top + 0.04 * max(0, top - second))
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

    gaps = derive_gaps(lowered, track)
    fit = derive_fit(gaps)
    overrides = {
        key: value
        for key, value in {
            "track": track_override,
            "profile": profile_override,
            "emphasis": emphasis_override,
            "language": language_override,
        }.items()
        if value
    }
    keywords = {term for terms in PROFILE_TERMS.values() for term in terms if term in lowered}
    keywords.update(
        concept
        for concept, phrases in SELECTION_CONCEPTS.items()
        if any(phrase in lowered for phrase in phrases)
    )
    reasons = [
        *(["ambiguous-signals"] if ambiguous else []),
        *(["low-confidence"] if confidence < CONFIDENCE_APPROVAL_THRESHOLD else []),
    ]
    return JobAnalysis(
        track=track,
        profile=profile,
        emphasis=emphasis,
        confidence=confidence,
        rationale=f"Matched {profile.value} signals; sales score {has_sales}, technology score {has_tech}.",
        fit=fit,
        gaps=gaps,
        mandatory_requirements=[gap.requirement for gap in gaps if gap.severity == "hard"],
        preferred_requirements=[gap.requirement for gap in gaps if gap.severity == "warning"],
        keywords=sorted(keywords),
        language=language_override or detect_language(text),
        classification_requires_approval=bool(unresolved_reasons(reasons, overrides)),
        approval_reasons=reasons,
        user_override=overrides,
    )
