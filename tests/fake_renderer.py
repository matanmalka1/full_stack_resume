"""The real renderer, with the page count `create_draft` measures made deterministic.

Fitting a new draft to its page limit renders it through Chromium on every
measurement. A test whose subject is not that would pay for a browser - and have
its draft trimmed by whatever the real layout says - so the services the fixtures
build count pages from the content instead. Everything else is the real
`PlaywrightRenderer`: HTML, PDF, and validation are untouched.

`claims_per_page` of None means every draft fits on one page. `failure`, when set,
is raised by every measurement from the `fail_from`-th on (1-based), as a missing
or crashing browser would.
"""

from __future__ import annotations

import math

from cv_engine.application.errors import InfrastructureFailure
from cv_engine.domain.contracts.drafts import DraftDocument
from cv_engine.domain.contracts.knowledge import CandidateContext
from cv_engine.domain.frame import STRUCTURAL_STYLES
from cv_engine.infrastructure.rendering import PlaywrightRenderer


def evidence_lines(draft: DraftDocument) -> int:
    """The section lines a page-fit trim may count: every non-structural one."""
    return sum(
        1
        for section in draft.sections
        for claim in section.claims
        if claim.style not in STRUCTURAL_STYLES
    )


class PageCountingRenderer(PlaywrightRenderer):
    def __init__(self, knowledge_root, *, claims_per_page: int | None = None):
        super().__init__(knowledge_root)
        self.claims_per_page = claims_per_page
        self.failure: InfrastructureFailure | None = None
        self.fail_from = 1
        #: The evidence-line count of every draft measured, in order.
        self.measured: list[int] = []

    def measure_pages(self, draft: DraftDocument, candidate: CandidateContext) -> int:
        del candidate
        lines = evidence_lines(draft)
        self.measured.append(lines)
        if self.failure is not None and len(self.measured) >= self.fail_from:
            raise self.failure
        if self.claims_per_page is None:
            return 1
        return max(1, math.ceil(lines / self.claims_per_page))
