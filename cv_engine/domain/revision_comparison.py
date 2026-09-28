"""What changed between two approved resumes, anchored to claims and facts.

The comparison is between two immutable documents and reads them only. It is
not a text diff: every line of a draft carries a stable `claim_id` and the
canonical `fact_ids` it states, so a line is followed through a revision by
identity first and by wording last. That is what lets the result say "the same
fact, reworded" or "moved from Core Skills" instead of one removed line and one
added line that happen to look alike.

Lines are paired in three passes, each over what the previous one left:

1. the same `claim_id` - the line a new draft inherited from its parent;
2. the same text - a line re-created with identical wording;
3. the same non-empty set of facts and the same style - the same statement
   worded differently.

A pair whose text differs is `reworded`; one whose section differs is `moved`;
anything left over is `added` (only in the newer revision) or `removed` (only in
the older one). Order inside a section is not reported as a change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .contracts.drafts import ClaimLine, ClaimStyle, DraftDocument

SectionKind = Literal["headline", "contacts", "section"]
ChangeKind = Literal["added", "removed", "reworded", "moved"]
SectionStatus = Literal["added", "removed", "changed", "unchanged"]


@dataclass(frozen=True)
class ClaimChange:
    kind: ChangeKind
    style: ClaimStyle
    before_text: str | None
    after_text: str | None
    fact_ids: tuple[str, ...]
    #: The section a `moved` or `reworded` line was in before, when it differs.
    from_section: str | None = None


@dataclass(frozen=True)
class SectionComparison:
    kind: SectionKind
    name: str
    status: SectionStatus
    changes: tuple[ClaimChange, ...]
    unchanged_count: int


@dataclass(frozen=True)
class ChangeSummary:
    added: int = 0
    removed: int = 0
    reworded: int = 0
    moved: int = 0
    unchanged: int = 0


@dataclass(frozen=True)
class DraftComparison:
    sections: tuple[SectionComparison, ...]
    summary: ChangeSummary
    profile_changed: bool
    emphasis_changed: bool
    language_changed: bool


@dataclass
class _Slot:
    key: tuple[SectionKind, str]
    order: int
    claim: ClaimLine
    partner: _Slot | None = field(default=None, repr=False)


def _slots(document: DraftDocument) -> list[_Slot]:
    slots = [_Slot(("headline", ""), 0, document.headline)]
    slots.extend(
        _Slot(("contacts", ""), index, claim) for index, claim in enumerate(document.contacts)
    )
    slots.extend(
        _Slot(("section", section.name), index, claim)
        for section in document.sections
        for index, claim in enumerate(section.claims)
    )
    return slots


def _section_keys(document: DraftDocument) -> list[tuple[SectionKind, str]]:
    return [
        ("headline", ""),
        ("contacts", ""),
        *(("section", section.name) for section in document.sections),
    ]


def _pair(older: list[_Slot], newer: list[_Slot], key) -> None:
    """Pair still-unpaired slots whose `key` agrees, first come first served."""
    waiting: dict[object, list[_Slot]] = {}
    for slot in older:
        if slot.partner is None and (value := key(slot.claim)) is not None:
            waiting.setdefault(value, []).append(slot)
    for slot in newer:
        if slot.partner is not None or (value := key(slot.claim)) is None:
            continue
        candidates = waiting.get(value)
        if candidates:
            match = candidates.pop(0)
            match.partner, slot.partner = slot, match


def _facts_key(claim: ClaimLine):
    return (claim.style, frozenset(claim.fact_ids)) if claim.fact_ids else None


def compare_drafts(older: DraftDocument, newer: DraftDocument) -> DraftComparison:
    """Every line of `newer` against `older`, grouped by section in `newer`'s order."""
    before = _slots(older)
    after = _slots(newer)
    # The headline is one line in both documents, so it is always the same line.
    before[0].partner, after[0].partner = after[0], before[0]
    _pair(before, after, lambda claim: claim.claim_id)
    _pair(before, after, lambda claim: claim.text.strip())
    _pair(before, after, _facts_key)

    changes: dict[tuple[SectionKind, str], list[ClaimChange]] = {}
    unchanged: dict[tuple[SectionKind, str], int] = {}
    for slot in after:
        partner = slot.partner
        claim = slot.claim
        if partner is None:
            change = ClaimChange("added", claim.style, None, claim.text, tuple(claim.fact_ids))
        else:
            moved_from = partner.key[1] if partner.key != slot.key else None
            if partner.claim.text != claim.text:
                change = ClaimChange(
                    "reworded",
                    claim.style,
                    partner.claim.text,
                    claim.text,
                    tuple(claim.fact_ids),
                    moved_from,
                )
            elif moved_from is not None:
                change = ClaimChange(
                    "moved", claim.style, claim.text, claim.text, tuple(claim.fact_ids), moved_from
                )
            else:
                unchanged[slot.key] = unchanged.get(slot.key, 0) + 1
                continue
        changes.setdefault(slot.key, []).append(change)
    for slot in before:
        if slot.partner is None:
            claim = slot.claim
            changes.setdefault(slot.key, []).append(
                ClaimChange("removed", claim.style, claim.text, None, tuple(claim.fact_ids))
            )

    older_keys = _section_keys(older)
    newer_keys = _section_keys(newer)
    ordered = newer_keys + [key for key in older_keys if key not in newer_keys]
    sections: list[SectionComparison] = []
    for key in ordered:
        section_changes = tuple(changes.get(key, ()))
        if key not in older_keys:
            status: SectionStatus = "added"
        elif key not in newer_keys:
            status = "removed"
        else:
            status = "changed" if section_changes else "unchanged"
        count = unchanged.get(key, 0)
        # Contacts are optional; a document without any on either side has nothing to show.
        if key[0] == "contacts" and not section_changes and count == 0:
            continue
        sections.append(SectionComparison(key[0], key[1], status, section_changes, count))

    every = [change for section in sections for change in section.changes]
    summary = ChangeSummary(
        added=sum(change.kind == "added" for change in every),
        removed=sum(change.kind == "removed" for change in every),
        reworded=sum(change.kind == "reworded" for change in every),
        moved=sum(change.kind == "moved" for change in every),
        unchanged=sum(section.unchanged_count for section in sections),
    )
    return DraftComparison(
        sections=tuple(sections),
        summary=summary,
        profile_changed=older.profile != newer.profile,
        emphasis_changed=older.emphasis != newer.emphasis,
        language_changed=older.language != newer.language,
    )
