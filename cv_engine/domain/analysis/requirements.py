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

Both questions are asked of one segmentation of the posting rather than of the
raw text: `_segments` reads it once into typed spans that know their section
and carry their offsets, and extraction and the completeness denominator are
two views of that same reading.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal, cast

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
        # A store with no requirement cues reads every posting as requiring
        # nothing - `absent`, the flattering answer, with full confidence. That
        # is a configuration error rather than a finding, so it is refused here
        # instead of being reported as a result.
        if not self.requirement_cues:
            raise RequirementConceptError(f"{origin}: no requirement cues declared")
        self.responsibility_cues = self._cues(payload, "responsibility_cues")
        # Which section a *bare* heading opens, keyed on the heading itself.
        # A line with no colon carries no syntactic evidence that it announces
        # anything, so it must match a configured marker outright rather than
        # merely contain one - otherwise "SaaS experience preferred" would be
        # read as a heading and the requirement in it would disappear.
        # Later entries win, so the precedence is the same as `_section_of`.
        self.heading_sections: dict[str, str] = {
            key: section
            for markers, section in (
                (self.responsibility_cues, "responsibilities"),
                (self.mandatory_markers, "requirements"),
                (self.block_markers, "requirements"),
                (self.preferred_markers, "preferred"),
            )
            for marker in markers
            for key in (heading_key(marker),)
            if key
        }
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
# Segmentation: one reading of the posting, before anything is asked of it
# --------------------------------------------------------------------------
#
# The posting is read once into typed spans that carry their own offsets, and
# every later question is asked of those spans rather than of the raw text.
# Three defects came from asking the text directly, and they were one layer
# missing three ways:
#
# - which section a statement sits in decides what is required by default, so
#   a `Responsibilities` heading closes the requirement block instead of every
#   later match inheriting the `Requirements:` heading above it;
# - a statement is one statement whether or not the posting punctuates its
#   bullets, so a list of unpunctuated items is a list rather than one long
#   sentence that any single concept can make look understood;
# - a concept reports where it matched, so coverage is decided by offset
#   overlap instead of by searching the raw text for a span that whitespace
#   normalization has already changed - a search that returned -1 for every
#   requirement the posting happened to wrap across a line.


SectionKind = Literal["requirements", "preferred", "responsibilities", "other"]
StatementKind = Literal["requirement", "responsibility"]
ExtractionState = Literal["parsed", "partial", "unparsed", "absent"]

#: Decoration a heading may be wrapped in. Stripped from both the line and the
#: configured marker before they are compared, so `**Requirements**`,
#: `Requirements:` and `Requirements` are one heading.
_HEADING_DECORATION = " \t*_#~`-\u2013\u2014\u2022\u2023\u25aa\u25e6:?.!,"

#: Below this a line is a fragment, a bullet glyph, or a label.
_MIN_STATEMENT = 12

#: A list glyph or an enumerator. It opens an item and is never part of it.
#: `\d{1,2}[.)]` deliberately does not match `1+`, which opens "1+ years of
#: sales closing experience" - an enumerator is punctuated, a quantity is not.
_BULLET = re.compile(r"^\s*(?:[-–—*•·‣▪◦]|\(?\d{1,2}[.)])\s+")

#: What ends a statement rather than wrapping it.
_TERMINAL = (".", "!", "?", ":", ";")

_WHITESPACE = re.compile(r"\s+")
_SENTENCE = re.compile(r"[.;\n]")
_ASIDE = re.compile(r"\([^)]*\)")


@dataclass(frozen=True)
class StatementLine:
    """One statement the posting makes, which kind, and where it sits.

    The kind is load-bearing. A requirement is a candidate qualification; a
    responsibility is what the role does. Only requirements enter the
    completeness denominator, so a posting with a long responsibilities
    section cannot look better understood for having one.
    """

    start: int
    end: int
    text: str
    kind: StatementKind
    section: SectionKind


@dataclass(frozen=True)
class _Span:
    """A statement together with the map back to where its text came from.

    `offsets[i]` is where `text[i]` sits in the posting. Whitespace collapsing
    happens here, once, so a match found in `text` can still say where in the
    posting it was found. `text.find(span)` could not: the span it was handed
    had already been normalized and no longer occurred in the posting, and the
    failed search was read as "this requirement was never mentioned".
    """

    start: int
    end: int
    text: str
    offsets: tuple[int, ...]
    section: SectionKind
    list_item: bool
    kind: StatementKind | None

    def origin(self, start: int, end: int) -> tuple[int, int]:
        """Where a match inside this statement sits in the posting."""
        return self.offsets[start], self.offsets[end - 1] + 1


def _collapse(text: str, base: int) -> tuple[str, tuple[int, ...]]:
    """One statement's text with whitespace runs collapsed, and its offsets.

    A collapsed run maps to where the run began, so a match that crosses the
    line break a posting wrapped its requirement at still resolves to a span
    of the original text.
    """
    body: list[str] = []
    offsets: list[int] = []
    index = 0
    while index < len(text):
        if text[index].isspace():
            run = index
            while run < len(text) and text[run].isspace():
                run += 1
            if body:
                body.append(" ")
                offsets.append(base + index)
            index = run
            continue
        body.append(text[index])
        offsets.append(base + index)
        index += 1
    while body and body[-1] == " ":
        body.pop()
        offsets.pop()
    return "".join(body), tuple(offsets)


def heading_key(text: str) -> str:
    """A heading reduced to what it says, for comparison against a marker."""
    return _WHITESPACE.sub(" ", text.strip(_HEADING_DECORATION)).strip().casefold()


def _heading_section(
    line: str, stripped: str, concepts: RequirementConceptStore
) -> SectionKind | None:
    """Which section this line opens, or `None` if it states something instead.

    A colon announces: the line is a heading whatever it says, and the loose
    containment match decides which kind.

    Without a colon there is no such evidence, so the line must *be* a
    configured marker. That is what lets a bare `Responsibilities` close the
    requirement block - the common case, and the one that left every later
    bullet inheriting the `Requirements:` above it - without letting a bullet
    that merely ends in "preferred" swallow itself as a heading. A glyph marks
    an item rather than a heading, so a bulleted line is never one.

    A question mark alone no longer announces anything. "Do you have 3+ years
    of sales experience?" is a requirement asked as a question, and discarding
    it reported a posting that stated requirements as one that stated none.
    """
    if stripped.endswith(":"):
        return _section_of(stripped.casefold(), concepts)
    if _BULLET.match(line):
        return None
    section = concepts.heading_sections.get(heading_key(stripped))
    return cast("SectionKind | None", section)


def _section_of(heading: str, concepts: RequirementConceptStore) -> SectionKind:
    """Which block this heading opens.

    Preferred is tested first: "Preferred requirements:" names both
    vocabularies and opens a preferred block, not a mandatory one.

    A heading matching nothing opens `other`, which is how `Benefits:` closes
    the requirement block above it. Leaving the block open to the end of the
    posting is what made a responsibility mandatory for having been printed
    below a `Requirements:` heading.
    """
    if any(marker in heading for marker in concepts.preferred_markers):
        return "preferred"
    if any(marker in heading for marker in concepts.block_markers):
        return "requirements"
    if any(marker in heading for marker in concepts.mandatory_markers):
        return "requirements"
    if any(cue in heading for cue in concepts.responsibility_cues):
        return "responsibilities"
    return "other"


def _statement_kind(
    text: str,
    section: SectionKind,
    list_item: bool,
    concepts: RequirementConceptStore,
) -> StatementKind | None:
    """Whether this statement asks something of the candidate.

    Cue-driven and explicit. There is deliberately no "this sentence has many
    adjectives, so it must be a requirement" heuristic: missing a rare soft
    skill costs a little denominator, whereas promoting marketing copy into a
    requirement would make the metric lie in the flattering direction.

    A list item under a requirements heading is a requirement even with no cue
    word in it, because the heading already said so. Prose under that heading
    is not - a posting's closing pitch is printed below its requirement
    bullets and is still a pitch.

    A cue outranks the section, in both directions. "You must have five years"
    under `Responsibilities` is a requirement that happens to be misfiled; a
    responsibility cue alone is never enough to make a line a requirement,
    since "You will manage the full sales cycle" describes the job rather than
    the candidate.
    """
    lowered = text.casefold()
    if any(cue in lowered for cue in concepts.requirement_cues):
        return "requirement"
    if list_item and section in {"requirements", "preferred"}:
        return "requirement"
    if any(cue in lowered for cue in concepts.responsibility_cues):
        return "responsibility"
    if list_item and section == "responsibilities":
        return "responsibility"
    return None


def _segments(text: str, concepts: RequirementConceptStore) -> list[_Span]:
    """Read the posting once into typed, offset-carrying statements."""
    found: list[_Span] = []
    section: SectionKind = "other"
    buffered: list[tuple[int, int]] = []
    list_item = False
    open_ended = False

    def flush() -> None:
        nonlocal buffered
        if not buffered:
            return
        start, end = buffered[0][0], buffered[-1][1]
        buffered = []
        body, offsets = _collapse(text[start:end], start)
        if len(body) < _MIN_STATEMENT:
            return
        found.append(
            _Span(
                start=start,
                end=end,
                text=body,
                offsets=offsets,
                section=section,
                list_item=list_item,
                kind=_statement_kind(body, section, list_item, concepts),
            )
        )

    offset = 0
    for line in text.split("\n"):
        start = offset
        offset += len(line) + 1
        stripped = line.strip()
        if not stripped:
            flush()
            open_ended = False
            continue
        heading = _heading_section(line, stripped, concepts)
        if heading is not None:
            # The statement above closes under the heading it was written
            # under, so `flush` runs before the section changes.
            flush()
            section = heading
            open_ended = False
            continue
        bullet = _BULLET.match(line)
        lead = bullet.end() if bullet else len(line) - len(line.lstrip())
        content = (start + lead, start + len(line.rstrip()))
        if content[0] >= content[1]:
            continue
        # A line continues the statement above it only on positive evidence:
        # that statement stopped mid-sentence and this line resumes in lower
        # case. Everything else opens a statement, including every line of a
        # script that has no case, such as Hebrew.
        #
        # The bias is deliberate. Splitting a wrapped statement costs
        # denominator and reads as less understood; merging two bullets hides
        # one requirement inside a statement that another requirement already
        # accounted for, and reads as more understood than the posting was.
        continues = bool(buffered) and bullet is None and open_ended and text[content[0]].islower()
        if not continues:
            flush()
            list_item = bullet is not None
        buffered.append(content)
        open_ended = not stripped.endswith(_TERMINAL)
    flush()
    return found


def statement_lines(text: str, concepts: RequirementConceptStore) -> list[StatementLine]:
    """Every statement that states a qualification or a responsibility."""
    return [
        StatementLine(
            start=span.start,
            end=span.end,
            text=span.text,
            kind=span.kind,
            section=span.section,
        )
        for span in _segments(text, concepts)
        if span.kind is not None
    ]


def requirement_lines(text: str, concepts: RequirementConceptStore) -> list[StatementLine]:
    """The requirement-bearing statements alone - the completeness denominator."""
    return [line for line in statement_lines(text, concepts) if line.kind == "requirement"]


# --------------------------------------------------------------------------
# Extraction: what does the employer require?
# --------------------------------------------------------------------------


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


def _understood(lines: list[StatementLine], extracted: list[ExtractedRequirement]) -> int:
    """How many stated requirements had something read inside them.

    Offset overlap, not `text.find`. The extracted span carries normalized
    text that a posting wrapping the requirement across a line no longer
    contains, so the search failed and the statement was counted unread.
    """
    return sum(
        1
        for line in lines
        if any(item.start < line.end and line.start < item.end for item in extracted)
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
    return _understood(lines, extracted) / len(lines)


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
