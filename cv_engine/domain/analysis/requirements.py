"""Requirement extraction and fact coverage, as two separate concerns.

The architecture this file exists to hold is the separation, not the regexes:

- `extract_requirements` answers "what does the employer require?". It sees the
  job text and nothing else. It never receives a `FactStore`, so it cannot let
  what the candidate happens to have decide what the employer asked for.
- `cover_requirements` answers "what canonical evidence do we actually have?".
  It sees the extracted spans and the facts, never the job text, so coverage
  cannot be re-derived from posting wording.

Profile selection answers the third question - how the evidence is presented -
and is downstream of both. Keeping the three apart is why the signatures refuse
the arguments they refuse.

Coverage is deliberately not tag-overlap alone. Tags find *candidate* evidence;
a concept-specific, typed rule decides whether that evidence is sufficient.
Otherwise posting-keyword brittleness is only traded for fact-tag brittleness.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from ...util import canonical_json, sha256_text
from ..facts import FactStore
from ..models import Coverage, FactStatus, MissingComponent, Requirement, RequirementKind


class RequirementConceptError(ValueError):
    pass


@dataclass(frozen=True)
class ConceptComponent:
    """One named part of a compositional requirement.

    A component with no satisfying facts or tags is not a modelling mistake: it
    states that nothing in canonical Knowledge can establish this part. That is
    how "sales carried out at a technology company" stays honestly missing
    instead of being satisfied by finding a sales fact and a technology fact
    separately.
    """

    component_id: str
    label: str
    satisfied_by_fact_ids: frozenset[str] = frozenset()
    satisfied_by_tags: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RequirementConcept:
    concept: str
    label: str
    kind: RequirementKind
    patterns: tuple[re.Pattern[str], ...]
    components: tuple[ConceptComponent, ...] = ()
    satisfied_by_fact_ids: frozenset[str] = frozenset()
    satisfied_by_tags: frozenset[str] = frozenset()
    boundary_fact_ids: frozenset[str] = frozenset()
    candidate_fact_ids: frozenset[str] = frozenset()
    candidate_tags: frozenset[str] = frozenset()
    scale: str = ""
    demand_terms: dict[str, tuple[str, ...]] = field(default_factory=dict)
    demand_pattern: re.Pattern[str] | None = None
    value_fact_ids: tuple[str, ...] = ()
    value_source: str = ""


class RequirementConceptStore:
    """The requirement vocabulary and its typed coverage rules.

    Versioned like every other Knowledge dependency so that changing what a
    requirement means is visible as a change, rather than silently reshaping
    analyses that were already committed.
    """

    def __init__(self, payload: dict[str, Any], *, origin: str = "requirement concepts"):
        self.origin = origin
        self.policy_version = str(payload.get("policy_version", ""))
        self.extraction_version = str(payload.get("extraction_version", ""))
        if not self.extraction_version:
            raise RequirementConceptError(f"{origin}: extraction_version is required")
        self.scales: dict[str, tuple[str, ...]] = {
            name: tuple(str(value).casefold() for value in values)
            for name, values in (payload.get("scales") or {}).items()
        }
        self.block_markers = tuple(
            str(value).casefold() for value in payload.get("requirement_block_markers") or ()
        )
        self.mandatory_markers = tuple(
            str(value).casefold() for value in payload.get("mandatory_markers") or ()
        )
        self.preferred_markers = tuple(
            str(value).casefold() for value in payload.get("preferred_markers") or ()
        )
        self.requirement_cues = self._cues(payload, "requirement_cues", "soft_skill_cues")
        self.responsibility_cues = self._cues(payload, "responsibility_cues")
        self.concepts: dict[str, RequirementConcept] = {
            name: self._concept(name, body)
            for name, body in (payload.get("concepts") or {}).items()
        }
        if not self.concepts:
            raise RequirementConceptError(f"{origin}: no concepts declared")
        self.version = sha256_text(canonical_json(payload))

    @staticmethod
    def _cues(payload: dict[str, Any], *keys: str) -> tuple[str, ...]:
        """Every supported language's cues for these keys, as one set.

        Scoped per language in the file so each vocabulary stays readable and
        maintainable on its own, then unioned here rather than selected by the
        posting's detected language. Postings are routinely mixed - a Hebrew
        listing naming English tools and titles is the normal case, not the
        exception - and selecting one language's cues would make the other
        half's requirements invisible.

        Unioning is also the conservative direction: it can only find more
        requirement-bearing statements, which lowers completeness and reports
        less confidence, never more.
        """
        found: list[str] = []
        for key in keys:
            entry = payload.get(key) or {}
            values = (
                [value for language in sorted(entry) for value in entry[language] or ()]
                if isinstance(entry, dict)
                else list(entry)
            )
            found.extend(str(value).casefold() for value in values)
        return tuple(dict.fromkeys(found))

    @classmethod
    def from_payload(
        cls, payload: dict[str, Any], *, origin: str = "requirement concepts"
    ) -> RequirementConceptStore:
        return cls(payload, origin=origin)

    def _concept(self, name: str, body: dict[str, Any]) -> RequirementConcept:
        kind = body.get("kind")
        if kind not in {"threshold", "compositional", "presence"}:
            raise RequirementConceptError(
                f"{self.origin}: concept {name} has unknown kind {kind!r}"
            )
        patterns = tuple(
            re.compile(str(pattern), re.IGNORECASE) for pattern in body.get("patterns") or ()
        )
        if not patterns:
            raise RequirementConceptError(f"{self.origin}: concept {name} declares no patterns")
        scale = str(body.get("scale", ""))
        if kind == "threshold" and not scale:
            raise RequirementConceptError(f"{self.origin}: threshold concept {name} needs a scale")
        if scale and scale != "years" and scale not in self.scales:
            raise RequirementConceptError(
                f"{self.origin}: concept {name} names unknown scale {scale!r}"
            )
        if kind == "compositional" and not body.get("components"):
            raise RequirementConceptError(
                f"{self.origin}: compositional concept {name} declares no components"
            )
        demand = body.get("demand_pattern")
        return RequirementConcept(
            concept=name,
            label=str(body.get("label", name)),
            kind=kind,
            patterns=patterns,
            components=tuple(
                ConceptComponent(
                    component_id=str(item["component_id"]),
                    label=str(item.get("label", item["component_id"])),
                    satisfied_by_fact_ids=frozenset(item.get("satisfied_by_fact_ids") or ()),
                    satisfied_by_tags=frozenset(item.get("satisfied_by_tags") or ()),
                )
                for item in body.get("components") or ()
            ),
            satisfied_by_fact_ids=frozenset(body.get("satisfied_by_fact_ids") or ()),
            satisfied_by_tags=frozenset(body.get("satisfied_by_tags") or ()),
            boundary_fact_ids=frozenset(body.get("boundary_fact_ids") or ()),
            candidate_fact_ids=frozenset(body.get("candidate_fact_ids") or ()),
            candidate_tags=frozenset(body.get("candidate_tags") or ()),
            scale=scale,
            demand_terms={
                str(level): tuple(str(term).casefold() for term in terms)
                for level, terms in (body.get("demand_terms") or {}).items()
            },
            demand_pattern=re.compile(str(demand), re.IGNORECASE) if demand else None,
            value_fact_ids=tuple(body.get("value_fact_ids") or ()),
            value_source=str(body.get("value_source", "")),
        )


# --------------------------------------------------------------------------
# Extraction: what does the employer require?
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ExtractedRequirement:
    """One requirement span, before any fact is consulted.

    `span` is the verbatim posting text. `identity_span` is the same text under
    the conservative normalization the ID is built from.
    """

    requirement_id: str
    concept: str
    kind: RequirementKind
    span: str
    identity_span: str
    ordinal: int
    mandatory: bool
    demanded: str | None


_WHITESPACE = re.compile(r"\s+")
_SENTENCE = re.compile(r"[.;\n]")
_ASIDE = re.compile(r"\([^)]*\)")


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


def _line_around(text: str, start: int) -> str:
    left = text.rfind("\n", 0, start) + 1
    right = text.find("\n", start)
    return text[left : right if right != -1 else len(text)]


def _in_requirement_block(lowered: str, start: int, markers: tuple[str, ...]) -> bool:
    return any(
        position != -1 and position < start
        for marker in markers
        for position in (lowered.find(marker),)
    )


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
    """Find what the posting requires. Deliberately given no `FactStore`."""
    lowered = text.casefold()
    seen: dict[str, int] = {}
    found: list[ExtractedRequirement] = []
    for concept in concepts.concepts.values():
        for pattern in concept.patterns:
            for match in pattern.finditer(text):
                span = match.group(0)
                identity = normalize_span(span)
                if not identity:
                    continue
                demanded = _demanded_level(concept, span)
                # A posting restating one requirement in different words
                # ("full sales cycle", "lead to close", "prospecting to
                # close") states one requirement, not five. Distinctness is
                # per concept, except for thresholds, where a different
                # demanded value is a genuinely different requirement.
                if any(
                    item.concept == concept.concept and item.demanded == demanded for item in found
                ):
                    continue
                ordinal = seen.get(identity, 0)
                seen[identity] = ordinal + 1
                clause = _clause_around(text, match.start(), match.end()).casefold()
                line = _line_around(text, match.start()).casefold()
                preferred = any(marker in clause for marker in concepts.preferred_markers)
                mandatory_marked = any(marker in line for marker in concepts.mandatory_markers)
                in_block = _in_requirement_block(lowered, match.start(), concepts.block_markers)
                # The clause wins over the line. "(ideally European market)"
                # inside a bullet ending "(must)" makes the European market
                # preferred and leaves the rest of the bullet mandatory, which
                # is what the posting actually says.
                mandatory = (not preferred) and (mandatory_marked or in_block)
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
                        span=_WHITESPACE.sub(" ", span).strip(),
                        identity_span=identity,
                        ordinal=ordinal,
                        mandatory=mandatory,
                        demanded=demanded,
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


#: A line that ends in a colon or a question mark announces something rather
#: than stating it. "What Will Make You Stand Out?" is a heading, not a
#: requirement, and counting it made the denominator dishonest.
_ANNOUNCEMENT = re.compile(r"[:?]\s*$")

#: Below this a line is a fragment, a bullet glyph, or a label.
_MIN_STATEMENT = 12

StatementKind = Literal["requirement", "responsibility"]
ExtractionState = Literal["parsed", "partial", "unparsed", "absent"]


@dataclass(frozen=True)
class StatementLine:
    """One line of the posting that states something, and which kind.

    The distinction is load-bearing. A requirement is a candidate
    qualification; a responsibility is what the role does. Only requirements
    enter the completeness denominator, so a posting with a long
    responsibilities section cannot look better understood for having one.
    """

    start: int
    end: int
    text: str
    kind: StatementKind


def has_requirement_structure(text: str, concepts: RequirementConceptStore) -> bool:
    """Whether the posting *formats* its requirements as a block.

    A strengthening signal only. Its absence never means there is nothing to
    extract - plenty of postings state their requirements in prose - so it must
    not decide whether extraction succeeded.
    """
    lowered = text.casefold()
    return any(marker in lowered for marker in concepts.block_markers) or any(
        marker in lowered for marker in concepts.mandatory_markers
    )


def _statements(text: str) -> list[tuple[int, int, str]]:
    """Join wrapped lines into whole statements, with their offsets.

    A requirement that wraps across two lines is one requirement. Counting the
    continuation separately inflated the denominator and made a posting look
    less understood purely for how its text was hard-wrapped.

    A statement ends at terminal punctuation or a blank line; anything else is
    a continuation of the statement above it.
    """
    out: list[tuple[int, int, str]] = []
    parts: list[str] = []
    begin: int | None = None
    offset = 0
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            if parts and begin is not None:
                out.append((begin, offset, " ".join(parts)))
            parts, begin = [], None
            offset += len(line) + 1
            continue
        if begin is None:
            begin = offset
        parts.append(stripped)
        if stripped.endswith((".", "!", "?", ":")):
            out.append((begin, offset + len(line), " ".join(parts)))
            parts, begin = [], None
        offset += len(line) + 1
    if parts and begin is not None:
        out.append((begin, offset, " ".join(parts)))
    return out


def statement_lines(text: str, concepts: RequirementConceptStore) -> list[StatementLine]:
    """Every line that states a qualification or a responsibility.

    Cue-driven and explicit. There is deliberately no "this sentence has many
    adjectives, so it must be a requirement" heuristic: missing a rare soft
    skill costs a little denominator, whereas promoting marketing copy into a
    requirement would make the metric lie in the flattering direction.

    A responsibility cue alone is never enough to make a line a requirement.
    "You will manage the full sales cycle" describes the job, not the
    candidate; it is kept as a responsibility so the signal is not lost.
    """
    found: list[StatementLine] = []
    for start, end, statement in _statements(text):
        lowered = statement.casefold()
        if len(statement) < _MIN_STATEMENT or _ANNOUNCEMENT.search(statement):
            continue
        if any(cue in lowered for cue in concepts.requirement_cues):
            kind: StatementKind = "requirement"
        elif any(cue in lowered for cue in concepts.responsibility_cues):
            kind = "responsibility"
        else:
            continue
        found.append(StatementLine(start=start, end=end, text=statement, kind=kind))
    return found


def requirement_lines(text: str, concepts: RequirementConceptStore) -> list[StatementLine]:
    """The requirement-bearing lines alone - the completeness denominator."""
    return [line for line in statement_lines(text, concepts) if line.kind == "requirement"]


def _understood(
    lines: list[StatementLine], extracted: list[ExtractedRequirement], text: str
) -> int:
    positions = [(text.find(item.span), item.span) for item in extracted]
    return sum(
        1
        for line in lines
        if any(at != -1 and line.start <= at < line.end for at, _ in positions)
    )


def extraction_completeness(
    text: str,
    extracted: list[ExtractedRequirement],
    concepts: RequirementConceptStore,
) -> float | None:
    """How much of what the employer *required* the extractor read.

    `None` means the question does not apply: the posting states no
    requirements at all, so there is nothing to have missed. That is different
    from 0.0, which means requirements were stated and none were read.

    Deliberately not a function of `len(extracted)` - a short posting whose two
    requirements are both understood is fully understood.
    """
    lines = requirement_lines(text, concepts)
    if not lines:
        return None
    return _understood(lines, extracted, text) / len(lines)


def concept_classification_completeness(extracted: list[ExtractedRequirement]) -> float:
    """How much of what was read the vocabulary could classify.

    Separate from `extraction_completeness` so a confidence drop is
    attributable: reading little is a different failure from reading plenty and
    understanding none of it.
    """
    if not extracted:
        return 1.0
    return sum(1 for item in extracted if item.concept) / len(extracted)


def extraction_state(
    text: str,
    extracted: list[ExtractedRequirement],
    concepts: RequirementConceptStore,
) -> ExtractionState:
    """Which of the four states this posting's extraction landed in."""
    completeness = extraction_completeness(text, extracted, concepts)
    if completeness is None:
        return "absent"
    if completeness == 0.0:
        return "unparsed"
    return "parsed" if completeness == 1.0 else "partial"


def extraction_failed(
    text: str,
    extracted: list[ExtractedRequirement],
    concepts: RequirementConceptStore,
    *,
    understood_elsewhere: bool = False,
) -> bool:
    """Requirements were stated in some form, and none of them were read.

    Keyed on requirement-bearing language rather than on section formatting. A
    posting that states its requirements in prose and is understood not at all
    is exactly as failed as one with a `Requirements:` block, and scoring it as
    a success was a false green.

    `understood_elsewhere` is the deterministic gap rules having recognised a
    requirement the concept vocabulary does not model yet. That is still the
    engine reading a requirement, so it is not a failed extraction - only an
    incompletely modelled one. Without this, every posting whose requirements
    only the legacy rules understand would be declared unreadable.
    """
    if understood_elsewhere:
        return False
    return extraction_state(text, extracted, concepts) == "unparsed"


def extraction_confidence(
    text: str,
    extracted: list[ExtractedRequirement],
    concepts: RequirementConceptStore,
    *,
    understood_elsewhere: bool = False,
) -> float:
    """The two completeness measures, combined into one reportable score.

    `understood_elsewhere` earns the coverage floor and no more: the legacy gap
    rules read a requirement, which is worth the credit the floor represents,
    but the requirement model itself covered none of the posting and the score
    should keep saying so.
    """
    completeness = extraction_completeness(text, extracted, concepts)
    classified = concept_classification_completeness(extracted)
    if completeness is None:
        return round(classified, 4)
    if completeness == 0.0:
        # The floor is credit for having read something. Nothing was read by
        # the concept vocabulary, so it is granted only when the rules read
        # something instead; otherwise a failed extraction would keep a
        # respectable-looking score.
        return round(_COVERAGE_FLOOR * classified, 4) if understood_elsewhere else 0.0
    return round((_COVERAGE_FLOOR + (1.0 - _COVERAGE_FLOOR) * completeness) * classified, 4)


#: What reading even one stated requirement is worth. A posting whose
#: requirements are half read is not half-confidence: something real was
#: understood. The floor keeps the product from collapsing on partial coverage
#: while still separating it from full coverage.
_COVERAGE_FLOOR = 0.4


# --------------------------------------------------------------------------
# Coverage: what canonical evidence do we have?
# --------------------------------------------------------------------------


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
                        MissingComponent(component_id=component.component_id, label=component.label)
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
