from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..models import JobAnalysis, JobClassificationProposal, OverrideKey
from .gaps import derive_fit, merge_fit, merge_gaps

if TYPE_CHECKING:
    from ..profiles import ProfileStore


CONFIDENCE_APPROVAL_THRESHOLD = 0.72

#: The override that records "proceed although the analysis read nothing".
#: Its own key rather than `fit`, because it answers extraction alone. Stage 3
#: removed the one checkbox that dismissed every blocker at once and this must
#: not become the next one.
ACCEPTED_INCOMPLETE_ANALYSIS = "accepted-incomplete-analysis"

CLASSIFICATION_AMBIGUITY = "MATERIAL_CLASSIFICATION_AMBIGUITY"
ANALYSIS_INCOMPLETE = "ANALYSIS_INCOMPLETE"


@dataclass(frozen=True)
class ApprovalReason:
    """What settles one reason an approval was demanded for, and how it reads.

    `overrides` is the set of explicit user overrides that answer this reason;
    empty means no decision answers it. `review_code` is the review reason the
    projection reports it as, so a posting that could not be read is not
    reported as an ambiguous classification.
    """

    overrides: frozenset[str]
    review_code: str


# Every reason the engine can record, and what answers it. A Profile determines
# its own Track, so choosing a Profile settles the pair; choosing only a Track
# leaves the Profile inside it undecided. Each reason is settled only by an
# override that actually answers it - an unrelated override must not open the
# gate.
#
# The table is total on purpose. It used to omit `extraction-failed` to mean
# "nothing resolves this", which made an absent entry ambiguous: a reason added
# later and never registered here would be silently reported as a posting that
# could not be read, rather than as the programming error it is. Now an empty
# `overrides` states that deliberately, and an unregistered reason is caught by
# the guard that derives this table's key set from the code that emits reasons.
APPROVAL_REASONS: dict[str, ApprovalReason] = {
    "ambiguous-signals": ApprovalReason(frozenset({"track", "profile"}), CLASSIFICATION_AMBIGUITY),
    "low-confidence": ApprovalReason(frozenset({"track", "profile"}), CLASSIFICATION_AMBIGUITY),
    "track-disagreement": ApprovalReason(frozenset({"track", "profile"}), CLASSIFICATION_AMBIGUITY),
    "profile-disagreement": ApprovalReason(frozenset({"profile"}), CLASSIFICATION_AMBIGUITY),
    "emphasis-disagreement": ApprovalReason(frozenset({"emphasis"}), CLASSIFICATION_AMBIGUITY),
    "inconsistent-proposal": ApprovalReason(
        frozenset({"track", "profile"}), CLASSIFICATION_AMBIGUITY
    ),
    # Analyses written before reasons were recorded: fail closed on the pair.
    "unspecified-ambiguity": ApprovalReason(
        frozenset({"track", "profile"}), CLASSIFICATION_AMBIGUITY
    ),
    # Naming the Track or Profile does not recover a requirement that was never
    # read, so those do not answer this one. Only the explicit decision to
    # proceed with an incomplete analysis does, and it answers nothing else.
    "extraction-failed": ApprovalReason(frozenset({"analysis"}), ANALYSIS_INCOMPLETE),
}

#: How an unregistered reason is treated: blocking, advertising nothing. It is
#: unreachable while the guard passes, and failing closed is what makes the
#: guard the only thing that has to be right.
UNREGISTERED_REASON = ApprovalReason(frozenset(), ANALYSIS_INCOMPLETE)


def approval_reason(reason: str) -> ApprovalReason:
    return APPROVAL_REASONS.get(reason, UNREGISTERED_REASON)


def resolving_actions(reason: str) -> tuple[str, ...]:
    """Which command can settle this reason.

    Every override in the table is submitted through one command, so this is
    derived from whether anything settles the reason at all rather than kept as
    a second column that could drift out of step with the first.
    """
    return ("apply_analysis_decisions",) if approval_reason(reason).overrides else ()


def unresolved_reasons(reasons: Sequence[str], overrides: Mapping[OverrideKey, str]) -> list[str]:
    return [
        reason for reason in reasons if not (approval_reason(reason).overrides & overrides.keys())
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
    profiles: ProfileStore,
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
    # The deterministic run already decided whether extraction failed; a
    # proposal cannot re-open that, so Fit is re-derived from the merged gaps
    # alone and then folded against what the deterministic run concluded.
    fit = merge_fit(derive_fit(gaps), deterministic.fit)

    rationale = proposal.rationale
    if (track, profile) != (proposal.track, proposal.profile):
        rationale = (
            f"{deterministic.rationale} Proposed {proposal.track.value}/{proposal.profile.value} "
            "was not applied."
        )

    return JobAnalysis(
        track=track,
        requirements=deterministic.requirements,
        extraction_version=deterministic.extraction_version,
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
