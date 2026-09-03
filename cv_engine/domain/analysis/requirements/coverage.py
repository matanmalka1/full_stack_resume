"""Resolve extracted requirements against facts, without re-reading job text."""

from __future__ import annotations

import re
from datetime import date

from ...contracts.analysis import Coverage, MissingComponent, Requirement
from ...contracts.knowledge import FactStatus
from ...facts import FactStore
from .concepts import RequirementConcept, RequirementConceptStore
from .extraction import ExtractedRequirement

_DATE_SPAN = re.compile(r"(\d{4})-(\d{2})\s*/\s*(\d{4})-(\d{2})")


def _canonical(facts: FactStore) -> list:
    return [fact for fact in facts.facts.values() if fact.status is FactStatus.CANONICAL]


def _candidate_fact_ids(concept: RequirementConcept, facts: FactStore) -> list[str]:
    """Tag overlap finds candidate evidence. It never decides sufficiency.

    Boundary facts are excluded here and everywhere else evidence is counted. A
    boundary fact states what is *not* verified, so listing it as support would
    make a limit read as evidence for the thing it limits.
    """
    found = {
        fact.fact_id
        for fact in _canonical(facts)
        if concept.candidate_tags & set(fact.tags) or fact.fact_id in concept.candidate_fact_ids
    }
    return sorted(found - concept.boundary_fact_ids)


def _satisfied(
    fact_ids: frozenset[str],
    tags: frozenset[str],
    facts: FactStore,
    boundary_fact_ids: frozenset[str],
) -> list[str]:
    """Positive evidence only.

    A boundary fact can never satisfy a component or a presence requirement,
    however it is tagged or named, so it cannot move `unsupported -> partial`
    or `partial -> matched`.
    """
    return sorted(
        {
            fact.fact_id
            for fact in _canonical(facts)
            if fact.fact_id not in boundary_fact_ids
            and (fact.fact_id in fact_ids or (tags and tags & set(fact.tags)))
        }
    )


def _years_from_effective_dates(value: str | None) -> float | None:
    if not value:
        return None
    match = _DATE_SPAN.search(value)
    if not match:
        return None
    start = date(int(match.group(1)), int(match.group(2)), 1)
    end = date(int(match.group(3)), int(match.group(4)), 1)
    return (end - start).days / 365.25


def _value_fact(concept: RequirementConcept, fact_id: str, facts: FactStore):
    """The canonical fact carrying a threshold's held value, or None.

    A boundary fact is refused here too, so it cannot raise a held level and
    turn an unmet threshold into a met one.
    """
    if fact_id in concept.boundary_fact_ids:
        return None
    fact = facts.facts.get(fact_id)
    return fact if fact is not None and fact.status is FactStatus.CANONICAL else None


def _threshold_coverage(
    concept: RequirementConcept,
    extracted: ExtractedRequirement,
    facts: FactStore,
    scales: dict[str, tuple[str, ...]],
) -> tuple[Coverage, list[MissingComponent]]:
    """Met or not met. A threshold is never partial.

    Falling short of a demanded level is a real failure to meet the
    requirement, not half of one, even when a related canonical value exists.
    That value is still reported as supporting evidence.
    """
    if extracted.demanded is None:
        return "unsupported", [MissingComponent(component_id=concept.concept, label=concept.label)]
    held: float | None = None
    demanded_value: float | None = None
    if concept.scale == "years":
        demanded_value = float(extracted.demanded)
        for fact_id in concept.value_fact_ids:
            fact = _value_fact(concept, fact_id, facts)
            if fact is None:
                continue
            years = _years_from_effective_dates(fact.effective_dates)
            if years is not None:
                held = max(held or 0.0, years)
    else:
        levels = scales.get(concept.scale, ())
        if extracted.demanded.casefold() not in levels:
            return "unsupported", [
                MissingComponent(component_id=concept.concept, label=concept.label)
            ]
        demanded_value = float(levels.index(extracted.demanded.casefold()))
        for fact_id in concept.value_fact_ids:
            fact = _value_fact(concept, fact_id, facts)
            if fact is None:
                continue
            meaning = fact.meaning.casefold()
            for index, level in enumerate(levels):
                if level in meaning:
                    held = max(held or 0.0, float(index))
    if held is None or demanded_value is None or held < demanded_value:
        return "unsupported", [
            MissingComponent(
                component_id=concept.concept,
                label=concept.label,
                demanded=extracted.demanded,
            )
        ]
    return "matched", []


def cover_requirements(
    extracted: list[ExtractedRequirement],
    *,
    facts: FactStore,
    concepts: RequirementConceptStore,
) -> list[Requirement]:
    """Decide coverage from canonical facts. Deliberately given no job text."""
    covered: list[Requirement] = []
    for item in extracted:
        concept = concepts.concepts[item.concept]
        supporting = _candidate_fact_ids(concept, facts)
        boundary = sorted(
            fact_id
            for fact_id in concept.boundary_fact_ids
            if fact_id in facts.facts and facts.facts[fact_id].status is FactStatus.CANONICAL
        )
        missing: list[MissingComponent] = []

        if concept.kind == "threshold":
            coverage, missing = _threshold_coverage(concept, item, facts, concepts.scales)
        elif concept.kind == "compositional":
            met: list[str] = []
            for component in concept.components:
                evidence = _satisfied(
                    component.satisfied_by_fact_ids,
                    component.satisfied_by_tags,
                    facts,
                    concept.boundary_fact_ids,
                )
                if evidence:
                    met.append(component.component_id)
                else:
                    missing.append(
                        MissingComponent(
                            component_id=component.component_id,
                            label=component.label,
                        )
                    )
            coverage = "matched" if not missing else ("partial" if met else "unsupported")
        else:
            evidence = _satisfied(
                concept.satisfied_by_fact_ids,
                concept.satisfied_by_tags,
                facts,
                concept.boundary_fact_ids,
            )
            coverage = "matched" if evidence else "unsupported"
            if not evidence:
                missing = [MissingComponent(component_id=concept.concept, label=concept.label)]

        # A boundary fact is canonical Knowledge stating what is *not* verified.
        # It caps coverage: matched becomes unreachable while it stands.
        if boundary and coverage == "matched":
            coverage = "partial"

        covered.append(
            Requirement(
                requirement_id=item.requirement_id,
                text=item.span,
                kind=item.kind,
                concept=item.concept,
                mandatory=item.mandatory,
                coverage=coverage,
                supporting_fact_ids=supporting,
                boundary_fact_ids=boundary,
                missing_components=missing,
            )
        )
    return covered
