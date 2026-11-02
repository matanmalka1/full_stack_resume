"""Gap questions: ask about unmet requirements, draft a pending fact from each answer.

product-spec §5, §9, §17; state-and-use-cases.md §13a. The provider is the real
adapter over the fake transport, and every Operation runs through the runner, so
what is asserted is the queue, the handler, the deterministic checks, the AI call
log, and what activation writes.
"""

from __future__ import annotations

import pytest
from api_harness import MUTATION_HEADERS
from fake_provider import FakeOpenAI
from foreground import foreground_executor
from helpers import ACCOUNT_MANAGER_JOB, actor_of, analysis_proposal, services_transactions
from sqlalchemy import select

from cv_engine.api.app import API_PREFIX
from cv_engine.application.commands import (
    AnalyzeCommand,
    AskGapQuestionsCommand,
    DraftGapFactCommand,
    IngestCommand,
)
from cv_engine.application.errors import (
    KnowledgeRejected,
    PreconditionFailed,
    StateConflict,
)
from cv_engine.domain.contracts.analysis import JobAnalysis, Requirement
from cv_engine.domain.contracts.analysis_proposal import ProposedRequirement
from cv_engine.domain.contracts.knowledge import FactStatus
from cv_engine.domain.contracts.providers import (
    FactDraftProposal,
    GapQuestionsProposal,
    ProposedGapQuestion,
)
from cv_engine.domain.contracts.taxonomy import Emphasis, ProfileName, Track
from cv_engine.domain.gap_questions import (
    GAP_QUESTION_LIMIT,
    fact_draft_problems,
    fact_tags,
    gap_requirements,
)
from cv_engine.infrastructure.persistence.tables import ai_calls, gap_answers
from cv_engine.util import new_id

SALES_CYCLE = "Experience owning the full sales cycle."
ENGLISH = "Fluent English."
NEGOTIATION = "negotiation"


def _requirement(requirement_id: str, importance: str, coverage: str) -> Requirement:
    return Requirement(
        requirement_id=requirement_id,
        text=requirement_id,
        importance=importance,  # type: ignore[arg-type]
        coverage=coverage,  # type: ignore[arg-type]
    )


# The pure rules.


def test_gap_requirements_are_unmet_ones_mandatory_first_and_capped() -> None:
    analysis = JobAnalysis(
        track=Track.SALES,
        profile=ProfileName.ACCOUNT_MANAGER,
        emphasis=Emphasis.ACCOUNT_GROWTH,
        language="en",
        summary="s",
        requirements=[
            _requirement("preferred-partial", "preferred", "partial"),
            _requirement("mandatory-matched", "mandatory", "matched"),
            _requirement("mandatory-unknown", "mandatory", "unknown"),
            _requirement("unknown-unsupported", "unknown", "unsupported"),
            _requirement("mandatory-unsupported", "mandatory", "unsupported"),
            *(_requirement(f"extra-{n}", "preferred", "unsupported") for n in range(6)),
        ],
    )
    chosen = [requirement.requirement_id for requirement in gap_requirements(analysis)]
    assert len(chosen) == GAP_QUESTION_LIMIT
    assert chosen[:2] == ["mandatory-unsupported", "preferred-partial"]
    assert "mandatory-matched" not in chosen and "mandatory-unknown" not in chosen
    assert "unknown-unsupported" not in chosen  # preferred ones fill the cap first


def test_a_drafted_fact_may_not_add_a_number_or_a_named_term() -> None:
    answer = "I ran the quarterly renewals for 40 accounts in Salesforce."
    clean, offending = fact_draft_problems(
        answer, ["Ran quarterly renewals for 40 accounts in Salesforce."]
    )
    assert (clean, offending) == ([], [])

    problems, offending = fact_draft_problems(
        answer, ["Ran renewals for 45 accounts in Salesforce and HubSpot, growing ARR 20%."]
    )
    assert problems == ["unsupported-number", "unsupported-term"]
    assert set(offending) == {"45", "20%", "HubSpot", "ARR"}

    # A sentence-initial capital is rewording, not a name.
    assert fact_draft_problems("i led the onboarding", ["Led the onboarding."]) == ([], [])
    assert fact_draft_problems(answer, ["", "x"])[0] == ["empty-wording"]


def test_fact_tags_keep_the_source_tags_and_only_known_ones() -> None:
    assert fact_tags(["crm", "invented", "sales"], ["crm", "sales"], "sales") == [
        "sales",
        "situational",
        "crm",
    ]


# Through the runner.


def _analyzed(services, fake_openai: FakeOpenAI, *, language: str = "en"):
    """An Application whose newest analysis has two unmet requirements and one met."""
    fake_openai.script(
        "propose_analysis",
        analysis_proposal(
            language=language,
            requirements=[
                ProposedRequirement(
                    text=NEGOTIATION,
                    importance="preferred",
                    coverage="unsupported",
                    shortfall_severity="material",
                ),
                ProposedRequirement(
                    text=SALES_CYCLE,
                    importance="mandatory",
                    coverage="unsupported",
                    shortfall_severity="material",
                ),
                ProposedRequirement(text=ENGLISH, importance="mandatory", coverage="unknown"),
            ],
        ),
    )
    actor = actor_of(services)
    ingested = services.applications.ingest(
        actor,
        IngestCommand(
            company=f"Gap Co {new_id()[:8]}",
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
            acknowledged_duplicates=True,
            client="web",
        ),
    )
    queued = services.operation_submissions.submit_analysis(
        actor,
        AnalyzeCommand(
            application_id=ingested.application_id, job_text_hash=ingested.job_text_hash
        ),
        idempotency_key=new_id(),
        analysis_service=services.analysis,
    )
    done = foreground_executor(services).execute(queued.id)
    assert done.status.value == "succeeded", done.safe_failure_detail
    detail = services.queries.application_detail(actor, ingested.application_id)
    return actor, ingested.application_id, detail


def _ask(services, actor, application_id: str, analysis_id: str):
    queued = services.operation_submissions.submit_gap_questions(
        actor,
        AskGapQuestionsCommand(application_id=application_id, job_analysis_id=analysis_id),
        idempotency_key=new_id(),
        gap_questions=services.gap_questions,
    )
    return foreground_executor(services).execute(queued.id)


def _echo_questions(payload) -> GapQuestionsProposal:
    return GapQuestionsProposal(
        questions=[
            ProposedGapQuestion(
                requirement_id=item["requirement_id"], question=f"Tell us about {item['text']}?"
            )
            for item in payload["requirements"]
        ]
    )


def _answer(services, actor, application_id: str, question_id: str, answer: str):
    queued = services.operation_submissions.submit_gap_answer(
        actor,
        DraftGapFactCommand(
            application_id=application_id, gap_question_id=question_id, answer=answer
        ),
        idempotency_key=new_id(),
        gap_questions=services.gap_questions,
    )
    return foreground_executor(services).execute(queued.id)


def test_questions_are_asked_about_unmet_requirements_only(
    ai_services, fake_openai: FakeOpenAI
) -> None:
    actor, application_id, detail = _analyzed(ai_services, fake_openai)
    assert "ask_gap_questions" in detail.available_actions

    fake_openai.script("propose_gap_questions", _echo_questions)
    done = _ask(ai_services, actor, application_id, detail.latest_analysis_id)
    assert done.status.value == "succeeded", done.safe_failure_detail

    sent = fake_openai.calls_for("propose_gap_questions")[-1].payload
    assert [item["text"] for item in sent["requirements"]] == [SALES_CYCLE, NEGOTIATION]
    assert sent["language"] == "en"

    view = ai_services.gap_questions.read(actor, application_id)
    assert view.job_analysis_id == detail.latest_analysis_id
    assert [question.requirement_text for question in view.questions] == [
        SALES_CYCLE,
        NEGOTIATION,
    ]
    assert {question.state for question in view.questions} == {"open"}
    assert {output.output_type for output in done.outputs} == {"gap_question"}
    assert len(done.outputs) == 2

    with services_transactions(ai_services).read() as tx:
        connection = services_transactions(ai_services).connection_for(tx)
        tasks = connection.execute(
            select(ai_calls.c.task).where(ai_calls.c.operation_id == done.id)
        ).scalars()
        assert list(tasks) == ["propose_gap_questions"]


def test_an_analysis_with_nothing_unmet_is_not_asked_about(
    ai_services, fake_openai: FakeOpenAI
) -> None:
    fake_openai.script("propose_analysis", analysis_proposal())
    actor = actor_of(ai_services)
    ingested = ai_services.applications.ingest(
        actor,
        IngestCommand(
            company="Nothing Unmet Co",
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
            acknowledged_duplicates=True,
            client="web",
        ),
    )
    queued = ai_services.operation_submissions.submit_analysis(
        actor,
        AnalyzeCommand(
            application_id=ingested.application_id, job_text_hash=ingested.job_text_hash
        ),
        idempotency_key=new_id(),
        analysis_service=ai_services.analysis,
    )
    foreground_executor(ai_services).execute(queued.id)
    detail = ai_services.queries.application_detail(actor, ingested.application_id)
    assert "ask_gap_questions" not in detail.available_actions
    with pytest.raises(PreconditionFailed):
        _ask(ai_services, actor, ingested.application_id, detail.latest_analysis_id)
    assert fake_openai.calls_for("propose_gap_questions") == []


def test_an_answer_becomes_a_pending_fact_with_the_answer_as_its_evidence(
    ai_services, fake_openai: FakeOpenAI
) -> None:
    actor, application_id, detail = _analyzed(ai_services, fake_openai)
    fake_openai.script("propose_gap_questions", _echo_questions)
    _ask(ai_services, actor, application_id, detail.latest_analysis_id)
    question = ai_services.gap_questions.read(actor, application_id).questions[0]

    answer = "I owned the sales cycle for 12 SMB accounts, from prospecting to close."
    fake_openai.script(
        "draft_fact_from_answer",
        FactDraftProposal(
            meaning="Owned the sales cycle for 12 SMB accounts from prospecting to close.",
            english="Owned the full sales cycle for 12 SMB accounts, from prospecting to close.",
            hebrew=None,
            tags=["sales", "not-a-known-tag"],
            resume_style="bullet",
        ),
    )
    done = _answer(ai_services, actor, application_id, question.id, answer)
    assert done.status.value == "succeeded", (done.safe_failure_detail, done.failure_reason)
    [output] = done.outputs
    assert output.output_type == "fact"

    sent = fake_openai.calls_for("draft_fact_from_answer")[-1].payload
    assert sent["answer"] == answer and sent["question"] == question.question

    fact = ai_services.knowledge_queries.show_fact(actor, output.output_id).fact
    assert fact.status is FactStatus.PENDING
    assert fact.source_file.endswith("situational_skills.json")
    assert answer in fact.provenance
    assert fact.tags[:2] == ["sales", "situational"]
    assert "not-a-known-tag" not in fact.tags

    view = ai_services.gap_questions.read(actor, application_id)
    answered = next(item for item in view.questions if item.id == question.id)
    assert answered.state == "answered"
    assert answered.answer == answer
    assert answered.fact is not None and answered.fact.fact_id == fact.fact_id

    # One outcome per question: a second answer is refused before anything is queued.
    with pytest.raises(StateConflict):
        _answer(ai_services, actor, application_id, question.id, "again")
    with pytest.raises(StateConflict):
        ai_services.gap_questions.skip(actor, application_id, question.id)

    # The user edits the pending draft, then confirms it; only then is it canonical.
    edited = ai_services.knowledge_lifecycle.edit_pending_fact(
        actor, fact.fact_id, renderings={"en": "Owned the sales cycle for 12 SMB accounts."}
    )
    assert edited.fact.renderings["en"] == "Owned the sales cycle for 12 SMB accounts."
    assert edited.fact.provenance == fact.provenance
    confirmed = ai_services.knowledge_lifecycle.confirm_fact(
        actor, fact.fact_id, explicitly_confirmed=True
    )
    assert confirmed.fact.status is FactStatus.CANONICAL
    with pytest.raises(KnowledgeRejected):
        ai_services.knowledge_lifecycle.edit_pending_fact(actor, fact.fact_id, meaning="later")


@pytest.mark.parametrize(
    ("english", "problem"),
    [
        ("Owned the sales cycle for 15 accounts.", "unsupported-number"),
        ("Owned the sales cycle in HubSpot.", "unsupported-term"),
    ],
)
def test_a_draft_that_adds_to_the_answer_is_refused_and_nothing_is_saved(
    ai_services, fake_openai: FakeOpenAI, english: str, problem: str
) -> None:
    actor, application_id, detail = _analyzed(ai_services, fake_openai)
    fake_openai.script("propose_gap_questions", _echo_questions)
    _ask(ai_services, actor, application_id, detail.latest_analysis_id)
    question = ai_services.gap_questions.read(actor, application_id).questions[0]
    facts_before = len(ai_services.knowledge_queries.list_facts(actor, None).items)

    fake_openai.script(
        "draft_fact_from_answer",
        FactDraftProposal(
            meaning="Owned the sales cycle.",
            english=english,
            hebrew=None,
            tags=["sales"],
            resume_style="bullet",
        ),
    )
    done = _answer(ai_services, actor, application_id, question.id, "I owned the sales cycle.")
    assert done.status.value == "failed"
    assert done.failure_code is not None and done.failure_code.value == "INVALID_OUTPUT"
    assert done.failure_reason is not None
    assert done.failure_reason.code == "fact_draft"
    assert problem in done.failure_reason.problems  # type: ignore[union-attr]
    assert len(ai_services.knowledge_queries.list_facts(actor, None).items) == facts_before

    view = ai_services.gap_questions.read(actor, application_id)
    still = next(item for item in view.questions if item.id == question.id)
    assert still.state == "open"
    assert still.draft_operation is not None and still.draft_operation.id == done.id
    with services_transactions(ai_services).read() as tx:
        connection = services_transactions(ai_services).connection_for(tx)
        assert connection.execute(select(gap_answers.c.id)).first() is None


def test_a_hebrew_application_needs_a_hebrew_rendering(
    ai_services, fake_openai: FakeOpenAI
) -> None:
    actor, application_id, detail = _analyzed(ai_services, fake_openai, language="he")
    fake_openai.script("propose_gap_questions", _echo_questions)
    _ask(ai_services, actor, application_id, detail.latest_analysis_id)
    view = ai_services.gap_questions.read(actor, application_id)
    assert view.language == "he"
    assert fake_openai.calls_for("propose_gap_questions")[-1].payload["language"] == "he"

    fake_openai.script(
        "draft_fact_from_answer",
        FactDraftProposal(
            meaning="Owned the sales cycle.",
            english="Owned the sales cycle.",
            hebrew=None,
            tags=["sales"],
            resume_style="bullet",
        ),
    )
    done = _answer(
        ai_services, actor, application_id, view.questions[0].id, "ניהלתי את כל מחזור המכירה."
    )
    assert done.status.value == "failed"
    assert done.failure_reason is not None
    assert "missing-rendering" in done.failure_reason.problems  # type: ignore[union-attr]


def test_a_skipped_question_stays_skipped(ai_services, fake_openai: FakeOpenAI) -> None:
    actor, application_id, detail = _analyzed(ai_services, fake_openai)
    fake_openai.script("propose_gap_questions", _echo_questions)
    _ask(ai_services, actor, application_id, detail.latest_analysis_id)
    question = ai_services.gap_questions.read(actor, application_id).questions[1]

    view = ai_services.gap_questions.skip(actor, application_id, question.id)
    skipped = next(item for item in view.questions if item.id == question.id)
    assert skipped.state == "skipped" and skipped.answer is None and skipped.fact is None
    with pytest.raises(StateConflict):
        ai_services.gap_questions.skip(actor, application_id, question.id)
    with pytest.raises(StateConflict):
        _answer(ai_services, actor, application_id, question.id, "late answer")


def test_the_routes_ask_read_answer_skip_and_edit(ai_api_worker, fake_openai: FakeOpenAI) -> None:
    services = ai_api_worker.services
    client = ai_api_worker.client
    actor, application_id, detail = _analyzed(services, fake_openai)
    base = f"{API_PREFIX}/applications/{application_id}/gap-questions"

    empty = client.get(base)
    assert empty.status_code == 200, empty.text
    assert empty.json()["questions"] == [] and empty.json()["operation_id"] is None

    stale = client.post(base, json={"job_analysis_id": new_id()}, headers=MUTATION_HEADERS)
    assert stale.status_code == 404, stale.text

    fake_openai.script("propose_gap_questions", _echo_questions)
    asked = client.post(
        base, json={"job_analysis_id": detail.latest_analysis_id}, headers=MUTATION_HEADERS
    )
    assert asked.status_code == 202, asked.text
    assert asked.headers["Location"].endswith(asked.json()["id"])
    assert asked.json()["operation_type"] == "ask_gap_questions"
    finished = ai_api_worker.wait_for_operation(asked.json()["id"])
    assert finished["status"] == "succeeded", finished

    questions = client.get(base).json()["questions"]
    assert [item["state"] for item in questions] == ["open", "open"]

    fake_openai.script(
        "draft_fact_from_answer",
        FactDraftProposal(
            meaning="Owned the sales cycle.",
            english="Owned the sales cycle.",
            hebrew=None,
            tags=["sales"],
            resume_style="bullet",
        ),
    )
    empty_answer = client.post(
        f"{base}/{questions[0]['id']}/answer", json={"answer": ""}, headers=MUTATION_HEADERS
    )
    assert empty_answer.status_code == 422, empty_answer.text
    answered = client.post(
        f"{base}/{questions[0]['id']}/answer",
        json={"answer": "I owned the sales cycle."},
        headers=MUTATION_HEADERS,
    )
    assert answered.status_code == 202, answered.text
    drafted = ai_api_worker.wait_for_operation(answered.json()["id"])
    assert drafted["status"] == "succeeded", drafted
    fact_id = drafted["outputs"][0]["output_id"]

    skipped = client.post(f"{base}/{questions[1]['id']}/skip", headers=MUTATION_HEADERS)
    assert skipped.status_code == 200, skipped.text
    states = {item["id"]: item for item in skipped.json()["questions"]}
    assert states[questions[0]["id"]]["state"] == "answered"
    assert states[questions[0]["id"]]["fact"]["status"] == "pending"
    assert states[questions[0]["id"]]["fact"]["source"] == "situational_skills.json"
    assert states[questions[1]["id"]]["state"] == "skipped"
    again = client.post(f"{base}/{questions[1]['id']}/skip", headers=MUTATION_HEADERS)
    assert again.status_code == 409, again.text

    edited = client.patch(
        f"{API_PREFIX}/facts/{fact_id}",
        json={"meaning": "Owned the whole sales cycle."},
        headers=MUTATION_HEADERS,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["fact"]["meaning"] == "Owned the whole sales cycle."
    assert edited.json()["fact"]["status"] == "pending"
