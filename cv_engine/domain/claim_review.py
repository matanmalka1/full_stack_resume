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


def _protected_numbers(value: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)?%?", value))


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
    one verbatim source quote per fact, and introduce no number the facts lack.
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
        for fact_id, quote in zip(assertion.fact_ids, assertion.source_quotes, strict=True):
            if fact_id not in fact_ids:
                continue  # reported once below as a coverage mismatch
            fact = facts.get(fact_id, canonical_only=True)
            if quote not in fact.meaning and quote not in facts.rendering(fact_id, language):
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
