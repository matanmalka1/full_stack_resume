"""Independent structural completeness for AI requirement extraction."""

from __future__ import annotations

from .concepts import RequirementConceptStore
from .segmentation import StatementLine, overlaps, requirement_lines, statement_asks


def _asks(text: str, lines: list[StatementLine]) -> list[tuple[int, int]]:
    return [ask for line in lines for ask in statement_asks(text, line)]


def span_completeness(
    text: str,
    spans: list[tuple[int, int]],
    concepts: RequirementConceptStore,
) -> float | None:
    lines = requirement_lines(text, concepts)
    if not lines:
        return None
    asks = _asks(text, lines)
    understood = sum(1 for ask in asks if any(overlaps(ask, span) for span in spans))
    return understood / len(asks)
