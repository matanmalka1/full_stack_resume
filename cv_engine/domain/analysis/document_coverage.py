"""Which covered mandatory requirements the written CV no longer evidences.

The analysis records, per requirement, the facts that answer it. Nothing
downstream is bound to use them: the writer chooses which facts to cite, and
the page-fit trim can drop the very line that carried a mandatory requirement.
This module compares the two after the fact. It decides nothing and stops
nothing - the projection turns its answer into a non-blocking warning, and an
evaluation harness can call it on its own to score drafts.

Pure and deterministic: the answer depends only on the analysis and the
document's claims, never on wording, so the same pair always yields the same
list in the analysis's own order.
"""

from __future__ import annotations

from ..contracts.analysis import Coverage, JobAnalysis, Requirement
from ..contracts.drafts import DraftDocument
from ..document import dependent_fact_ids

#: A requirement the analysis found evidence for. `unsupported` and `unknown`
#: have nothing the CV could have kept, so their absence is not a loss.
COVERED: frozenset[Coverage] = frozenset({"matched", "partial"})


def requirements_missing_from_document(
    analysis: JobAnalysis, content: DraftDocument | None
) -> list[Requirement]:
    """The mandatory, covered requirements none of whose supporting facts the CV cites.

    A requirement is returned when all of these hold:

    - `importance` is `mandatory` - a preferred or unknown one is the writer's
      choice to leave out;
    - `coverage` is `matched` or `partial` - there was something to show;
    - it lists at least one supporting fact - otherwise there is nothing the
      document could have cited, and nothing to compare;
    - no supporting fact is among the facts the document's claims link
      (`dependent_fact_ids`, the same set the document's basis is computed from).

    One supporting fact still cited is enough: the document still evidences the
    requirement, whichever of its facts it chose. A document without content
    cites nothing, and is answered with an empty list rather than every
    requirement - there is no written CV yet to have dropped anything.
    """
    if content is None:
        return []
    cited = dependent_fact_ids(content)
    return [
        requirement
        for requirement in analysis.requirements
        if requirement.importance == "mandatory"
        and requirement.coverage in COVERED
        and requirement.supporting_fact_ids
        and cited.isdisjoint(requirement.supporting_fact_ids)
    ]
