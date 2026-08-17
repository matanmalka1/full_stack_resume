from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from typing import TYPE_CHECKING

from .models import Emphasis, FitLevel, Gap, JobAnalysis, JobClassificationProposal, ProfileName, Track

if TYPE_CHECKING:
    from .profiles import ProfileStore


HEBREW = re.compile(r"[\u0590-\u05ff]")

CONFIDENCE_APPROVAL_THRESHOLD = 0.72

FIT_SEVERITY = {FitLevel.HIGH: 0, FitLevel.MEDIUM: 1, FitLevel.LOW: 2}

PROFILE_TERMS: dict[ProfileName, tuple[str, ...]] = {
    ProfileName.DEVELOPMENT: ("developer", "software", "backend", "frontend", "full stack", "python", "react", "api"),
    ProfileName.FIELD_SALES: ("field sales", "territory", "on-site", "travel", "route sales"),
    ProfileName.ACCOUNT_MANAGER: ("account manager", "retention", "portfolio", "renewal", "customer relationships"),
    ProfileName.KEY_ACCOUNT_MANAGER: ("key account", "strategic account", "enterprise account"),
    ProfileName.SDR_BDR: ("sdr", "bdr", "sales development", "cold call", "outbound"),
    ProfileName.ACCOUNT_EXECUTIVE: ("account executive", "closing", "quota", "new business"),
    ProfileName.BUSINESS_DEVELOPMENT: ("business development", "market expansion", "new markets"),
    ProfileName.SALES_MANAGEMENT: ("sales manager", "team leader", "sales leadership", "coach", "forecast"),
    ProfileName.TECH_SALES: ("tech sales", "technical sales", "saas sales", "technology sales"),
    ProfileName.PRE_SALES: ("pre-sales", "presales", "solutions consultant", "sales engineer", "solution consultant"),
}

SALES_TERMS = ("sales", "revenue", "pipeline", "account", "prospect", "customer", "business development", "quota")
TECH_TERMS = ("software", "saas", "api", "cloud", "technical", "developer", "technology", "solution")


def detect_language(text: str) -> str:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return "en"
    return "he" if sum(bool(HEBREW.match(char)) for char in letters) / len(letters) >= 0.25 else "en"


def derive_fit(gaps: Sequence[Gap]) -> FitLevel:
    if any(gap.severity == "hard" for gap in gaps):
        return FitLevel.LOW
    return FitLevel.MEDIUM if gaps else FitLevel.HIGH


def merge_gaps(deterministic: Sequence[Gap], proposed: Sequence[Gap]) -> list[Gap]:
    """Union the two gap sets under a monotonic policy.

    Every deterministic gap survives with its own reason and substitute facts. A
    proposal may add a gap or raise an existing one from warning to hard; it can
    never drop a gap, soften its severity, or rewrite its authoritative text.
    """
    merged: dict[str, Gap] = {gap.requirement: gap for gap in deterministic}
    for gap in proposed:
        existing = merged.get(gap.requirement)
        if existing is None:
            merged[gap.requirement] = gap
        elif gap.severity == "hard" and existing.severity == "warning":
            merged[gap.requirement] = Gap(
                requirement=existing.requirement,
                severity="hard",
                reason=existing.reason,
                substitute_fact_ids=existing.substitute_fact_ids,
            )
    return list(merged.values())


def merge_classification(
    deterministic: JobAnalysis,
    proposal: JobClassificationProposal,
    profiles: "ProfileStore",
) -> JobAnalysis:
    """Fold an AI classification proposal into deterministic policy.

    The proposal may move Track/Profile/Emphasis, lower confidence, add gaps and
    keywords, and supply a rationale. It cannot decide approval routing, Fit,
    language, requirements, or which gaps survive, and an explicit user override
    still wins over both classifiers.
    """
    overrides = dict(deterministic.user_override)
    consistent = profiles.get(proposal.profile).track is proposal.track
    pinned = consistent and not ("track" in overrides or "profile" in overrides)
    track = proposal.track if pinned else deterministic.track
    profile = proposal.profile if pinned else deterministic.profile

    allowed = profiles.get(profile).allowed_emphases
    if "emphasis" in overrides:
        emphasis = deterministic.emphasis
    elif proposal.emphasis in allowed:
        emphasis = proposal.emphasis
    elif deterministic.emphasis in allowed:
        emphasis = deterministic.emphasis
    else:
        emphasis = profiles.get(profile).default_emphasis

    # Section 9.4 routes a materially ambiguous classification to the user. Two
    # classifiers that disagree on Track/Profile are exactly that: neither is
    # authoritative, so neither may be applied silently. Emphasis is a refinement
    # inside one Profile and does not currently change selected content, so a
    # disagreement there is not an approval gate. An internally inconsistent
    # proposal is treated as disagreement rather than trusted or raised.
    disagreement = (track, profile) != (deterministic.track, deterministic.profile) or not consistent

    confidence = min(deterministic.confidence, proposal.confidence)
    gaps = merge_gaps(deterministic.gaps, proposal.gaps)
    fit = max(derive_fit(gaps), deterministic.fit, key=lambda level: FIT_SEVERITY[level])

    rationale = proposal.rationale
    if (track, profile) != (proposal.track, proposal.profile):
        rationale = (
            f"{deterministic.rationale} Proposed {proposal.track.value}/{proposal.profile.value} "
            "was not applied."
        )

    return JobAnalysis(
        track=track,
        profile=profile,
        emphasis=emphasis,
        confidence=confidence,
        deterministic_confidence=deterministic.confidence,
        proposal_confidence=proposal.confidence,
        rationale=rationale,
        fit=fit,
        gaps=gaps,
        mandatory_requirements=[gap.requirement for gap in gaps if gap.severity == "hard"],
        preferred_requirements=[gap.requirement for gap in gaps if gap.severity == "warning"],
        keywords=sorted(set(deterministic.keywords) | set(proposal.keywords)),
        language=deterministic.language,
        classification_requires_approval=(
            deterministic.classification_requires_approval
            or disagreement
            or confidence < CONFIDENCE_APPROVAL_THRESHOLD
        ),
        user_override=overrides,
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
    scores = Counter({profile: sum(lowered.count(term) for term in terms) for profile, terms in PROFILE_TERMS.items()})
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
                profile = ProfileName.PRE_SALES if scores[ProfileName.PRE_SALES] > scores[ProfileName.TECH_SALES] else ProfileName.TECH_SALES
            elif profile in {ProfileName.DEVELOPMENT, ProfileName.TECH_SALES, ProfileName.PRE_SALES}:
                sales_scores = {
                    key: value for key, value in scores.items()
                    if key not in {ProfileName.DEVELOPMENT, ProfileName.TECH_SALES, ProfileName.PRE_SALES}
                }
                profile = max(sales_scores, key=sales_scores.get) if max(sales_scores.values(), default=0) else ProfileName.ACCOUNT_MANAGER
    elif profile in {ProfileName.TECH_SALES, ProfileName.PRE_SALES} or (has_sales >= 2 and has_tech >= 2):
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
        ProfileName.DEVELOPMENT: Emphasis.DEVELOPMENT_BACKEND if "backend" in lowered else Emphasis.DEVELOPMENT_BALANCED,
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

    gaps: list[Gap] = []
    if re.search(r"(?:direct|proven|must have|required).{0,40}saas sales", lowered):
        gaps.append(Gap(
            requirement="Direct SaaS Sales",
            severity="hard",
            reason="Device Sales plus separate Development experience does not verify direct SaaS Sales.",
            substitute_fact_ids=["sales.company.activity", "development.phdigital.role"],
        ))
    if "salesforce" in lowered:
        gaps.append(Gap(
            requirement="Salesforce",
            severity="warning",
            reason="Salesforce is not verified; Priority ERP and pipeline experience may be presented instead.",
            substitute_fact_ids=["sales.tool.priority", "sales.leadership.pipeline"],
        ))
    years = [int(value) for value in re.findall(r"(\d+)\s*\+?\s*years?", lowered)]
    if years and max(years) >= 5 and track is Track.DEVELOPMENT:
        gaps.append(Gap(
            requirement=f"{max(years)}+ years of Development experience",
            severity="hard",
            reason="Canonical professional Development history does not meet this threshold.",
        ))

    fit = derive_fit(gaps)
    overrides = {
        key: value for key, value in {
            "track": track_override,
            "profile": profile_override,
            "emphasis": emphasis_override,
            "language": language_override,
        }.items() if value
    }
    keywords = sorted({term for terms in PROFILE_TERMS.values() for term in terms if term in lowered})
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
        keywords=keywords,
        language=language_override or detect_language(text),
        classification_requires_approval=ambiguous or confidence < CONFIDENCE_APPROVAL_THRESHOLD,
        user_override=overrides,
    )
