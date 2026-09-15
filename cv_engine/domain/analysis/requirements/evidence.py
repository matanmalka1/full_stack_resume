"""Decide coverage from the evidence an AI extraction proposed (D5).

Under D5 the provider is the semantic authority for *which canonical facts
answer a requirement*. It is not the authority for whether those facts exist,
whether they may be used, or whether a number actually clears a threshold.
This module is that split, written out:

- The provider proposes a coverage reading and names the canonical facts it
  read as evidence for it.
- Every named fact is checked here against the `FactStore`: it must exist and
  be canonical. A fact that is neither is invalid output, not a weaker
  reading - naming a fact that is not there is the failure mode D5's
  "provider self-reports do not prove" clause exists for.
- A positive reading (`matched`/`partial`) with nothing inspectable behind it
  is refused for the same reason. D5: "Positive coverage must retain
  inspectable evidence."
- A threshold is recomputed here from the evidence facts' own structured
  fields and never taken from the provider. Arithmetic the provider performed
  on a value it also supplied proves nothing; a held value that cannot be
  traced to canonical structured evidence leaves the comparison
  `undetermined`, which is explicit and reviewable rather than silently
  matched or unsupported.
- A canonical boundary fact still caps `matched` to `partial`. Its
  applicability is decided deterministically, from the concept vocabulary's
  own patterns against the verified quote - never from a provider relation or
  tag, which D5 names specifically. This is the one thing the vocabulary still
  decides, and it can only ever *lower* coverage, so a vocabulary that does
  not model a posting cannot manufacture a false positive from it.

What the vocabulary no longer does is decide coverage. `concept_for_quote`
gating `matched`/`unsupported` meant a real requirement the six configured
concepts did not model returned `undetermined` however well the provider read
it - the closed-vocabulary collapse product-spec §2 "Semantic analysis
authority" removes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

from ...contracts.analysis import Coverage, MissingComponent
from ...contracts.knowledge import FactStatus
from ...contracts.providers import ProposedEvidence
from ...facts import FactStore
from .concepts import RequirementConceptStore

_DATE_SPAN = re.compile(r"(\d{4})-(\d{2})\s*/\s*(\d{4})-(\d{2})")


def years_from_effective_dates(value: str | None) -> float | None:
    if not value:
        return None
    match = _DATE_SPAN.search(value)
    if not match:
        return None
    start = date(int(match.group(1)), int(match.group(2)), 1)
    end = date(int(match.group(3)), int(match.group(4)), 1)
    return (end - start).days / 365.25


#: What a provider may propose. The same vocabulary `Coverage` uses, because
#: the provider is reading the same question - it just does not get the last
#: word on the answer.
ProposedCoverage = Literal["matched", "partial", "unsupported", "undetermined"]


class InvalidRequirementEvidence(ValueError):
    """The proposal named evidence that cannot be verified, or claimed coverage with none."""


@dataclass(frozen=True)
class CoverageDecision:
    """What the gates decided, and what the record shows for it."""

    coverage: Coverage
    supporting_fact_ids: list[str]
    boundary_fact_ids: list[str]
    missing_components: list[MissingComponent]


def verify_evidence(
    evidence: list[ProposedEvidence],
    facts: FactStore,
    *,
    where: str,
) -> list[str]:
    """The canonical fact ids behind a proposed reading, or a refusal.

    Deliberately strict in both directions. An unknown fact id is a fabricated
    citation; a non-canonical one is a fact the engine is not allowed to
    present, and accepting it would let a pending or superseded fact carry a
    requirement into a CV. Either rejects the whole proposal rather than
    weakening this one requirement, which is the rule the source and
    interpretation gates already follow: this is a Proposal, not a partially
    applied edit.

    Duplicates collapse. A provider citing one fact twice is citing it once.
    """
    verified: list[str] = []
    for item in evidence:
        fact = facts.facts.get(item.fact_id)
        if fact is None:
            raise InvalidRequirementEvidence(
                f"{where}: evidence names unknown fact {item.fact_id!r}"
            )
        if fact.status is not FactStatus.CANONICAL:
            raise InvalidRequirementEvidence(
                f"{where}: evidence names non-canonical fact {item.fact_id!r} "
                f"(status {fact.status.value})"
            )
        verified.append(item.fact_id)
    return sorted(dict.fromkeys(verified))


def boundary_facts_for_quote(
    quote: str, concepts: RequirementConceptStore, facts: FactStore
) -> list[str]:
    """Canonical boundary facts that apply to this requirement's own quote.

    Applicability is a deterministic pattern match on the verified quote, and
    every concept whose patterns match contributes - not only a unique match.
    `concept_for_quote` refuses an ambiguous match because picking one of two
    readings would misclassify coverage; here the direction is the opposite,
    because a boundary can only cap `matched` to `partial`. Taking every
    matching concept's boundary is the conservative reading, and refusing on
    ambiguity would drop a real limit on a technicality.
    """
    found = {
        fact_id
        for concept in concepts.concepts.values()
        if any(pattern.search(quote) for pattern in concept.patterns)
        for fact_id in concept.boundary_fact_ids
    }
    return sorted(
        fact_id
        for fact_id in found
        if fact_id in facts.facts and facts.facts[fact_id].status is FactStatus.CANONICAL
    )


def threshold_coverage_from_evidence(
    demanded: str,
    fact_ids: list[str],
    facts: FactStore,
    scales: dict[str, tuple[str, ...]],
) -> Coverage:
    """Whether the evidence facts themselves clear the demanded level.

    Two traceable forms, and nothing else:

    - A numeric demand is compared against the longest span any evidence fact's
      `effective_dates` covers. That field is structured canonical Knowledge,
      so the comparison is one the engine performed rather than one it was
      told the answer to.
    - A named level is compared against the configured scale it belongs to,
      read out of the evidence facts' `meaning`. `config/requirements.json`
      still owns the ordering of such a scale - "fluent" outranking
      "conversational" is a fact about the scale, not about a posting - which
      is why the `scales` block survives D5 while the concept vocabulary's
      coverage authority does not.

    Anything else is `undetermined`: a demand the engine cannot compute against
    is not a demand the candidate failed. Reporting it as `unsupported` would
    tell the candidate they lack something nobody measured.
    """
    if not fact_ids:
        return "unsupported"
    canonical = [
        facts.facts[fact_id]
        for fact_id in fact_ids
        if fact_id in facts.facts and facts.facts[fact_id].status is FactStatus.CANONICAL
    ]
    try:
        demanded_years = float(demanded)
    except ValueError:
        demanded_years = None
    if demanded_years is not None:
        held = max(
            (
                years
                for fact in canonical
                if (years := years_from_effective_dates(fact.effective_dates)) is not None
            ),
            default=None,
        )
        if held is None:
            return "undetermined"
        return "matched" if held >= demanded_years else "unsupported"
    level = demanded.casefold()
    scale = next((values for values in scales.values() if level in values), None)
    if scale is None:
        return "undetermined"
    wanted = scale.index(level)
    held_level = max(
        (
            index
            for fact in canonical
            for index, name in enumerate(scale)
            if name in fact.meaning.casefold()
        ),
        default=None,
    )
    if held_level is None:
        return "undetermined"
    return "matched" if held_level >= wanted else "unsupported"


#: How positive a verdict is, for the one comparison this module makes.
#: `undetermined` is deliberately absent: it is not a point on this scale but a
#: statement that the scale could not be applied, and it stays explicit rather
#: than being ranked against readings that were actually reached.
_STRENGTH = {"unsupported": 1, "partial": 2, "matched": 3}


def _weaker(proposed: ProposedCoverage, computed: Coverage) -> Coverage:
    """The less positive of a provider's reading and the engine's own.

    Either side saying "could not tell" makes the answer that, which is what
    keeps an unresolved condition explicit and reviewable instead of being
    silently converted to matched or unsupported.
    """
    if proposed == "undetermined" or computed == "undetermined":
        return "undetermined"
    return proposed if _STRENGTH[proposed] <= _STRENGTH[computed] else computed


def decide_coverage(
    *,
    proposed: ProposedCoverage,
    evidence: list[ProposedEvidence],
    quote: str,
    label: str,
    kind: str,
    demanded: str | None,
    facts: FactStore,
    concepts: RequirementConceptStore,
    where: str,
) -> CoverageDecision:
    """One requirement's coverage: the provider's reading, under the gates.

    Order matters, and each step is a narrowing:

    1. The cited facts are verified. Anything unverifiable rejects the proposal.
    2. A positive reading with no verified evidence is rejected.
    3. A threshold is recomputed from structured evidence and the weaker of
       the two readings stands. The engine can check this one itself, so a
       reported `matched` the dates do not support becomes `unsupported`.
       It does not run the other way: a computed `matched` cannot overrule a
       provider that read the requirement as unmet, because the arithmetic
       proves the cited fact clears the number, not that the cited fact is
       the right evidence for this demand - only the provider read that.
    4. A canonical boundary fact caps `matched` to `partial`.

    No step can raise coverage above what the provider proposed. Every gate
    here narrows.
    """
    verified = verify_evidence(evidence, facts, where=where)
    if proposed in ("matched", "partial") and not verified:
        raise InvalidRequirementEvidence(
            f"{where}: coverage {proposed!r} was proposed with no canonical evidence"
        )
    boundary = boundary_facts_for_quote(quote, concepts, facts)

    if kind == "threshold":
        if demanded is None:
            raise InvalidRequirementEvidence(
                f"{where}: a threshold requirement declares no demanded value"
            )
        computed = threshold_coverage_from_evidence(demanded, verified, facts, concepts.scales)
        coverage: Coverage = _weaker(proposed, computed)
    else:
        coverage = proposed

    if boundary and coverage == "matched":
        coverage = "partial"

    missing = (
        []
        if coverage == "matched"
        else [
            MissingComponent(
                component_id="requirement",
                label=label,
                demanded=demanded,
            )
        ]
    )
    return CoverageDecision(
        coverage=coverage,
        supporting_fact_ids=verified,
        boundary_fact_ids=boundary,
        missing_components=missing,
    )
