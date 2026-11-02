"""Gap questions: asking about unmet requirements and turning answers into pending facts.

Commands name their sources (state-and-use-cases.md §1): a question set is asked
about one named analysis, and an answer is given to one named question.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ...domain.contracts.knowledge import Fact
from ...domain.gap_questions import ANSWER_MAX_CHARACTERS
from ..operations import OperationView
from ._base import BoundaryDTO


class AskGapQuestionsCommand(BoundaryDTO):
    """`ask_gap_questions`: one question per unmet requirement of the newest analysis."""

    application_id: str
    job_analysis_id: str = Field(min_length=1)
    provider: Literal["openai"] = "openai"
    model: str | None = None
    reasoning_effort: str | None = None


class DraftGapFactCommand(BoundaryDTO):
    """`draft_gap_fact`: the user's own answer to one question, to become a pending fact."""

    application_id: str
    gap_question_id: str = Field(min_length=1)
    answer: str = Field(min_length=1, max_length=ANSWER_MAX_CHARACTERS)
    provider: Literal["openai"] = "openai"
    model: str | None = None
    reasoning_effort: str | None = None


GapQuestionState = Literal["open", "drafting", "answered", "skipped"]


class GapQuestionView(BoundaryDTO):
    """One question, and what has become of it.

    `open`: no outcome and nothing drafting. `drafting`: a `draft_gap_fact` for it is
    queued or running. `answered`: the answer became `fact`, pending until the user
    confirms it (or already confirmed, or deleted - `fact.status` says which).
    `skipped`: the user declined to answer. `draft_operation` is the newest
    `draft_gap_fact` for the question, live or terminal, so a failed draft can be
    explained and retried.
    """

    id: str
    ordinal: int
    requirement_id: str
    requirement_text: str
    importance: str
    coverage: str
    question: str
    state: GapQuestionState
    answer: str | None = None
    fact: Fact | None = None
    draft_operation: OperationView | None = None


class GapQuestionSetView(BoundaryDTO):
    """The questions asked about the Application's newest analysis, newest set only.

    Empty `questions` with a null `operation_id`: none were asked about that analysis.
    """

    application_id: str
    job_analysis_id: str | None = None
    operation_id: str | None = None
    language: str | None = None
    asked_at: str | None = None
    questions: list[GapQuestionView] = []
