"""Gap questions over HTTP (state-and-use-cases.md §13a).

A question set is asked about one named analysis; an answer is given to one named
question and comes back as an Operation that drafts a pending fact. The model and
effort are the user's Settings, frozen when the Operation is queued, as for every
AI Operation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ...application.commands import GapQuestionSetView
from ...domain.gap_questions import ANSWER_MAX_CHARACTERS
from .facts import FactResponse
from .health import HttpSchema
from .operations import OperationResponse


class AskGapQuestionsRequest(HttpSchema):
    """Ask about the unmet requirements of this analysis, the Application's newest."""

    job_analysis_id: str = Field(min_length=1)


class AnswerGapQuestionRequest(HttpSchema):
    """The user's own answer, in their words; it is the only source of the fact."""

    answer: str = Field(min_length=1, max_length=ANSWER_MAX_CHARACTERS)


class GapQuestionResponse(HttpSchema):
    """One question and its outcome.

    `state`: `open` (unanswered), `drafting` (a `draft_gap_fact` is queued or
    running), `answered` (`fact` holds the drafted fact; `fact.status` is `pending`
    until confirmed), `skipped`. `draft_operation` is the newest `draft_gap_fact`
    for this question, live or terminal.
    """

    id: str
    ordinal: int
    requirement_id: str
    requirement_text: str
    importance: Literal["mandatory", "preferred", "unknown"]
    coverage: Literal["partial", "unsupported"]
    question: str
    state: Literal["open", "drafting", "answered", "skipped"]
    answer: str | None = None
    fact: FactResponse | None = None
    draft_operation: OperationResponse | None = None


class GapQuestionSetResponse(HttpSchema):
    """The newest question set of the Application's newest analysis.

    No set asked yet: `questions` is empty and `operation_id` is null.
    """

    application_id: str
    job_analysis_id: str | None = None
    operation_id: str | None = None
    language: Literal["en", "he"] | None = None
    asked_at: str | None = None
    questions: list[GapQuestionResponse]

    @classmethod
    def of(cls, view: GapQuestionSetView) -> GapQuestionSetResponse:
        """Project the application view onto the wire: facts by source, not by path."""
        return cls.model_validate(
            {
                **view.model_dump(mode="json", exclude={"questions"}),
                "questions": [
                    {
                        **question.model_dump(mode="json", exclude={"fact", "draft_operation"}),
                        "fact": (
                            FactResponse.of(question.fact) if question.fact is not None else None
                        ),
                        "draft_operation": (
                            OperationResponse.model_validate(
                                question.draft_operation.model_dump(mode="json")
                            )
                            if question.draft_operation is not None
                            else None
                        ),
                    }
                    for question in view.questions
                ],
            }
        )
