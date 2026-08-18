from __future__ import annotations

import re
from collections.abc import Sequence

from ..models import FitLevel, Gap, Track


FIT_SEVERITY = {FitLevel.HIGH: 0, FitLevel.MEDIUM: 1, FitLevel.LOW: 2}


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
