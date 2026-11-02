"""Gap questions (state-and-use-cases.md §13a): ask, answer, skip, read.

Asking and answering are Operations (`202` with the Operation to poll); skipping and
reading are synchronous. Each route is one application command or query, addressed
to the Application that owns the questions.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from ...application.commands import AskGapQuestionsCommand, DraftGapFactCommand
from ...util import new_id
from ..dependencies import Services
from ..headers import IdempotencyKey
from ..responses import accepted_operation
from ..schemas.gap_questions import (
    AnswerGapQuestionRequest,
    AskGapQuestionsRequest,
    GapQuestionSetResponse,
)
from ..schemas.operations import OperationResponse
from ..session_cookie import CurrentActor

router = APIRouter(prefix="/applications/{application_id}/gap-questions", tags=["gap-questions"])


@router.get(
    "",
    response_model=GapQuestionSetResponse,
    summary="Read the questions asked about the newest analysis, and their outcomes",
)
def read_gap_questions(
    application_id: str, services: Services, actor: CurrentActor
) -> GapQuestionSetResponse:
    return GapQuestionSetResponse.of(services.gap_questions.read(actor, application_id))


@router.post(
    "",
    response_model=OperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ask one question per unsupported or partial requirement",
)
def ask_gap_questions(
    application_id: str,
    request: AskGapQuestionsRequest,
    services: Services,
    actor: CurrentActor,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> OperationResponse:
    """`202`. Refused (`412`) when the analysis has nothing to ask about, `409` when a
    newer analysis exists."""
    queued = services.operation_submissions.submit_gap_questions(
        actor,
        AskGapQuestionsCommand(
            application_id=application_id, job_analysis_id=request.job_analysis_id
        ),
        idempotency_key=idempotency_key or new_id(),
        gap_questions=services.gap_questions,
    )
    return accepted_operation(response, queued)


@router.post(
    "/{question_id}/answer",
    response_model=OperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Answer one question; a pending fact is drafted from the answer",
)
def answer_gap_question(
    application_id: str,
    question_id: str,
    request: AnswerGapQuestionRequest,
    services: Services,
    actor: CurrentActor,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> OperationResponse:
    """`202`. The fact it drafts is `pending`: it counts only once the user confirms it."""
    queued = services.operation_submissions.submit_gap_answer(
        actor,
        DraftGapFactCommand(
            application_id=application_id,
            gap_question_id=question_id,
            answer=request.answer,
        ),
        idempotency_key=idempotency_key or new_id(),
        gap_questions=services.gap_questions,
    )
    return accepted_operation(response, queued)


@router.post(
    "/{question_id}/skip",
    response_model=GapQuestionSetResponse,
    summary="Decline to answer one question",
)
def skip_gap_question(
    application_id: str, question_id: str, services: Services, actor: CurrentActor
) -> GapQuestionSetResponse:
    """`200` with the question set as it now reads; `409` if it already has an outcome."""
    return GapQuestionSetResponse.of(
        services.gap_questions.skip(actor, application_id, question_id)
    )
