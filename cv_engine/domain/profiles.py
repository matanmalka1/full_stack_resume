from __future__ import annotations

import re

from ..util import canonical_json, sha256_text
from .contracts.knowledge import FactStatus, Profile
from .contracts.taxonomy import ProfileName
from .facts import FactStore
from .selection import ROLE_BLOCK_TAG


class ProfileStoreError(ValueError):
    pass


# A role block's span, as the fact store states it: "YYYY-MM/YYYY-MM". The month
# alternation is part of the shape on purpose: `\d{2}` would read "2025-13" as a
# thirteenth month and carry it into the sweep as an ordinal no calendar month
# occupies, which then decides whether a timeline has a hole in it.
_ROLE_SPAN = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])\s*/\s*(\d{4})-(0[1-9]|1[0-2])$")


def _month(year: str, month: str) -> int:
    """A year and month as one comparable ordinal, so spans can be swept."""
    return int(year) * 12 + int(month)


def _dated_roles(facts: FactStore) -> dict[str, tuple[int, int]]:
    """Every canonical role block the fact store declares, as a month span.

    A role block opens the employment history a reader dates by eye, so a
    canonical role fact whose span cannot be read is refused here rather than
    skipped. Skipping it would let a role escape the coverage rule below by
    losing its dates, which is exactly the disappearance the rule exists to
    prevent.

    Readable means a real interval, not merely a numeric shape. A month outside
    01..12 and an end before its start both parse and both produce an ordinal
    the gap sweep would compare in good faith, so a nonsense span could decide
    that a timeline is continuous. Refusing them keeps the sweep's inputs
    meaningful rather than merely well-formed.

    The heading style is checked rather than assumed. Coverage only proves a
    Profile *offers* a role; what makes offering it enough is that selection
    treats a heading as structure and carries it unconditionally. A role styled
    as a bullet is scored as evidence instead, competes for the section budget,
    and can be dropped below it - so it would satisfy this rule and still vanish
    from the page, which is precisely the disappearance the rule exists to
    prevent. `_refuse_structural_exclusion` already guards the overlay against a
    title that is not structural; this closes the same hole on the budget side,
    at the one place that can see every role at once.
    """
    spans: dict[str, tuple[int, int]] = {}
    for fact_id in sorted(facts.facts):
        fact = facts.facts[fact_id]
        if fact.status is not FactStatus.CANONICAL or ROLE_BLOCK_TAG not in fact.tags:
            continue
        if fact.resume_style != "heading":
            raise ProfileStoreError(
                f"role fact {fact_id} is styled {fact.resume_style!r}, not 'heading': a role "
                "title selection does not treat as structure can be dropped by a section budget"
            )
        match = _ROLE_SPAN.match(fact.effective_dates or "")
        if match is None:
            raise ProfileStoreError(
                f"role fact {fact_id} has no readable span: expected "
                f"'YYYY-MM/YYYY-MM', found {fact.effective_dates!r}"
            )
        start, end = _month(*match.group(1, 2)), _month(*match.group(3, 4))
        if end < start:
            raise ProfileStoreError(
                f"role fact {fact_id} ends before it starts: {fact.effective_dates!r}"
            )
        spans[fact_id] = (start, end)
    return spans


def _refuse_unaccounted_roles(
    profile: Profile, origin: str, spans: dict[str, tuple[int, int]]
) -> frozenset[str]:
    """Refuse a Profile that neither offers a dated role nor waives it.

    A Profile may reorder, rename or de-emphasize a dated canonical role, and it
    may decline to carry one - a development CV owes no account of a 2019 sales
    job. What it may not do is drop one silently. Every dated role is therefore
    either in a section pool or named in `omitted_roles` against a reason, so a
    role added to the fact store tomorrow fails every Profile until each one has
    decided about it, rather than disappearing from all of them at once.

    Returns the dated roles this Profile offers, for the timeline check.
    """
    pool = {fact_id for spec in profile.sections for fact_id in spec.fact_ids}
    offered = frozenset(pool & set(spans))
    waived = set(profile.omitted_roles)
    stale = sorted(waived - set(spans))
    if stale:
        raise ProfileStoreError(
            f"profile {origin} waives {', '.join(stale)}, which is not a dated canonical role"
        )
    contradicted = sorted(waived & offered)
    if contradicted:
        raise ProfileStoreError(
            f"profile {origin} both offers and waives {', '.join(contradicted)}"
        )
    unaccounted = sorted(set(spans) - offered - waived)
    if unaccounted:
        raise ProfileStoreError(
            f"profile {origin} neither offers nor waives {', '.join(unaccounted)}: a dated "
            "role is carried or declined in omitted_roles, never left out silently"
        )
    return offered


def _refuse_interior_gap(
    origin: str, spans: dict[str, tuple[int, int]], offered: frozenset[str]
) -> None:
    """Refuse a hole between two roles the Profile does offer.

    Dates are printed, so what the page asserts is bounded by them. Ending the
    history early states nothing about the months after it, and starting it late
    states nothing about the months before; both are incomplete, not false. A
    hole *between* two printed roles is different: the reader sees two roles
    abutting and reads them as consecutive, which the dates deny. That is the
    one omission the document itself misrepresents, so no waiver clears it - a
    waived role is simply absent from `offered`, and the roles left around the
    hole are what fails here.
    """
    ordered = sorted((spans[fact_id], fact_id) for fact_id in offered)
    if not ordered:
        return
    (_, covered_to), previous = ordered[0]
    for (start, end), fact_id in ordered[1:]:
        if start > covered_to + 1:
            raise ProfileStoreError(
                f"profile {origin} leaves an unexplained gap between {previous} and "
                f"{fact_id}: the employment history it prints reads as continuous"
            )
        covered_to = max(covered_to, end)
        previous = fact_id


class ProfileStore:
    def __init__(
        self, profiles: dict[ProfileName, Profile], sources: dict[ProfileName, str] | None = None
    ):
        self.profiles = profiles
        # Where each profile came from, as an opaque label for messages and
        # records. It is not a path this layer may resolve or open.
        self.sources = sources or {}
        self.version = sha256_text(
            canonical_json(
                [profiles[key].model_dump(mode="json") for key in sorted(profiles, key=str)]
            )
        )

    @classmethod
    def from_documents(cls, documents: dict[str, dict], facts: FactStore) -> ProfileStore:
        """Build the store from already-read profile documents, keyed by origin.

        Finding and reading those documents is the storage adapter's job. What
        stays here is what a profile set must satisfy: every profile present,
        none duplicated, every fact it names known to the fact store, and every
        dated role in that store either carried or explicitly declined.

        The employment-history rules belong here rather than in selection
        because they are a property of the profile set crossed with the fact
        store, fixed before any job is analysed. A role title is heading-styled
        and therefore structural, so selection already carries every one a
        Profile offers and refuses every attempt to exclude one; the only place
        a role can go missing is the pool declared here.
        """
        if not documents:
            raise ProfileStoreError("no profile files found")
        spans = _dated_roles(facts)
        result: dict[ProfileName, Profile] = {}
        sources: dict[ProfileName, str] = {}
        for origin in sorted(documents):
            try:
                profile = Profile.model_validate(documents[origin])
            except ValueError as exc:
                raise ProfileStoreError(f"invalid profile {origin}: {exc}") from exc
            if profile.profile in result:
                raise ProfileStoreError(f"duplicate profile: {profile.profile}")
            for section in profile.sections:
                for fact_id in section.fact_ids:
                    facts.get(fact_id)
            offered = _refuse_unaccounted_roles(profile, origin, spans)
            _refuse_interior_gap(origin, spans, offered)
            result[profile.profile] = profile
            sources[profile.profile] = origin
        required = set(ProfileName)
        if set(result) != required:
            missing = sorted(str(item) for item in required - set(result))
            raise ProfileStoreError(f"missing profiles: {', '.join(missing)}")
        return cls(result, sources)

    def get(self, name: ProfileName | str) -> Profile:
        key = ProfileName(name)
        return self.profiles[key]

    def source(self, name: ProfileName | str) -> str:
        key = ProfileName(name)
        try:
            return self.sources[key]
        except KeyError as exc:
            raise ProfileStoreError(f"profile {key.value} has no source file") from exc


def attach_fact_to_section(
    payload: dict, fact_id: str, section: str, *, origin: str, pin: bool = False
) -> tuple[Profile, dict]:
    """Add a canonical fact to one Profile section's candidate pool.

    A canonical fact is only reachable in a CV once some Profile section offers
    it, so this is the last step of the fact lifecycle rather than a Profile
    redesign: it widens a pool and never reorders, removes, or reweights it.

    Returns the validated profile and the document to store, so what counts as
    a valid attachment is decided here and the writing happens outside.
    """
    matches = [
        spec for spec in payload["sections"] if section in {spec["name_en"], spec["name_he"]}
    ]
    if len(matches) != 1:
        available = ", ".join(spec["name_en"] for spec in payload["sections"])
        raise ProfileStoreError(
            f"section {section!r} does not identify exactly one section in {origin} "
            f"(sections: {available})"
        )
    spec = matches[0]
    if fact_id not in spec["fact_ids"]:
        spec["fact_ids"].append(fact_id)
    if pin and fact_id not in spec.setdefault("pinned_fact_ids", []):
        spec["pinned_fact_ids"].append(fact_id)
    return Profile.model_validate(payload), payload
