"""Deterministic writing-style findings. Advice only: none of them blocks (§11).

They read the stored claims, so canonical wording the user wrote is read like any
other line; a warning is a suggestion to reword or pick another fact, never a claim
that the line is unsupported. Rules about English phrasing (openers, first person) run
on English documents only. Line length, repeated openers, em dashes, and date formats
apply to both languages.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from .contracts.drafts import ClaimLine, DraftDocument
from .date_display import HEBREW_MONTHS, displayed_date

#: Openers that describe proximity to the work rather than the work itself.
WEAK_OPENERS: tuple[str, ...] = (
    "responsible for",
    "helped with",
    "helped to",
    "helped",
    "assisted with",
    "assisted in",
    "assisted",
    "involved in",
    "participated in",
    "worked on",
    "tasked with",
    "duties included",
    "in charge of",
)
LONG_BULLET_WORDS = 35
REPEATED_OPENER_LIMIT = 3

_WEAK_OPENER = re.compile(
    r"^\W*(?:" + "|".join(re.escape(opener) for opener in WEAK_OPENERS) + r")\b",
    re.IGNORECASE,
)
# "I" as a word but not inside "I/O"; me/my/mine/myself in lower or title case only,
# so an acronym such as "ME" is not read as a pronoun.
_FIRST_PERSON = re.compile(r"(?<![\w/.-])I(?![\w/.-])|\b[Mm](?:e|y|ine|yself)\b")
# An em dash, or two or three hyphens standing in for one.
_EM_DASH = re.compile(r"—|(?<![\w-])-{2,3}(?![\w-])|(?<=\w)-{2,3}(?=\w)")
_FIRST_WORD = re.compile(r"[^\W_][\w+#./&'-]*")

_EN_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_HE_MONTH_YEAR = re.compile(
    "(" + "|".join(sorted(HEBREW_MONTHS, key=len, reverse=True)) + r")\s+(\d{4})"
)
_DATE_FORMATS: dict[str, re.Pattern[str]] = {
    "month-name": re.compile(rf"\b{_EN_MONTH}\.?,?\s+\d{{4}}\b", re.IGNORECASE),
    "month-number": re.compile(r"(?<!\d)\d{1,2}[/.]\d{4}\b"),
    "year-month": re.compile(r"\b\d{4}[-/.]\d{1,2}(?!\d)"),
}

_PROSE_STYLES = frozenset({"paragraph", "bullet", "item"})


@dataclass(frozen=True)
class WritingFinding:
    code: str
    message: str


def _excerpt(text: str, limit: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _line(claim: ClaimLine) -> str:
    return f"claim {claim.claim_id} ({_excerpt(claim.text)!r})"


def _entries(draft: DraftDocument) -> Iterator[list[ClaimLine]]:
    """The bullets of each entry: a section's lines under one heading, or above all."""
    for section in draft.sections:
        bullets: list[ClaimLine] = []
        for claim in section.claims:
            if claim.style == "heading":
                yield bullets
                bullets = []
            elif claim.style == "bullet":
                bullets.append(claim)
        yield bullets


def _line_findings(claim: ClaimLine, english: bool) -> Iterator[WritingFinding]:
    if claim.style not in _PROSE_STYLES:
        return
    text = claim.text
    if _EM_DASH.search(text):
        yield WritingFinding("em-dash", f"{_line(claim)} uses an em dash")
    if claim.style == "bullet" and len(text.split()) > LONG_BULLET_WORDS:
        yield WritingFinding("long-bullet", f"{_line(claim)} is over {LONG_BULLET_WORDS} words")
    if not english:
        return
    if claim.style == "bullet" and _WEAK_OPENER.search(text):
        yield WritingFinding("weak-opener", f"{_line(claim)} opens with a weak phrase")
    if _FIRST_PERSON.search(text):
        yield WritingFinding("first-person", f"{_line(claim)} is written in the first person")


def _repeated_openers(draft: DraftDocument) -> Iterator[WritingFinding]:
    for bullets in _entries(draft):
        openers: dict[str, list[ClaimLine]] = {}
        for claim in bullets:
            if match := _FIRST_WORD.search(claim.text):
                openers.setdefault(match[0].casefold(), []).append(claim)
        for word, claims in openers.items():
            if len(claims) >= REPEATED_OPENER_LIMIT:
                ids = ", ".join(claim.claim_id for claim in claims)
                yield WritingFinding(
                    "repeated-opener",
                    f"{len(claims)} bullets of one entry open with {word!r}: {ids}",
                )


def _date_formats(draft: DraftDocument) -> Iterator[WritingFinding]:
    """One finding when the date lines write months in more than one way.

    Read as displayed: a Hebrew date line the renderer shows numerically counts as
    numeric, so our own normalization never trips this. A Hebrew month name the
    renderer leaves as written (a line it cannot read whole, such as "<month> YYYY -
    היום") counts as numeric too: the format is ours to normalize, not the user's to
    fix. Year-only lines carry no month and are a choice of precision, not of format.
    """
    seen: dict[str, str] = {}
    for section in draft.sections:
        for claim in section.claims:
            if claim.style != "date":
                continue
            shown = displayed_date(claim.text, draft.language)
            if draft.language == "he":
                shown = _HE_MONTH_YEAR.sub(
                    lambda match: f"{HEBREW_MONTHS[match[1]]:02d}/{match[2]}", shown
                )
            for name, pattern in _DATE_FORMATS.items():
                if pattern.search(shown):
                    seen.setdefault(name, shown)
    if len(seen) > 1:
        examples = "; ".join(f"{name}: {example!r}" for name, example in seen.items())
        yield WritingFinding("mixed-date-formats", f"date lines mix formats ({examples})")


def writing_findings(draft: DraftDocument) -> list[WritingFinding]:
    """Every writing-style finding for the draft's sections, in document order."""
    english = draft.language == "en"
    findings = [
        finding
        for section in draft.sections
        for claim in section.claims
        for finding in _line_findings(claim, english)
    ]
    findings.extend(_repeated_openers(draft))
    findings.extend(_date_formats(draft))
    return findings
