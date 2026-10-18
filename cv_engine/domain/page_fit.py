"""Which line a CV gives up first when it runs past its page limit.

A pure policy: it reads a draft, its Profile and the facts, and names one claim. It
never measures anything - how many pages a draft takes is the renderer's to say -
and it never drops a line itself; `drop_claims` does that.

What may go:

- only a section's evidence lines: never the headline, a contact, a heading or a date;
- never a line linked to a fact its section pins (`pinned_fact_ids`);
- a role keeps at least `max(1, min_claims_per_role)` lines under its title, and any
  other heading keeps one, so no heading is ever left with nothing under it;
- lines before a section's first heading may all go when the section has headings;
- a section with no headings keeps one line, unless its Profile marks it optional,
  in which case it may lose them all and is dropped from the document.

Which goes: among the blocks (a heading and the lines under it, or a section's lines
with no heading above them) that hold a removable line, the block furthest above its
floor; on a tie, the one later in the document - an older role, a later section.
Within that block its last removable line goes, since a section's lines are laid out
in the Profile's pool order and the last is the one the Profile ranks lowest.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts.drafts import ClaimLine, DraftDocument
from .contracts.knowledge import Profile, ResumeSectionSpec
from .facts import FactStore
from .frame import ROLE_BLOCK_TAG, STRUCTURAL_STYLES


@dataclass(frozen=True)
class TrimmedLine:
    """Where a dropped line sat and what it said, read before it was dropped."""

    claim_id: str
    section: str
    heading: str | None
    text: str


@dataclass(frozen=True)
class _Block:
    heading: ClaimLine | None
    lines: tuple[ClaimLine, ...]


def _blocks(claims: list[ClaimLine]) -> list[_Block]:
    """A section's lines grouped under the heading above them, in document order."""
    blocks: list[_Block] = []
    heading: ClaimLine | None = None
    lines: list[ClaimLine] = []
    for claim in claims:
        if claim.style == "heading":
            if heading is not None or lines:
                blocks.append(_Block(heading, tuple(lines)))
            heading, lines = claim, []
        elif claim.style not in STRUCTURAL_STYLES:
            lines.append(claim)
    if heading is not None or lines:
        blocks.append(_Block(heading, tuple(lines)))
    return blocks


def _is_role(heading: ClaimLine, facts: FactStore) -> bool:
    return any(
        fact_id in facts.facts and ROLE_BLOCK_TAG in facts.facts[fact_id].tags
        for fact_id in heading.fact_ids
    )


def _floor(block: _Block, spec: ResumeSectionSpec, headed: bool, facts: FactStore) -> int:
    """How many lines a block keeps however long the document runs."""
    if block.heading is None:
        if headed:
            return 0
        return 0 if spec.optional else 1
    if _is_role(block.heading, facts):
        return max(1, spec.min_claims_per_role)
    return 1


def _never_dropped(claim: ClaimLine, pinned: frozenset[str], facts: FactStore) -> bool:
    if pinned.intersection(claim.fact_ids):
        return True
    # A role title is structure even when it is not styled as a heading.
    return any(
        fact_id in facts.facts and ROLE_BLOCK_TAG in facts.facts[fact_id].tags
        for fact_id in claim.fact_ids
    )


def next_trim(draft: DraftDocument, profile: Profile, facts: FactStore) -> str | None:
    """The claim to drop next to shorten `draft`, or None when nothing may go."""
    specs = {
        (spec.name_he if draft.language == "he" else spec.name_en): spec
        for spec in profile.sections
    }
    best: tuple[int, tuple[int, int], str] | None = None
    for section_index, section in enumerate(draft.sections):
        spec = specs.get(section.name)
        if spec is None:
            continue
        pinned = frozenset(spec.pinned_fact_ids)
        blocks = _blocks(section.claims)
        headed = any(block.heading is not None for block in blocks)
        for block_index, block in enumerate(blocks):
            surplus = len(block.lines) - _floor(block, spec, headed, facts)
            removable = [line for line in block.lines if not _never_dropped(line, pinned, facts)]
            if surplus <= 0 or not removable:
                continue
            candidate = (surplus, (section_index, block_index), removable[-1].claim_id)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
    return None if best is None else best[2]


def trimmed_line(draft: DraftDocument, claim_id: str) -> TrimmedLine:
    """The section line `claim_id` names, with the heading it sits under."""
    for section in draft.sections:
        heading: str | None = None
        for claim in section.claims:
            if claim.style == "heading":
                heading = claim.text
            if claim.claim_id == claim_id:
                return TrimmedLine(
                    claim_id=claim_id, section=section.name, heading=heading, text=claim.text
                )
    raise KeyError(claim_id)
