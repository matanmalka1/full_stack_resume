"""Measure extraction completeness, state, failure, and confidence."""

from __future__ import annotations

from typing import Literal

from .concepts import RequirementConceptStore
from .extraction import ExtractedRequirement
from .segmentation import StatementLine, overlaps, requirement_lines, statement_asks

ExtractionState = Literal["parsed", "partial", "unparsed", "absent"]


def _asks(text: str, lines: list[StatementLine]) -> list[tuple[int, int]]:
    """Every demand the requirement statements make, as posting offsets.

    The unit the measure counts. A statement is what the posting formatted,
    not what it demanded: one bullet can state three things, and counting
    statements scored such a bullet fully understood for one of the three.
    See `statement_asks` for why the split lives in the measure rather than in
    the segmenter.
    """
    return [ask for line in lines for ask in statement_asks(text, line)]


def _understood(asks: list[tuple[int, int]], spans: list[tuple[int, int]]) -> int:
    """How many stated demands had something read inside them.

    Offset overlap, not `text.find`. The extracted span carries normalized
    text that a posting wrapping the requirement across a line no longer
    contains, so the search failed and the statement was counted unread.
    """
    return sum(1 for ask in asks if any(overlaps(ask, span) for span in spans))


def span_completeness(
    text: str,
    spans: list[tuple[int, int]],
    concepts: RequirementConceptStore,
) -> float | None:
    """`extraction_completeness`, asked of spans rather than of concept matches.

    The same independently derived structural denominator, so an AI extraction
    and a deterministic one are measured against one ruler and neither can
    inflate completeness by choosing a friendlier segmentation of the posting
    (D5: a provider cannot certify its own completeness). `None` still means
    the posting states no requirements at all.
    """
    lines = requirement_lines(text, concepts)
    if not lines:
        return None
    asks = _asks(text, lines)
    return _understood(asks, spans) / len(asks)


def confidence_from_completeness(completeness: float | None) -> float:
    """What a completeness measure alone is worth as an extraction score.

    The same curve `extraction_confidence` applies, without the concept
    classification factor: under D5 an AI extraction is not asked to map the
    posting onto a closed vocabulary, so "how much of what was read the
    vocabulary could classify" is no longer a question about it, and folding
    in a 1.0 for a measure that does not apply would be arithmetic theatre.

    `None` - the posting states no requirements - scores 1.0: there was
    nothing to miss. The caller still records `requirements-absent` for it,
    which is the reason a user actually needs to see.
    """
    if completeness is None:
        return 1.0
    if completeness == 0.0:
        return 0.0
    return round(_COVERAGE_FLOOR + (1.0 - _COVERAGE_FLOOR) * completeness, 4)


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

    Counted per demand, not per statement. `requirement_lines` still decides
    *whether* the posting states requirements at all - so `None` still means
    exactly what it meant - but a statement that packs three demands into one
    bullet now owes three, and a match reaching one of them no longer pays for
    the other two.
    """
    lines = requirement_lines(text, concepts)
    if not lines:
        return None
    asks = _asks(text, lines)
    return _understood(asks, [(item.start, item.end) for item in extracted]) / len(asks)


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
) -> bool:
    """Requirements were stated in some form, and none of them were read.

    Keyed on requirement-bearing language rather than on section formatting. A
    posting that states its requirements in prose and is understood not at all
    is exactly as failed as one with a `Requirements:` block, and scoring it as
    a success was a false green.

    Exactly `extraction_state(...) == "unparsed"`, with no override. A local gap
    rule recognising one term the concept vocabulary does not model yet
    (`understood_elsewhere`) used to short-circuit this to `False` - before the
    state was even computed, so a single rule hit cleared the failure for a
    posting whose twenty requirement statements were all unread. "The rules read
    something" is a claim about how much credit the confidence score owes, not
    about whether the extraction failed; it stays an input to
    `extraction_confidence` alone, where it earns the coverage floor and
    nothing more.
    """
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
