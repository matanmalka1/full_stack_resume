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

from dataclasses import dataclass

from ..util import canonical_json, sha256_text
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

SELECTION_POLICY_VERSION = "1.0.0"

# Headings, dates and contact lines are structure, not evidence. They never
# compete with bullets for a section budget.
STRUCTURAL_STYLES = frozenset({"heading", "date", "contact"})

# A historical job title opens a role block; everything until the next title
# belongs to that role.
ROLE_BLOCK_TAG = "historical-title"

# Facts carrying a verified number. A role block described only in duties reads
# as an unmeasured role, so these have their own floor.
QUANTITATIVE_TAG = "verified-quantitative"


class SelectionError(ValueError):
    pass


class EmphasisPolicyStore:
    def __init__(self, policies: dict[Emphasis, EmphasisPolicy], policy_version: str):
        self.policies = policies
        self.policy_version = policy_version
        self.version = sha256_text(
            canonical_json(
                {
                    "policy_version": policy_version,
                    "emphases": [
                        policies[key].model_dump(mode="json") for key in sorted(policies, key=str)
                    ],
                }
            )
        )

    @classmethod
    def from_payload(cls, payload: dict, *, origin: str = "emphasis policy") -> EmphasisPolicyStore:
        """Build the store from an already-read policy document.

        Locating and reading it belongs to the storage adapter; what a complete
        and self-consistent policy set is stays here.
        """
        try:
            policies = {
                Emphasis(key): EmphasisPolicy.model_validate(value)
                for key, value in payload["emphases"].items()
            }
            policy_version = payload["policy_version"]
        except (KeyError, ValueError) as exc:
            raise SelectionError(f"invalid emphasis policy {origin}: {exc}") from exc
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
    extra_pinned: frozenset[str],
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
        pinned=fact.fact_id in set(spec.pinned_fact_ids) or fact.fact_id in extra_pinned,
        tags=tags,
    )


def _omission_reason(scored: _Scored) -> OmissionReason:
    return "not_relevant_to_emphasis" if scored.semantic_score == 0 else "below_section_budget"


def _role_blocks(pool: list[_Scored]) -> list[list[_Scored]]:
    """Split a section pool into the role blocks its titles open.

    Facts before the first historical title belong to the section, not to a
    role, so they are left out: a section without titles has no blocks and no
    floors to honour.
    """
    blocks: list[list[_Scored]] = []
    for item in pool:
        if ROLE_BLOCK_TAG in item.tags:
            blocks.append([])
        elif blocks:
            blocks[-1].append(item)
    return blocks


def _block_floor_picks(
    block: list[_Scored],
    spec: ResumeSectionSpec,
    line_of: dict[str, str],
) -> list[_Scored]:
    """The contenders a role block needs to reach its floors, best-ranked first.

    Pinned evidence already under the heading counts towards both floors, so a
    block that is already substantial pulls nothing extra out of the budget.
    Floors count *lines*, not facts: two facts a presentation rule combines into
    one bullet are one line on the page, which is the only thing a reader counts.
    """
    held = [item for item in block if item.pinned and not item.structural]
    ranked = sorted(
        (item for item in block if not (item.structural or item.pinned)),
        key=lambda item: item.rank,
        reverse=True,
    )
    picks: list[_Scored] = []
    quantitative_needed = spec.min_quantitative_per_role - sum(
        1 for item in held if QUANTITATIVE_TAG in item.tags
    )
    for item in ranked:
        if quantitative_needed <= 0:
            break
        if QUANTITATIVE_TAG in item.tags:
            picks.append(item)
            quantitative_needed -= 1
    lines = {line_of.get(item.fact_id, item.fact_id) for item in held + picks}
    for item in ranked:
        if len(lines) >= spec.min_claims_per_role:
            break
        if item not in picks:
            picks.append(item)
            lines.add(line_of.get(item.fact_id, item.fact_id))
    return picks


def _floor_reach(
    block: list[_Scored],
    spec: ResumeSectionSpec,
    line_of: dict[str, str],
) -> tuple[int, int]:
    """How many lines and quantitative claims this block can reach at its floors."""
    held = [item for item in block if item.pinned and not item.structural]
    reached = held + _block_floor_picks(block, spec, line_of)
    lines = {line_of.get(item.fact_id, item.fact_id) for item in reached}
    return len(lines), sum(1 for item in reached if QUANTITATIVE_TAG in item.tags)


def _refuse_structural_exclusion(
    section: str,
    pool: list[_Scored],
    excluded: frozenset[str],
) -> None:
    """Structure is not evidence, so it is not a user's to remove.

    Headings, dates and contact lines never competed for the budget, and the
    title that opens a role block is what makes the block exist at all. Removing
    one does not shorten the document; it produces bullets under no role, or a
    role under no heading.
    """
    for item in pool:
        if item.fact_id not in excluded:
            continue
        if item.structural:
            raise SelectionError(
                f"section {section!r} cannot exclude the structural claim {item.fact_id}"
            )
        if ROLE_BLOCK_TAG in item.tags:
            raise SelectionError(
                f"section {section!r} cannot exclude {item.fact_id}: it opens a role block"
            )


def _refuse_floor_loss(
    section: str,
    spec: ResumeSectionSpec,
    pool: list[_Scored],
    live: list[_Scored],
    line_of: dict[str, str],
    excluded: frozenset[str],
) -> None:
    """Refuse an exclusion that costs a role block one of its floors.

    Excluding the only quantitative claim under a role would otherwise leave
    that role described in duties alone - exactly the shape
    `min_quantitative_per_role` exists to prevent. The comparison is against
    what the same block reached before the exclusion, not against the floor
    itself, so a block that was already short of its floor for reasons of its
    own keeps behaving as it always did.
    """
    if not excluded:
        return
    for index, (before, after) in enumerate(
        zip(_role_blocks(pool), _role_blocks(live), strict=True)
    ):
        before_lines, before_quantitative = _floor_reach(before, spec, line_of)
        after_lines, after_quantitative = _floor_reach(after, spec, line_of)
        if after_lines >= before_lines and after_quantitative >= before_quantitative:
            continue
        blocking = sorted(
            item.fact_id
            for item in _block_floor_picks(before, spec, line_of)
            if item.fact_id in excluded
        )
        raise SelectionError(
            f"section {section!r} role block {index + 1} cannot reach its floors without "
            f"{', '.join(blocking) or 'the excluded facts'}"
        )


def _refuse_uncovered_required_tags(
    profile: Profile,
    pools: dict[str, list[_Scored]],
    scored: dict[str, list[_Scored]],
    chosen: dict[str, set[str]],
    excluded: frozenset[str],
) -> None:
    """Refuse an exclusion that empties a required tag the rescue cannot refill.

    `_rescue_required_tags` pulls a covering fact back in when one is available.
    An exclusion can remove the last one, and the rescue then finds nothing and
    says nothing. A Profile that cannot evidence its own required tag is not
    that Profile, so this is a refusal rather than a warning - but only when an
    excluded fact is what would have covered it, since a tag no fact in the
    Profile carries has always been left uncovered.
    """
    if not excluded:
        return
    selected = {fact_id for ids in chosen.values() for fact_id in ids}
    for tag in profile.required_tags:
        if any(
            tag in item.tags
            for pool in scored.values()
            for item in pool
            if item.fact_id in selected
        ):
            continue
        blocking = sorted(
            item.fact_id
            for pool in pools.values()
            for item in pool
            if tag in item.tags and item.fact_id in excluded
        )
        if blocking:
            raise SelectionError(
                f"required tag {tag!r} would be left uncovered by excluding {', '.join(blocking)}"
            )


def build_selection(
    *,
    analysis: JobAnalysis,
    profile: Profile,
    policy: EmphasisPolicy,
    policy_store_version: str,
    facts: FactStore,
    line_groups: dict[str, list[tuple[str, ...]]] | None = None,
    pinned_fact_ids: frozenset[str] = frozenset(),
    excluded_fact_ids: frozenset[str] = frozenset(),
) -> tuple[dict[str, list[str]], SelectionManifest]:
    """Choose each section's facts and record why.

    Returns the per-section selected fact IDs in pool order, plus the manifest
    describing every candidate that was considered.

    `line_groups` names, per section, the fact groups a presentation rule would
    render as a single line. Role-block floors and ceilings are stated in lines,
    so selection has to know which facts will share one, or a section that
    combines two facts into one bullet quietly overshoots its own ceiling.

    `pinned_fact_ids` and `excluded_fact_ids` are one user's explicit selection
    decisions, laid over the Profile's own pins. They constrain the engine; they
    do not replace it. Everything the overlay does not name is still chosen
    here, under the same section budgets, role-block floors and required-tag
    rescue, so a plan built from a review form is the same kind of object as one
    built from nothing.

    The overlay is refused rather than trimmed. A fact the Profile never offered,
    a fact named on both sides, a heading or date removed as if it were evidence,
    an exclusion that empties a role block below its floor, and an exclusion that
    leaves a required tag with nothing to cover it all raise `SelectionError`.
    Silently dropping any of them would either discard what the user asked for or
    break an invariant the document depends on.
    """
    overlap = sorted(pinned_fact_ids & excluded_fact_ids)
    if overlap:
        raise SelectionError(f"facts cannot be pinned and excluded at once: {', '.join(overlap)}")
    pool_ids = {fact_id for spec in profile.sections for fact_id in spec.fact_ids}
    unknown = sorted((pinned_fact_ids | excluded_fact_ids) - pool_ids)
    if unknown:
        raise SelectionError(
            f"Profile {profile.profile.value} offers no candidate named: {', '.join(unknown)}"
        )

    gap_substitutes = frozenset(
        fact_id for gap in analysis.gaps for fact_id in gap.substitute_fact_ids
    )

    # `pools` is every candidate the Profile offered, and is what the manifest
    # accounts for; `scored` is what the engine may still choose from. They are
    # the same object when nothing is excluded.
    pools: dict[str, list[_Scored]] = {}
    scored: dict[str, list[_Scored]] = {}
    chosen: dict[str, set[str]] = {}
    outcomes: dict[str, SelectionOutcome] = {}
    reasons: dict[str, OmissionReason] = {}
    protected: set[str] = set()

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
                extra_pinned=pinned_fact_ids,
            )
            for index, fact_id in enumerate(spec.fact_ids)
        ]
        pools[section] = pool
        _refuse_structural_exclusion(section, pool, excluded_fact_ids)
        live = [item for item in pool if item.fact_id not in excluded_fact_ids]
        scored[section] = live
        for item in pool:
            if item.fact_id in excluded_fact_ids:
                outcomes[item.fact_id] = "omitted"
                reasons[item.fact_id] = "excluded_by_user"
        held = [item for item in live if item.structural or item.pinned]
        budget = spec.max_claims if spec.max_claims is not None else len(live)
        if len(held) > budget:
            raise SelectionError(
                f"section {section!r} pins {len(held)} facts into a budget of {budget}"
            )
        allowance = budget - len(held)
        line_of = {
            fact_id: group[0] for group in (line_groups or {}).get(section, []) for fact_id in group
        }
        _refuse_floor_loss(section, spec, pool, live, line_of, excluded_fact_ids)
        floor_picks: list[_Scored] = []
        for block in _role_blocks(live):
            for item in _block_floor_picks(block, spec, line_of):
                if item not in floor_picks:
                    floor_picks.append(item)
        if len(floor_picks) > allowance:
            raise SelectionError(
                f"section {section!r} needs {len(floor_picks)} claims to reach its "
                f"role-block floors but has room for {allowance}"
            )
        protected.update(item.fact_id for item in floor_picks)
        contenders = sorted(
            (item for item in live if not (item.structural or item.pinned)),
            key=lambda item: item.rank,
            reverse=True,
        )
        floor_ids = {item.fact_id for item in floor_picks}
        block_of = {
            item.fact_id: index for index, block in enumerate(_role_blocks(live)) for item in block
        }
        # Lines already spoken for in each block: pinned evidence, then the
        # floor picks. Facts that share a presentation line share one entry.
        taken: dict[int, set[str]] = {}
        for item in live:
            if item.pinned and not item.structural and item.fact_id in block_of:
                taken.setdefault(block_of[item.fact_id], set()).add(
                    line_of.get(item.fact_id, item.fact_id)
                )
        for item in floor_picks:
            taken.setdefault(block_of[item.fact_id], set()).add(
                line_of.get(item.fact_id, item.fact_id)
            )
        winners = list(floor_picks)
        for item in contenders:
            if len(winners) >= allowance:
                break
            if item.fact_id in floor_ids:
                continue
            block = block_of.get(item.fact_id)
            line = line_of.get(item.fact_id, item.fact_id)
            if (
                block is not None
                and spec.max_claims_per_role is not None
                and line not in taken.get(block, set())
                and len(taken.get(block, set())) >= spec.max_claims_per_role
            ):
                continue
            winners.append(item)
            if block is not None:
                taken.setdefault(block, set()).add(line)
        winner_ids = {item.fact_id for item in winners}
        chosen[section] = {item.fact_id for item in held} | winner_ids
        for item in held:
            outcomes[item.fact_id] = "pinned"
        for item in winners:
            outcomes[item.fact_id] = "selected"
        for item in contenders:
            if item.fact_id in winner_ids:
                continue
            outcomes[item.fact_id] = "omitted"
            reasons[item.fact_id] = _omission_reason(item)

    _rescue_required_tags(profile, scored, chosen, outcomes, reasons, protected)
    _refuse_uncovered_required_tags(profile, pools, scored, chosen, excluded_fact_ids)

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
        for pool in pools.values()
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
    protected: set[str],
) -> None:
    """Force a Profile's structural invariants back into the document.

    `Profile.required_tags` describes what a Profile must be able to evidence at
    all — an Account Manager CV without a single account-management fact is not
    an Account Manager CV, whatever the Emphasis says. So a required tag left
    uncovered by scoring pulls in the best-ranked omitted fact carrying it and
    evicts the weakest ordinary selection from that same section, keeping the
    budget intact. Emphasis preferences deliberately get no such power.

    Claims holding a role block up to its floors are not ordinary selections and
    cannot be evicted: a rescue that emptied a role to satisfy a tag would trade
    one structural invariant for another.
    """
    for tag in profile.required_tags:
        selected = {fact_id for ids in chosen.values() for fact_id in ids}
        if any(
            tag in item.tags
            for pool in scored.values()
            for item in pool
            if item.fact_id in selected
        ):
            continue
        available = sorted(
            (
                item
                for pool in scored.values()
                for item in pool
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
                item
                for item in scored[winner.section]
                if item.fact_id in chosen[winner.section]
                and outcomes.get(item.fact_id) == "selected"
                and item.fact_id not in protected
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
