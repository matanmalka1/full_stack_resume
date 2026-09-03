from __future__ import annotations

import re
from collections.abc import Sequence

from ..models import FitLevel, Gap, Requirement, Track

#: Only the three assessed levels are ordered. UNKNOWN is deliberately absent:
#: it is not a point on the scale, so giving it a number would let it be
#: compared - and a comparison is exactly what must not happen silently.
FIT_SEVERITY = {FitLevel.HIGH: 0, FitLevel.MEDIUM: 1, FitLevel.LOW: 2}

#: Why a requirement is not met, when no boundary fact gives the authoritative
#: account. Deterministic labels rather than generated prose: the reason is
#: displayed, never matched on.
_COVERAGE_REASON = {
    "partial": "Canonical facts cover part of this requirement; the rest is not verified.",
    "unsupported": "Canonical facts do not verify this requirement.",
}


def derive_fit(gaps: Sequence[Gap], *, extraction_failed: bool = False) -> FitLevel:
    """Fit from the gaps, unless the requirements were never readable.

    `extraction_failed` is an explicit signal, never inferred from an empty
    requirement list. An analysis written before the extractor existed also has
    no requirements, and it must keep the Fit it was assessed with rather than
    being reinterpreted as unassessable.

    A hard gap still outranks a failed extraction: evidence of poor Fit is
    knowledge, and losing it to "we could not tell" would be a downgrade.
    """
    if any(gap.severity == "hard" for gap in gaps):
        return FitLevel.LOW
    if extraction_failed:
        return FitLevel.UNKNOWN
    return FitLevel.MEDIUM if gaps else FitLevel.HIGH


def merge_fit(left: FitLevel, right: FitLevel) -> FitLevel:
    """Combine two Fit judgements without ranking UNKNOWN.

    LOW wins over everything, UNKNOWN included: an identified poor Fit is a
    finding, and a failed assessment must not erase it. Against HIGH or MEDIUM,
    UNKNOWN wins instead - a Fit that was never assessed cannot be reported as
    one that was.
    """
    if FitLevel.LOW in (left, right):
        return FitLevel.LOW
    if FitLevel.UNKNOWN in (left, right):
        return FitLevel.UNKNOWN
    return max(left, right, key=lambda level: FIT_SEVERITY[level])


def gaps_from_requirements(
    requirements: Sequence[Requirement], *, boundary_meanings: dict[str, str] | None = None
) -> list[Gap]:
    """Project the unmet requirements as gaps.

    A mandatory requirement produces a hard gap whether its coverage is
    `partial` or `unsupported`. Partial means relevant evidence exists, not
    that the requirement is satisfied, so it still demands an explicit decision
    before drafting.

    `substitute_fact_ids` carries the supporting facts because for a *gap* that
    is what they are - what may be shown in place of the thing that is missing.
    The two fields stay distinct on `Requirement`, where they mean different
    things.
    """
    meanings = boundary_meanings or {}
    gaps: list[Gap] = []
    for requirement in requirements:
        if requirement.coverage == "matched":
            continue
        authoritative = [
            meanings[fact_id] for fact_id in requirement.boundary_fact_ids if fact_id in meanings
        ]
        gaps.append(
            Gap(
                requirement=requirement.text,
                severity="hard" if requirement.mandatory else "warning",
                reason=authoritative[0]
                if authoritative
                else _COVERAGE_REASON[requirement.coverage],
                substitute_fact_ids=list(requirement.supporting_fact_ids),
                requirement_id=requirement.requirement_id,
            )
        )
    return gaps


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
                requirement_id=existing.requirement_id,
            )
    return list(merged.values())


def derive_gaps(lowered: str, track: Track) -> list[Gap]:
    gaps: list[Gap] = []
    hard_saas = bool(re.search(r"(?:direct|proven|must have|required).{0,40}saas sales", lowered))
    if hard_saas:
        gaps.append(
            Gap(
                requirement="Direct SaaS Sales",
                severity="hard",
                reason="Device Sales plus separate Development experience does not verify direct SaaS Sales.",
                substitute_fact_ids=["sales.company.activity", "development.phdigital.role"],
            )
        )
    elif "saas" in lowered:
        gaps.append(
            Gap(
                requirement="Direct SaaS Sales preference",
                severity="warning",
                reason=(
                    "Direct SaaS/software Sales is not verified; B2B Sales and separate "
                    "professional Development experience may be presented without merging them."
                ),
                substitute_fact_ids=[
                    "development.phdigital.role",
                    "development.phdigital.fullstack",
                ],
            )
        )
    if re.search(
        r"(?:using|use|experience|familiarity).{0,50}\bcrm\b|\bcrm\b.{0,30}(?:tool|system)", lowered
    ):
        gaps.append(
            Gap(
                requirement="Sales CRM usage",
                severity="warning",
                reason=(
                    "Use of a named Sales CRM is not verified; canonical pipeline, Priority ERP, "
                    "and CRM-development experience may be shown instead."
                ),
                substitute_fact_ids=[
                    "sales.leadership.pipeline",
                    "sales.tool.priority",
                    "development.phdigital.crm",
                ],
            )
        )
    if re.search(
        r"strategic partnerships?|distribution partners?|strategic b2b channels?", lowered
    ):
        gaps.append(
            Gap(
                requirement="Strategic partnerships / channel Sales experience",
                severity="warning",
                reason=(
                    "Direct strategic-partnership or channel-Sales ownership is not verified; "
                    "new-business prospecting, complex deals, and strategic-customer work may be shown."
                ),
                substitute_fact_ids=[
                    "sales.cycle.prospecting",
                    "sales.achievement.complex_deals",
                    "sales.leadership.strategic_customers",
                ],
            )
        )
    if "salesforce" in lowered:
        gaps.append(
            Gap(
                requirement="Salesforce",
                severity="warning",
                reason="Salesforce is not verified; Priority ERP and pipeline experience may be presented instead.",
                substitute_fact_ids=["sales.tool.priority", "sales.leadership.pipeline"],
            )
        )
    years = [int(value) for value in re.findall(r"(\d+)\s*\+?\s*years?", lowered)]
    if years and max(years) >= 5 and track is Track.DEVELOPMENT:
        gaps.append(
            Gap(
                requirement=f"{max(years)}+ years of Development experience",
                severity="hard",
                reason="Canonical professional Development history does not meet this threshold.",
            )
        )
    return gaps
