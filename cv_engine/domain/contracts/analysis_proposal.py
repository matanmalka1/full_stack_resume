"""The analysis contract: what one provider call returns, and what survives it.

The previous contract asked a provider for character offsets, a declared
`source_role`, a `context_quote`, a composition with members, and a separate
unmapped-statement census - then treated any one of those being wrong as a
reason to refuse the whole reading. A live run showed what that costs: a model
returned sixteen requirements read correctly and lost all of them to a span
that reached one character past its sentence, and a second run lost fifteen to
a one-word context quote that the interpretation did not even need.

So the contract asks for what a model can actually give - the requirement's
text, how important it is, whether the candidate's facts answer it, and which
facts - and the engine answers the rest itself. Everything the engine can
prove it still proves: a fact must exist and be canonical, a positive reading
must carry evidence, a quote must occur in the posting. What it cannot prove
becomes an `AnalysisIssue` attached to the result, not an exception that
discards it. Only a response that cannot be parsed at all fails the operation.
"""

from __future__ import annotations

from typing import Literal

from .base import StrictModel
from .taxonomy import Emphasis, ProfileName, Track

#: How much the posting weights this requirement. `unknown` is a real answer:
#: a posting that never says whether something is required is not thereby
#: saying it is optional.
Importance = Literal["mandatory", "preferred", "unknown"]

#: Whether canonical facts answer the requirement. `unknown` is what an
#: unassessed or unevidenced reading collapses to - never `unsupported`, which
#: is a claim that the candidate lacks it.
ProposedRequirementCoverage = Literal["matched", "partial", "unsupported", "unknown"]

ProposalLanguage = Literal["en", "he"]


class ProposedRequirement(StrictModel):
    """One requirement, as the provider read it.

    `text` is the provider's transcription of what the posting asks for. The
    engine locates it in the snapshot itself rather than asking where it is;
    a text it cannot locate is kept and marked unverified, because a
    requirement the model read is still a requirement whether or not the
    engine could match its wording character for character.

    `fact_ids` is a citation, never a proof. Every id is checked against the
    canonical fact store, and a positive `coverage` with nothing left after
    that check collapses to `unknown`.
    """

    text: str
    importance: Importance = "unknown"
    coverage: ProposedRequirementCoverage = "unknown"
    fact_ids: list[str] = []
    rationale: str | None = None


class AnalysisProposal(StrictModel):
    """`propose_analysis`: one call, one reading of the posting.

    Classification and requirements come back together because they are one
    judgement about one text. Splitting them cost a second call, a second
    prompt version, and a second way for the two halves to disagree about the
    posting they had both just read.
    """

    track: Track
    profile: ProfileName
    emphasis: Emphasis
    language: ProposalLanguage
    requirements: list[ProposedRequirement]
    summary: str
    #: Kept because selection already reads them: they break ties between facts
    #: the semantic score rates equally (`domain/selection.py`). Dropping them
    #: would move selected content for reasons unrelated to this contract.
    keywords: list[str] = []


#: How the posting was found to carry this text. Stated rather than inferred
#: from whether offsets came back: "verified at one place", "verified but the
#: posting wraps it differently", and "verified in several places" are three
#: different answers that all lack a single span, and reading them back off a
#: missing span collapses them into one.
SourceMatch = Literal["exact", "normalized", "ambiguous", "not_found"]


class RequirementSource(StrictModel):
    """Where the posting says this requirement, when the engine could find it.

    `verified` is the claim that matters: the posting carries this text.
    `start` and `end` are a display detail, and they are absent whenever the
    match was not a single exact occurrence - picking one occurrence, or
    pointing into a whitespace-collapsed copy the snapshot does not hold, would
    be the engine inventing a precision it does not have.
    """

    quote: str
    match: SourceMatch = "not_found"
    start: int | None = None
    end: int | None = None

    @property
    def verified(self) -> bool:
        return self.match != "not_found"


#: What the engine could not establish about one proposal, kept beside the
#: result instead of replacing it. Every code here describes something the
#: engine narrowed or dropped, never something it accepted on trust.
IssueCode = Literal[
    "quote_not_found",
    "quote_ambiguous",
    "unknown_fact",
    "fact_not_canonical",
    "coverage_without_evidence",
    "duplicate_requirement",
    "requirement_unusable",
]


class AnalysisIssue(StrictModel):
    """One thing the engine corrected, dropped, or could not confirm.

    `severity` is `warning` for everything the engine could handle by lowering
    what the analysis claims, which is every code above. It exists so a future
    condition that genuinely should stop the workflow can say so without
    changing the shape of the record.
    """

    code: IssueCode
    severity: Literal["warning", "error"] = "warning"
    #: Which requirement in the *proposal* this is about, when it is about one.
    requirement_index: int | None = None
    details: dict[str, str] = {}
