"""Extract what the employer requires, without consulting candidate facts."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ....util import canonical_json, sha256_text
from ...models import RequirementKind
from .concepts import RequirementConcept, RequirementConceptStore
from .segmentation import _segments

_WHITESPACE = re.compile(r"\s+")
_SENTENCE = re.compile(r"[.;\n]")
_ASIDE = re.compile(r"\([^)]*\)")


@dataclass(frozen=True)
class ExtractedRequirement:
    """One requirement span, before any fact is consulted.

    `span` is the posting text under whitespace collapsing; `identity_span` is
    the same text under the conservative normalization the ID is built from.
    `start` and `end` are where the match sits in the posting, which is how
    coverage of a statement is decided without searching for the span again.
    """

    requirement_id: str
    concept: str
    kind: RequirementKind
    span: str
    identity_span: str
    ordinal: int
    mandatory: bool
    demanded: str | None
    start: int
    end: int


def normalize_span(text: str) -> str:
    """The conservative normalization requirement identity is built from.

    Whitespace and case only. Qualifiers - `native`, `3+ years`, `European`,
    `preferred`, `must` - are part of what a requirement *is* and are never
    stripped, so two requirements that differ only by a qualifier keep separate
    identities.
    """
    return _WHITESPACE.sub(" ", text).strip().casefold()


def _clause_around(text: str, start: int, end: int) -> str:
    """The text whose qualifiers govern this match.

    A parenthetical aside qualifies what is inside it, not what surrounds it,
    and the direction matters in both senses:

    - A match *inside* an aside is governed by that aside. "(ideally European
      market)" makes the European market preferred even though the bullet it
      sits in ends "(must)".
    - A match that *contains* an aside is not governed by it. The span "sales
      closing experience ... (ideally European market) at a technology company"
      swallows that aside, and must not inherit its "ideally" - the technology
      company is required, only the European market is preferred.

    So: an enclosed match takes its aside as the clause; otherwise the clause
    is the sentence with every aside removed.
    """
    for aside in _ASIDE.finditer(text):
        if aside.start() < start and end <= aside.end():
            return aside.group(0)
    left = max((match.end() for match in _SENTENCE.finditer(text, 0, start)), default=0)
    right_match = _SENTENCE.search(text, end)
    right = right_match.start() if right_match else len(text)
    return _ASIDE.sub(" ", text[left:right])


def _demanded_level(concept: RequirementConcept, span: str) -> str | None:
    lowered = span.casefold()
    if concept.demand_pattern is not None:
        match = concept.demand_pattern.search(span)
        return match.group(1) if match else None
    for level, terms in concept.demand_terms.items():
        if any(term in lowered for term in terms):
            return level
    return None


def extract_requirements(
    text: str,
    *,
    normalized_hash: str,
    concepts: RequirementConceptStore,
) -> list[ExtractedRequirement]:
    """Find what the posting requires. Deliberately given no `FactStore`.

    Concepts run inside requirement statements and nowhere else. A concept
    matching the day-to-day paragraph has matched a description of the job,
    not a demand on the candidate; reading it as a requirement is how "Own the
    full sales cycle" became a mandatory requirement under a
    `Responsibilities` heading.
    """
    seen: dict[str, int] = {}
    found: list[ExtractedRequirement] = []
    for span in _segments(text, concepts):
        if span.kind != "requirement":
            continue
        statement = span.text.casefold()
        # The statement is the unit a mandatory marker governs. It was the
        # physical line, which meant a marker on one wrapped half did not
        # reach the other, and a marker anywhere in a run of unpunctuated
        # bullets reached all of them.
        marked = any(marker in statement for marker in concepts.mandatory_markers)
        for concept in concepts.concepts.values():
            for pattern in concept.patterns:
                for match in pattern.finditer(span.text):
                    matched = match.group(0)
                    identity = normalize_span(matched)
                    if not identity:
                        continue
                    demanded = _demanded_level(concept, matched)
                    # A posting restating one requirement in different words
                    # ("full sales cycle", "lead to close", "prospecting to
                    # close") states one requirement, not five. Distinctness
                    # is per concept, except for thresholds, where a different
                    # demanded value is a genuinely different requirement.
                    if any(
                        item.concept == concept.concept and item.demanded == demanded
                        for item in found
                    ):
                        continue
                    ordinal = seen.get(identity, 0)
                    seen[identity] = ordinal + 1
                    clause = _clause_around(span.text, match.start(), match.end()).casefold()
                    preferred = any(marker in clause for marker in concepts.preferred_markers)
                    start, end = span.origin(match.start(), match.end())
                    # The clause wins over the statement, and the statement
                    # over the section. "(ideally European market)" inside a
                    # bullet ending "(must)" makes the European market
                    # preferred and leaves the rest of the bullet mandatory,
                    # which is what the posting actually says.
                    mandatory = (not preferred) and (marked or span.section == "requirements")
                    found.append(
                        ExtractedRequirement(
                            requirement_id=requirement_id(
                                normalized_hash=normalized_hash,
                                extraction_version=concepts.extraction_version,
                                identity_span=identity,
                                ordinal=ordinal,
                            ),
                            concept=concept.concept,
                            kind=concept.kind,
                            span=_WHITESPACE.sub(" ", matched).strip(),
                            identity_span=identity,
                            ordinal=ordinal,
                            mandatory=mandatory,
                            demanded=demanded,
                            start=start,
                            end=end,
                        )
                    )
    return sorted(found, key=lambda item: (item.concept, item.ordinal))


def requirement_id(
    *,
    normalized_hash: str,
    extraction_version: str,
    identity_span: str,
    ordinal: int,
) -> str:
    """Identity from the immutable analysis input, not a global taxonomy.

    Keyed on the snapshot's normalized hash so the same posting text always
    yields the same IDs and two different postings never share one, and on the
    extractor version so a semantics change does not silently inherit an
    acceptance recorded against the old meaning.
    """
    return sha256_text(
        canonical_json(
            {
                "snapshot": normalized_hash,
                "extractor": extraction_version,
                "span": identity_span,
                "ordinal": ordinal,
            }
        )
    )[:16]
