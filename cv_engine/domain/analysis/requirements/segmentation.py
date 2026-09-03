"""Read a posting once into typed statements shared by later analysis stages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, cast

from .concepts import RequirementConceptStore, heading_key

SectionKind = Literal["requirements", "preferred", "responsibilities", "other"]
StatementKind = Literal["requirement", "responsibility"]

#: Below this a line is a fragment, a bullet glyph, or a label.
_MIN_STATEMENT = 12

#: A list glyph or an enumerator. It opens an item and is never part of it.
#: `\d{1,2}[.)]` deliberately does not match `1+`, which opens "1+ years of
#: sales closing experience" - an enumerator is punctuated, a quantity is not.
_BULLET = re.compile(r"^\s*(?:[-–—*•·‣▪◦]|\(?\d{1,2}[.)])\s+")

#: What ends a statement rather than wrapping it.
_TERMINAL = (".", "!", "?", ":", ";")


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
