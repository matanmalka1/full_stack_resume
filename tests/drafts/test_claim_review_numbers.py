"""The review's number check compares what a number states, not how it is written."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cv_engine.domain.claim_review import review_problems
from cv_engine.domain.contracts.drafts import ClaimReviewAssertion


class _OneFact:
    """The two reads `review_problems` makes of a fact store, for one fact."""

    def __init__(self, text: str) -> None:
        self.text = text

    def get(self, fact_id: str, *, canonical_only: bool = False) -> SimpleNamespace:
        return SimpleNamespace(meaning=self.text)

    def rendering(self, fact_id: str, language: str) -> str:
        return self.text


def _number_problems(source: str, claim: str, language: str = "en") -> set[str]:
    problems = review_problems(
        claim_id="claim-1",
        text=claim,
        style="bullet",
        fact_ids=["fact-1"],
        assertions=[
            ClaimReviewAssertion(claim_quote=claim, fact_ids=["fact-1"], source_quotes=[source])
        ],
        facts=_OneFact(source),  # type: ignore[arg-type]
        language=language,
    )
    return {problem.code for problem in problems}


@pytest.mark.parametrize(
    ("source", "claim", "language"),
    [
        ("Grew a book of 1,000 accounts", "Grew a 1000-account book", "en"),
        ("Raised retention by 40%", "Raised retention by 40 percent", "en"),
        ("Raised retention by 40 percent", "Raised retention by 40%", "en"),
        ("Closed $2M in new business", "Closed 2 million dollars in new business", "en"),
        ("Closed $2M in new business", "Closed $2,000,000 in new business", "en"),
        ("Managed a 1.5M budget", "Managed a $1,500,000 budget", "en"),
        ("Served 12K users", "Served 12,000 users", "en"),
        ("Served 12 thousand users", "Served 12K users", "en"),
        ("הגדלת שימור לקוחות ב-40%", "הגדלת שימור לקוחות ב-40 אחוז", "he"),
        ("הגדלת שימור לקוחות ב40 אחוזים", "הגדלת שימור לקוחות ב-40%", "he"),
        ("ניהול תקציב של 2 מיליון ₪", "ניהול תקציב של ₪2,000,000", "he"),
        # A digit inside a name stays a digit; it is not read as a scale.
        ("Sold B2B software to 3 banks", "Sold B2B software to 3 banks", "en"),
    ],
)
def test_a_reformatted_number_is_the_same_number(source: str, claim: str, language: str) -> None:
    assert "unsupported-review-number" not in _number_problems(source, claim, language)


@pytest.mark.parametrize(
    ("source", "claim"),
    [
        ("Grew a book of 1,000 accounts", "Grew a book of 1,001 accounts"),
        ("Grew a book of 1,000 accounts", "Grew a book of 10,000 accounts"),
        ("Raised retention by 40%", "Raised retention by 45 percent"),
        ("Closed $2M in new business", "Closed $2B in new business"),
        ("Closed $2M in new business", "Closed $2 in new business"),
        ("Closed 2 deals", "Closed 2M in deals"),
        ("Managed 40 accounts", "Grew revenue 40%"),
        ("Grew revenue 40%", "Managed 40 accounts"),
        ("Managed 40 accounts", "Managed 40 accounts across 7 regions"),
        ("Managed 1.5M budget", "Managed 1.6M budget"),
    ],
)
def test_a_new_or_changed_number_still_fails(source: str, claim: str) -> None:
    assert "unsupported-review-number" in _number_problems(source, claim)


def test_a_new_number_fails_in_hebrew_too() -> None:
    codes = _number_problems("הגדלת שימור לקוחות ב-40%", "הגדלת שימור לקוחות ב-45 אחוז", "he")
    assert "unsupported-review-number" in codes
