"""Measure extraction completeness, state, failure, and confidence."""

from __future__ import annotations

from typing import Literal

from .concepts import RequirementConceptStore
from .extraction import ExtractedRequirement
from .segmentation import StatementLine, requirement_lines

ExtractionState = Literal["parsed", "partial", "unparsed", "absent"]


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

