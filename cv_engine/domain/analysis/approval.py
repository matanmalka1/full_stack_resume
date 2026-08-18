from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from ..models import JobAnalysis, JobClassificationProposal
from .gaps import FIT_SEVERITY, derive_fit, merge_gaps

if TYPE_CHECKING:
    from ..profiles import ProfileStore


CONFIDENCE_APPROVAL_THRESHOLD = 0.72

# Which explicit user overrides settle each reason an approval was demanded for.
# A Profile determines its own Track, so choosing a Profile settles the pair;
# choosing only a Track leaves the Profile inside it undecided. Each reason is
# settled only by an override that actually answers it — an unrelated override
# must not open the gate.
APPROVAL_RESOLVING_OVERRIDES: dict[str, frozenset[str]] = {
    "ambiguous-signals": frozenset({"track", "profile"}),
    "low-confidence": frozenset({"track", "profile"}),
    "track-disagreement": frozenset({"track", "profile"}),
    "profile-disagreement": frozenset({"profile"}),
    "emphasis-disagreement": frozenset({"emphasis"}),
    "inconsistent-proposal": frozenset({"track", "profile"}),
    # Analyses written before reasons were recorded: fail closed on the pair.
    "unspecified-ambiguity": frozenset({"track", "profile"}),
}


def unresolved_reasons(reasons: Sequence[str], overrides: dict[str, str]) -> list[str]:
    return [
        reason for reason in reasons
        if not (APPROVAL_RESOLVING_OVERRIDES.get(reason, frozenset()) & overrides.keys())
    ]


def unresolved_approval_reasons(analysis: JobAnalysis) -> list[str]:
    """Reasons the classification still needs a decision from the user.

    A recorded reason clears only when the user overrode a field that actually
    answers it, so an Emphasis or language override can no longer open a gate
    that a Track/Profile ambiguity closed.
    """
    reasons = analysis.approval_reasons
    if not reasons and analysis.classification_requires_approval:
        reasons = ["unspecified-ambiguity"]
    return unresolved_reasons(reasons, analysis.user_override)


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

    confidence = min(deterministic.confidence, proposal.confidence)

    # Section 9.4 routes a materially ambiguous classification to the user. Two
    # classifiers that disagree are exactly that: neither is authoritative, so
    # neither may be applied silently. Emphasis is included because it now drives
    # fact selection — a different Emphasis produces a different document, which
    # is the definition of materially changing the CV. An internally inconsistent
    # proposal is recorded as its own reason rather than trusted or raised.
    reasons = list(deterministic.approval_reasons)
    if not consistent:
        reasons.append("inconsistent-proposal")
    else:
        if proposal.track is not deterministic.track:
            reasons.append("track-disagreement")
        if proposal.profile is not deterministic.profile:
            reasons.append("profile-disagreement")
    if emphasis is not deterministic.emphasis:
        reasons.append("emphasis-disagreement")
    if confidence < CONFIDENCE_APPROVAL_THRESHOLD:
        reasons.append("low-confidence")
    reasons = list(dict.fromkeys(reasons))
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
        classification_requires_approval=bool(unresolved_reasons(reasons, overrides)),
        approval_reasons=reasons,
        user_override=overrides,
    )
