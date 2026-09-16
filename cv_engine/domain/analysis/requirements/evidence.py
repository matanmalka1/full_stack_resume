"""Which canonical boundary facts apply to a requirement.

This module used to decide coverage: it verified cited evidence, recomputed
thresholds from a fact's structured fields, and composed members. The analysis
contract no longer carries any of that, and the normalizer performs the checks
that remain. What survives is the one deterministic veto that still stands -
a canonical boundary fact is the candidate's own statement that something is
not verified, and it caps `matched` to `partial` whatever the provider read.
"""

from __future__ import annotations

from ...contracts.knowledge import FactStatus
from ...facts import FactStore
from .concepts import RequirementConceptStore


def boundary_facts_for_quote(
    quote: str, concepts: RequirementConceptStore, facts: FactStore
) -> list[str]:
    """Canonical boundary facts that apply to this requirement's own text.

    Applicability is a deterministic pattern match on the text, and every
    concept whose patterns match contributes - not only a unique match. A
    boundary can only cap `matched` to `partial`. Taking every matching
    concept's boundary is the conservative reading, and refusing on ambiguity
    would drop a real limit on a technicality.

    Only canonical boundary facts are returned, so every id stored on a
    requirement names a fact that exists and is canonical at analysis time.
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
