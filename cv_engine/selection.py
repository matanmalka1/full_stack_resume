"""Deterministic content selection.

Before this module existed, a Profile's `fact_ids` were a fixed output list:
every fact a Profile named reached the document, so Emphasis, job text, keywords
and gaps could not change what the CV said. Selection now happens here, once,
under an explicit authority order:

    pinned > required-tag rescue > gap substitute > Profile/Emphasis semantics > job keywords

The last three are a lexicographic ranking, not a weighted sum. That is what
keeps the order an authority order: no amount of keyword overlap in a job
posting can lift a fact above one the Profile and Emphasis consider central,
because keywords are only consulted when the semantic scores are equal.

Selection decides *what* enters a section. Emission order stays the pool's
declared order, so relevance never reshuffles a chronology or separates a role
heading from the bullets underneath it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .facts import FactStore
from .models import (
    Emphasis,
    EmphasisPolicy,
    Fact,
    JobAnalysis,
    OmissionReason,
    Profile,
    ResumeSectionSpec,
    SelectionCandidate,
    SelectionManifest,
    SelectionOutcome,
)
from .util import canonical_json, sha256_text


SELECTION_POLICY_VERSION = "1.0.0"

# Headings, dates and contact lines are structure, not evidence. They never
# compete with bullets for a section budget.
STRUCTURAL_STYLES = frozenset({"heading", "date", "contact"})


class SelectionError(ValueError):
    pass


class EmphasisPolicyStore:
    def __init__(self, policies: dict[Emphasis, EmphasisPolicy], policy_version: str):
        self.policies = policies
        self.policy_version = policy_version
        self.version = sha256_text(canonical_json({
            "policy_version": policy_version,
            "emphases": [policies[key].model_dump(mode="json") for key in sorted(policies, key=str)],
        }))

    @classmethod
    def load(cls, root: Path) -> "EmphasisPolicyStore":
        path = root / "config" / "emphasis.json"
        if not path.is_file():
            raise SelectionError(f"missing emphasis policy: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SelectionError(f"invalid emphasis policy {path}: {exc}") from exc
        try:
            policies = {
                Emphasis(key): EmphasisPolicy.model_validate(value)
                for key, value in payload["emphases"].items()
            }
            policy_version = payload["policy_version"]
        except (KeyError, ValueError) as exc:
            raise SelectionError(f"invalid emphasis policy {path}: {exc}") from exc
        for emphasis, policy in policies.items():
            if policy.emphasis is not emphasis:
                raise SelectionError(f"emphasis policy {emphasis} is filed under the wrong key")
        missing = sorted(str(item) for item in set(Emphasis) - set(policies))
        if missing:
            raise SelectionError(f"missing emphasis policies: {', '.join(missing)}")
        return cls(policies, policy_version)

    def get(self, emphasis: Emphasis | str) -> EmphasisPolicy:
        return self.policies[Emphasis(emphasis)]


@dataclass(frozen=True)
class _Scored:
    fact_id: str
    section: str
    pool_index: int
    profile_score: int
    emphasis_score: int
    keyword_hits: int
    gap_substitute: bool
    structural: bool
    pinned: bool
    tags: frozenset[str]

    @property
    def semantic_score(self) -> int:
        return self.profile_score + self.emphasis_score

    @property
    def rank(self) -> tuple[int, int, int, int]:
        """Authority order as a sort key, highest first.

        Ties fall back to the declared pool position so the same inputs always
        produce the same document.
        """
        return (
            int(self.gap_substitute),
            self.semantic_score,
            self.keyword_hits,
            -self.pool_index,
        )


def _keyword_hits(fact: Fact, keywords: list[str]) -> int:
    haystack = f"{fact.meaning} {' '.join(fact.tags)}".casefold()
    return sum(1 for keyword in keywords if keyword.casefold() in haystack)


def _score(
    fact: Fact,
    *,
    section: str,
    pool_index: int,
    spec: ResumeSectionSpec,
    profile: Profile,
    policy: EmphasisPolicy,
    analysis: JobAnalysis,
    gap_substitutes: frozenset[str],
) -> _Scored:
    tags = frozenset(fact.tags)
    return _Scored(
        fact_id=fact.fact_id,
        section=section,
        pool_index=pool_index,
        profile_score=sum(profile.tag_weights.get(tag, 0) for tag in tags),
        emphasis_score=sum(policy.tag_weights.get(tag, 0) for tag in tags),
        keyword_hits=_keyword_hits(fact, analysis.keywords),
        gap_substitute=fact.fact_id in gap_substitutes,
        structural=fact.resume_style in STRUCTURAL_STYLES,
        pinned=fact.fact_id in set(spec.pinned_fact_ids),
        tags=tags,
    )


def _omission_reason(scored: _Scored) -> OmissionReason:
    return "not_relevant_to_emphasis" if scored.semantic_score == 0 else "below_section_budget"


def build_selection(
    *,
    analysis: JobAnalysis,
    profile: Profile,
    policy: EmphasisPolicy,
    policy_store_version: str,
    facts: FactStore,
) -> tuple[dict[str, list[str]], SelectionManifest]:
    """Choose each section's facts and record why.

    Returns the per-section selected fact IDs in pool order, plus the manifest
    describing every candidate that was considered.
    """
    gap_substitutes = frozenset(
        fact_id for gap in analysis.gaps for fact_id in gap.substitute_fact_ids
    )

    scored: dict[str, list[_Scored]] = {}
    chosen: dict[str, set[str]] = {}
    outcomes: dict[str, SelectionOutcome] = {}
    reasons: dict[str, OmissionReason] = {}

    for spec in profile.sections:
        section = spec.name_en
        pool = [
            _score(
                facts.get(fact_id, canonical_only=True),
                section=section,
                pool_index=index,
                spec=spec,
                profile=profile,
                policy=policy,
                analysis=analysis,
                gap_substitutes=gap_substitutes,
            )
            for index, fact_id in enumerate(spec.fact_ids)
        ]
        scored[section] = pool
        held = [item for item in pool if item.structural or item.pinned]
        budget = spec.max_claims if spec.max_claims is not None else len(pool)
        if len(held) > budget:
            raise SelectionError(
                f"section {section!r} pins {len(held)} facts into a budget of {budget}"
            )
        contenders = sorted(
            (item for item in pool if not (item.structural or item.pinned)),
            key=lambda item: item.rank,
            reverse=True,
        )
        winners = contenders[: budget - len(held)]
        chosen[section] = {item.fact_id for item in held} | {item.fact_id for item in winners}
        for item in held:
            outcomes[item.fact_id] = "pinned"
        for item in winners:
            outcomes[item.fact_id] = "selected"
        for item in contenders[budget - len(held):]:
            outcomes[item.fact_id] = "omitted"
            reasons[item.fact_id] = _omission_reason(item)

    _rescue_required_tags(profile, scored, chosen, outcomes, reasons)

    selected_by_section = {
        spec.name_en: [fact_id for fact_id in spec.fact_ids if fact_id in chosen[spec.name_en]]
        for spec in profile.sections
    }
    selected_ids = {fact_id for ids in selected_by_section.values() for fact_id in ids}

    candidates = [
        SelectionCandidate(
            fact_id=item.fact_id,
            section=item.section,
            pool_index=item.pool_index,
            profile_score=item.profile_score,
            emphasis_score=item.emphasis_score,
            semantic_score=item.semantic_score,
            keyword_hits=item.keyword_hits,
            gap_substitute=item.gap_substitute,
            outcome=outcomes[item.fact_id],
            reason=reasons.get(item.fact_id),
        )
        for pool in scored.values()
        for item in pool
    ]
    manifest = SelectionManifest(
        policy_version=SELECTION_POLICY_VERSION,
        emphasis=analysis.emphasis,
        emphasis_policy_version=policy_store_version,
        candidates=candidates,
        selected_fact_ids=sorted(selected_ids),
        required_tag_coverage=_coverage(profile.required_tags, scored, selected_ids),
        preferred_tag_coverage=_coverage(policy.preferred_tags, scored, selected_ids),
    )
    return selected_by_section, manifest


def _coverage(
    tags: list[str],
    scored: dict[str, list[_Scored]],
    selected_ids: set[str],
) -> dict[str, list[str]]:
    return {
        tag: sorted(
            item.fact_id
            for pool in scored.values()
            for item in pool
            if tag in item.tags and item.fact_id in selected_ids
        )
        for tag in tags
    }


def _rescue_required_tags(
    profile: Profile,
    scored: dict[str, list[_Scored]],
    chosen: dict[str, set[str]],
    outcomes: dict[str, SelectionOutcome],
    reasons: dict[str, OmissionReason],
) -> None:
    """Force a Profile's structural invariants back into the document.

    `Profile.required_tags` describes what a Profile must be able to evidence at
    all — an Account Manager CV without a single account-management fact is not
    an Account Manager CV, whatever the Emphasis says. So a required tag left
    uncovered by scoring pulls in the best-ranked omitted fact carrying it and
    evicts the weakest ordinary selection from that same section, keeping the
    budget intact. Emphasis preferences deliberately get no such power.
    """
    for tag in profile.required_tags:
        selected = {fact_id for ids in chosen.values() for fact_id in ids}
        if any(tag in item.tags for pool in scored.values() for item in pool if item.fact_id in selected):
            continue
        available = sorted(
            (
                item for pool in scored.values() for item in pool
                if tag in item.tags and outcomes.get(item.fact_id) == "omitted"
            ),
            key=lambda item: item.rank,
            reverse=True,
        )
        if not available:
            # Nothing in any pool can evidence the tag; validation reports the
            # gap rather than this layer inventing a fact to fill it.
            continue
        winner = available[0]
        evictable = sorted(
            (
                item for item in scored[winner.section]
                if item.fact_id in chosen[winner.section]
                and outcomes.get(item.fact_id) == "selected"
                and tag not in item.tags
            ),
            key=lambda item: item.rank,
        )
        if not evictable:
            raise SelectionError(
                f"section {winner.section!r} cannot make room for required tag {tag!r}"
            )
        loser = evictable[0]
        chosen[winner.section].discard(loser.fact_id)
        outcomes[loser.fact_id] = "omitted"
        reasons[loser.fact_id] = "evicted_by_required_tag_rescue"
        chosen[winner.section].add(winner.fact_id)
        outcomes[winner.fact_id] = "rescued"
        reasons.pop(winner.fact_id, None)
