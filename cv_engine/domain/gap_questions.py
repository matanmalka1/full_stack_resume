"""Gap questions: which requirements to ask about, and what a drafted fact may say.

An analysis names the requirements the user's facts do not answer. A gap question
asks the user, in their own words, about real experience that would answer one of
them; the answer is turned into one pending fact (product-spec §17). Two rules live
here, both pure:

- which requirements are asked about: `unsupported` or `partial`, mandatory first,
  at most `GAP_QUESTION_LIMIT`;
- what a fact drafted from an answer may not add: a number, or a named tool,
  product, or acronym, that the answer itself does not contain. This is the part of
  "nothing the answer does not say" that can be checked without a reader; the rest
  is the prompt's, and the user confirms the fact before it counts.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import Literal

from .claim_review import protected_numbers
from .contracts.analysis import JobAnalysis, Requirement

#: How many questions one set asks at most. A short list is answered; a long one is
#: skipped wholesale.
GAP_QUESTION_LIMIT = 6

#: The coverages a question can help with. `unknown` is not asked about: the engine
#: could not tell whether the facts answer it, which is not a gap.
GAP_COVERAGES = frozenset({"unsupported", "partial"})

#: Where a fact drafted from an answer is filed: the source new real facts default
#: to, the one that holds skills and experience outside the track files.
GAP_FACT_SOURCE = "situational_skills.json"
#: The tag every fact in that source carries.
GAP_FACT_SOURCE_TAG = "situational"

#: Bounds on what the user types. Long enough for a paragraph about one piece of
#: work; short enough that it is an answer to one question.
ANSWER_MAX_CHARACTERS = 2000
QUESTION_MAX_CHARACTERS = 500

_IMPORTANCE_ORDER = {"mandatory": 0, "preferred": 1, "unknown": 2}

FactDraftProblem = Literal[
    "unsupported-number",
    "unsupported-term",
    "missing-rendering",
    "empty-wording",
]

#: A Latin-script term: letters, then letters, digits, and the joiners tool names use
#: (`Node.js`, `C#`, `C++`, `ASP.NET`). It never ends on a joiner but `+` or `#`, so a
#: sentence's closing period is not part of the word before it.
_TERM = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]*[A-Za-z0-9+#]|[A-Za-z]")


def gap_requirements(analysis: JobAnalysis, limit: int = GAP_QUESTION_LIMIT) -> list[Requirement]:
    """The requirements a question set asks about, in the order it asks.

    Mandatory before preferred before unknown importance; within one importance,
    the order the analysis read them in.
    """
    candidates = [
        (index, requirement)
        for index, requirement in enumerate(analysis.requirements)
        if requirement.coverage in GAP_COVERAGES
    ]
    candidates.sort(key=lambda item: (_IMPORTANCE_ORDER.get(item[1].importance, 2), item[0]))
    return [requirement for _index, requirement in candidates[:limit]]


def _named_terms(text: str) -> set[str]:
    """Terms that name something: a capital after the first letter, a digit, or a joiner.

    `PostgreSQL`, `AWS`, `GitHub`, `CI`, `S3`, `Node.js`, `C#` are such terms; a word
    capitalized only because it opens a sentence (`Built`, `Led`) is not, so English
    rewording of the user's own verbs is not mistaken for something new.
    """
    terms: set[str] = set()
    for match in _TERM.finditer(text):
        token = match.group(0)
        if (
            any(char.isupper() for char in token[1:])
            or any(char.isdigit() for char in token)
            or any(char in "+#." for char in token)
        ):
            terms.add(token)
    return terms


def fact_draft_problems(
    answer: str, wording: Sequence[str]
) -> tuple[list[FactDraftProblem], list[str]]:
    """Why wording drafted from `answer` adds something the answer does not say.

    Returns the problem codes and the offending numbers and terms. Two checks:
    every number in the wording occurs in the answer (the same digit runs claim
    review compares), and every named term (`_named_terms`) occurs in the answer,
    ignoring case. Empty wording is a problem of its own.
    """
    problems: list[FactDraftProblem] = []
    offending: list[str] = []
    if any(not text.strip() for text in wording):
        problems.append("empty-wording")
    combined = " ".join(wording)
    written = protected_numbers(combined)
    numbers = sorted(written[key] for key in written.keys() - protected_numbers(answer).keys())
    if numbers:
        problems.append("unsupported-number")
        offending.extend(numbers)
    folded = answer.casefold()
    terms = sorted(term for term in _named_terms(combined) if term.casefold() not in folded)
    if terms:
        problems.append("unsupported-term")
        offending.extend(terms)
    return problems, offending


def fact_tags(proposed: Iterable[str], vocabulary: Iterable[str], track: str) -> list[str]:
    """The tags a drafted fact is saved with.

    The track and the source's own tag first, as every fact in that source carries
    them; then the proposed tags that already exist in the user's facts, in the order
    proposed. A tag no fact uses is dropped rather than invented.
    """
    known = set(vocabulary)
    tags = [track, GAP_FACT_SOURCE_TAG]
    for tag in proposed:
        cleaned = tag.strip()
        if cleaned in known and cleaned not in tags:
            tags.append(cleaned)
    return tags
