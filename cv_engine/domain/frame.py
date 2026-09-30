"""The draft frame: what a Profile section may carry, and the structure it always keeps.

`draft_resume` chooses which facts a CV uses (docs/decisions/ai-owned-selection.md).
What stays here is what stops an invented fact and keeps a role readable:

- a fact is chosen only from its section's pool of canonical facts;
- every chosen fact has a rendering in the document language;
- headings, dates and contact lines are structure, not evidence, so they are always
  present;
- chosen facts are laid out in pool order, so a role's title, dates and bullets stay
  together and no bullet lands under another role.

Section budgets, tags, per-role minimums and Profile pins are guidance the request
carries. Nothing here enforces them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from .contracts.drafts import ClaimLine
from .contracts.knowledge import FactStatus, Profile, ResumeSectionSpec
from .facts import FactStore

# Headings, dates and contact lines are structure, not evidence.
STRUCTURAL_STYLES = frozenset({"heading", "date", "contact"})

# A historical job title opens a role block; everything until the next title
# belongs to that role.
ROLE_BLOCK_TAG = "historical-title"


class FrameError(ValueError):
    pass


class MissingFactRendering(FrameError):
    """A fact chosen for a document cannot be expressed in its language."""

    def __init__(self, fact_id: str, language: str):
        self.fact_id = fact_id
        self.language = language
        super().__init__(f"fact {fact_id} has no {language!r} rendering")


def require_fact_renderings(
    facts: FactStore, fact_ids: set[str] | frozenset[str] | list[str], language: str
) -> None:
    """Refuse before drafting if one chosen fact cannot render in `language`."""
    for fact_id in sorted(fact_ids):
        fact = facts.get(fact_id, canonical_only=True)
        if not fact.renderings.get(language):
            raise MissingFactRendering(fact_id, language)


def section_pool(spec: ResumeSectionSpec, facts: FactStore) -> list[str]:
    """The section's canonical facts, in the order the Profile declares them.

    A pooled fact that is not canonical cannot be chosen, so it is not offered.
    """
    return [
        fact_id
        for fact_id in spec.fact_ids
        if fact_id in facts.facts and facts.facts[fact_id].status is FactStatus.CANONICAL
    ]


def is_structural(fact_id: str, facts: FactStore) -> bool:
    fact = facts.get(fact_id)
    return fact.resume_style in STRUCTURAL_STYLES or ROLE_BLOCK_TAG in fact.tags


def lay_out_choice(
    profile: Profile,
    facts: FactStore,
    language: str,
    chosen: Mapping[str, Iterable[str]] | None = None,
) -> dict[str, list[str]]:
    """Each section's facts in pool order: the chosen ones plus its structure.

    `chosen` maps a section's English name to the facts picked for it. `None` offers
    every fact in every pool, which is the frame `draft_resume` chooses from. A section
    absent from `chosen` keeps only its structure.

    A section the Profile does not have, or a fact outside its section's canonical
    pool, is refused rather than dropped: the choice came from somewhere that was not
    offered it.
    """
    specs = {spec.name_en: spec for spec in profile.sections}
    if chosen is not None:
        unknown = sorted(set(chosen) - set(specs))
        if unknown:
            raise FrameError(
                f"Profile {profile.profile.value} has no section named: {', '.join(unknown)}"
            )
    laid_out: dict[str, list[str]] = {}
    for name, spec in specs.items():
        pool = section_pool(spec, facts)
        if chosen is None:
            laid_out[name] = pool
            continue
        picked = set(chosen.get(name, ()))
        outside = sorted(picked - set(pool))
        if outside:
            raise FrameError(f"section {name!r} does not offer: {', '.join(outside)}")
        laid_out[name] = [
            fact_id for fact_id in pool if fact_id in picked or is_structural(fact_id, facts)
        ]
    require_fact_renderings(
        facts, {fact_id for ids in laid_out.values() for fact_id in ids}, language
    )
    return laid_out


def dangling_heading(claims: list[ClaimLine]) -> str | None:
    """The first heading in a section that no evidence follows, if any.

    A role title with only its dates under it is a heading nothing supports.
    """
    heading: str | None = None
    supported = True
    for claim in claims:
        if claim.style == "heading":
            if heading is not None and not supported:
                return heading
            heading, supported = claim.text, False
        elif claim.style not in STRUCTURAL_STYLES:
            supported = True
    return None if supported else heading


def misplaced_role_claims(
    claims: list[ClaimLine], spec: ResumeSectionSpec, facts: FactStore
) -> list[str]:
    """Claims that sit under a role other than the one their facts belong to.

    The pool's order says which role each fact belongs to: every fact after a
    historical title, until the next one, is that role's. A claim sits under the last
    role title above it. A bullet or a date that moved under another role is attributed
    to the wrong employer, so each claim's facts must belong to the role it sits under.
    Facts outside the pool are another check's to report.
    """
    role_of: dict[str, str | None] = {}
    current: str | None = None
    for fact_id in spec.fact_ids:
        fact = facts.facts.get(fact_id)
        if fact is not None and ROLE_BLOCK_TAG in fact.tags:
            current = fact_id
        role_of[fact_id] = current
    misplaced: list[str] = []
    current = None
    for claim in claims:
        titles = [
            fact_id
            for fact_id in claim.fact_ids
            if fact_id in facts.facts and ROLE_BLOCK_TAG in facts.facts[fact_id].tags
        ]
        if titles:
            current = titles[0]
        if any(fact_id in role_of and role_of[fact_id] != current for fact_id in claim.fact_ids):
            misplaced.append(claim.claim_id)
    return misplaced
