"""The one deterministic check a semantic review assertion set must pass.

A `reviewed` claim is wording no template produced, authorized because a separate
review attested it against canonical facts. That attestation is checked twice: when
the review's proposal is activated, and again whenever the draft is validated for
approval. Both run this function, so the evidence that let a line in is exactly the
evidence that keeps it in, and a check cannot drift between the two.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol

from .drafts import EDITABLE_STYLES
from .facts import FactStore, FactStoreError

REVIEW_POLICY_VERSION = "semantic-claim-support-v1"

ReviewProblemCode = Literal[
    "invalid-review-evidence",
    "incomplete-review-coverage",
    "invalid-review-claim-quote",
    "invalid-review-source-quote",
    "stale-review-source",
    "review-fact-coverage-mismatch",
    "unsupported-review-number",
]

#: Problems that mean the evidence does not describe the claim at all. They take
#: precedence over the finer checks: a number the facts do not carry is only an
#: `unsupported` finding when the assertions actually cover the claim.
SHAPE_PROBLEMS: frozenset[ReviewProblemCode] = frozenset(
    {"invalid-review-evidence", "incomplete-review-coverage"}
)


class ReviewAssertion(Protocol):
    @property
    def claim_quote(self) -> str: ...

    @property
    def fact_ids(self) -> list[str]: ...

    @property
    def source_quotes(self) -> list[str]: ...


@dataclass(frozen=True)
class ReviewProblem:
    code: ReviewProblemCode
    message: str


def _alphanumeric(value: str) -> str:
    return "".join(char.casefold() for char in value if char.isalnum())


_SCALES: dict[str, int] = {
    "k": 1_000,
    "thousand": 1_000,
    "אלף": 1_000,
    "אלפים": 1_000,
    "m": 1_000_000,
    "million": 1_000_000,
    "מיליון": 1_000_000,
    "מליון": 1_000_000,
    "b": 1_000_000_000,
    "billion": 1_000_000_000,
    "מיליארד": 1_000_000_000,
}
_PERCENT = ("%", "percent", "per cent", "אחוזים", "אחוז")
_UNITS = "|".join(re.escape(unit) for unit in sorted([*_SCALES, *_PERCENT], key=len, reverse=True))
#: A number as written: an optional currency mark (ignored, as it always was), digits
#: with optional thousands separators and decimals, and an optional scale or percent
#: word. A unit must end the word, so "2 managers" is 2 and "3 B2B" is 3, not billions.
_NUMBER = re.compile(
    r"(?P<number>\d{1,3}(?:,\d{3})+(?!\d)|\d+)(?P<fraction>\.\d+)?"
    rf"(?:\s*(?P<unit>%|(?:{_UNITS})(?!\w)))?",
    re.IGNORECASE,
)


def _protected_numbers(value: str) -> set[str]:
    """Each number in `value` by what it states, not how it is written.

    `1,000` and `1000`, `40%` and `40 percent` / `40 אחוז`, `2M` and `2 million` and
    `2,000,000` all state the same value, so a reformat is not a new number. A changed
    value, a changed scale, or a plain number becoming a percentage still is.
    """
    found: set[str] = set()
    for match in _NUMBER.finditer(value):
        amount = Decimal(match["number"].replace(",", "") + (match["fraction"] or ""))
        # A digit inside a Latin word ("B2B", "S3") is part of a name, so a letter after
        # it is no scale; the digit itself is still protected. A Hebrew prefix letter
        # ("ב40%") attaches to a quantity, so it does not count.
        previous = value[match.start() - 1 : match.start()]
        inside_word = previous.isascii() and previous.isalpha()
        unit = "" if inside_word else (match["unit"] or "").casefold()
        amount *= _SCALES.get(unit, 1)
        kind = "%" if unit in _PERCENT else ""
        found.add(f"{kind}{format(amount.normalize(), 'f')}")
    return found


def _quotes_pair_with_facts(
    linked: list[str], quotes: list[str], texts: dict[str, tuple[str, str]]
) -> bool:
    """Whether every linked fact takes its own verbatim quote, in whatever order.

    The pairing is what attests support; the order the reviewer listed its quotes in
    attests nothing, so the pairing is found rather than read positionally. Each quote
    serves one fact at most. A small bipartite match: an assertion cites a handful of
    facts.
    """
    fits = [
        [
            index
            for index, quote in enumerate(quotes)
            if any(quote in text for text in texts[fact_id])
        ]
        for fact_id in linked
    ]
    owner: dict[int, int] = {}

    def assign(fact: int, seen: set[int]) -> bool:
        for quote in fits[fact]:
            if quote in seen:
                continue
            seen.add(quote)
            if quote not in owner or assign(owner[quote], seen):
                owner[quote] = fact
                return True
        return False

    return all(assign(fact, set()) for fact in range(len(linked)))


def review_problems(
    *,
    claim_id: str,
    text: str,
    style: str,
    fact_ids: Sequence[str],
    assertions: Sequence[ReviewAssertion],
    facts: FactStore,
    language: str,
) -> list[ReviewProblem]:
    """Every reason the assertions fail to attest `text` against its canonical facts.

    An empty list is the only passing result. The assertions must cover the whole
    claim, quote only the claim itself, cite each linked fact and nothing else with
    one verbatim source quote per fact (paired in any order), and introduce no number
    the facts lack.
    """
    if style not in EDITABLE_STYLES or not assertions:
        return [
            ReviewProblem(
                "invalid-review-evidence",
                f"claim {claim_id} has no reviewable assertions for style {style!r}",
            )
        ]
    problems: list[ReviewProblem] = []
    covered = "".join(item.claim_quote for item in assertions)
    if _alphanumeric(covered) != _alphanumeric(text):
        problems.append(
            ReviewProblem("incomplete-review-coverage", f"claim {claim_id} is not fully reviewed")
        )

    source_texts: list[str] = []
    for fact_id in fact_ids:
        try:
            fact = facts.get(fact_id, canonical_only=True)
            source_texts += [fact.meaning, facts.rendering(fact_id, language)]
        except FactStoreError as exc:
            problems.append(ReviewProblem("stale-review-source", f"claim {claim_id}: {exc}"))
    if problems:
        return problems

    cited: set[str] = set()
    for assertion in assertions:
        cited.update(assertion.fact_ids)
        if not assertion.claim_quote or assertion.claim_quote not in text:
            problems.append(
                ReviewProblem(
                    "invalid-review-claim-quote",
                    f"claim {claim_id} quotes wording it does not contain",
                )
            )
        if len(assertion.fact_ids) != len(assertion.source_quotes):
            problems.append(
                ReviewProblem(
                    "invalid-review-source-quote",
                    f"claim {claim_id} does not map one source quote per fact",
                )
            )
            continue
        # A fact outside the claim's links is reported once below as a coverage
        # mismatch, so only the linked ones need a quote here.
        linked = [fact_id for fact_id in assertion.fact_ids if fact_id in fact_ids]
        texts = {
            fact_id: (
                facts.get(fact_id, canonical_only=True).meaning,
                facts.rendering(fact_id, language),
            )
            for fact_id in linked
        }
        if not _quotes_pair_with_facts(linked, list(assertion.source_quotes), texts):
            problems.append(
                ReviewProblem(
                    "invalid-review-source-quote",
                    f"claim {claim_id} has unverified source quotes",
                )
            )
    if cited != set(fact_ids):
        problems.append(
            ReviewProblem(
                "review-fact-coverage-mismatch",
                f"claim {claim_id} evidence does not cover exactly its linked facts",
            )
        )
    if _protected_numbers(text) - _protected_numbers(" ".join(source_texts)):
        problems.append(
            ReviewProblem(
                "unsupported-review-number",
                f"claim {claim_id} states a number its facts do not carry",
            )
        )
    return problems
