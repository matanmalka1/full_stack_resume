"""Gap questions: ask about unmet requirements, turn each answer into a pending fact.

product-spec §9 and §17, state-and-use-cases.md §13a. Two Operations and two
synchronous commands:

- `ask_gap_questions` reads one analysis, picks its unsupported and partial
  requirements (`domain/gap_questions.py`), and asks the provider for one question
  each. Activation records the questions; they are immutable.
- `draft_gap_fact` sends one question and the user's answer to the provider, which
  words one fact from the answer alone. The engine refuses wording with a number or
  a named term the answer lacks, then activation creates the fact as `pending` and
  records the answer beside it, in one transaction. Nothing becomes canonical here:
  the user edits (`edit_pending_fact`) and confirms it like any other pending fact.
- `skip_gap_question` records that the user declined to answer.
- `read` is the newest question set of the newest analysis, with each outcome.

Provider calls run outside every scope; each attempt is logged by `AICallRunner`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ...domain.contracts.analysis import JobAnalysis, Requirement
from ...domain.contracts.knowledge import Fact, FactStatus
from ...domain.facts import source_name_of
from ...domain.gap_questions import (
    GAP_FACT_SOURCE,
    QUESTION_MAX_CHARACTERS,
    fact_draft_problems,
    fact_tags,
    gap_requirements,
)
from ...domain.knowledge import Knowledge
from ...util import new_id, utc_now
from ..actor import Actor
from ..commands import (
    AskGapQuestionsCommand,
    DraftGapFactCommand,
    GapQuestionSetView,
    GapQuestionView,
)
from ..errors import (
    FactDraftRejected,
    LineageBroken,
    PreconditionFailed,
    ProviderInvalidOutput,
    ProviderNotConfigured,
    StateConflict,
)
from ..operations import FactDraftReason, OperationStatus, as_operation_view
from ..ports import AIProvider, FactFromAnswerContext, GapQuestionsContext, TransactionManager
from ..ports.analysis_plans import (
    AnalysisContextSource,
    AnalysisContextSourceReader,
    AnalysisKnowledgeSource,
)
from ..ports.gap_questions import GapAnswerRecord, GapQuestionRecord, GapQuestionStore
from ..ports.transactions import ReadTransaction, WriteTransaction
from ..transactions import assert_external_io_allowed
from .ai_calls import AICallRunner
from .documents import load_knowledge
from .knowledge import FactLifecycleService

#: How many existing facts are sent as wording examples for a drafted fact.
_EXAMPLE_COUNT = 3


@dataclass(frozen=True)
class PreparedGapQuestions:
    """One question set, computed but not written."""

    job_analysis_id: str
    language: str
    questions: tuple[tuple[Requirement, str], ...]


@dataclass(frozen=True)
class PreparedGapFact:
    """One fact drafted from one answer and checked, but not written."""

    question: GapQuestionRecord
    answer: str
    payload: dict[str, object]


def _analysis_source(
    tx: ReadTransaction,
    analyses: AnalysisContextSourceReader,
    actor: Actor,
    application_id: str,
    job_analysis_id: str,
) -> AnalysisContextSource:
    """The analysis, refused unless it is this Application's and the Application is live."""
    source = analyses.analysis_context_source(tx, job_analysis_id, actor.user_id)
    if source.application_id != application_id:
        raise LineageBroken(
            f"job analysis {job_analysis_id} does not belong to application {application_id}"
        )
    if source.deleted_at is not None:
        raise StateConflict(f"application is deleted: {application_id}")
    return source


def _canonical_tags(knowledge: Knowledge) -> list[str]:
    return sorted(
        {
            tag
            for fact in knowledge.facts.facts.values()
            if fact.status is FactStatus.CANONICAL
            for tag in fact.tags
        }
    )


def _examples(knowledge: Knowledge) -> list[dict[str, object]]:
    """A few canonical facts from the source a drafted fact is filed in, for shape."""
    picked: list[dict[str, object]] = []
    for fact in knowledge.facts.facts.values():
        if fact.status is not FactStatus.CANONICAL or fact.resume_style not in {"bullet", "item"}:
            continue
        try:
            if source_name_of(fact) != GAP_FACT_SOURCE:
                continue
        except ValueError:
            continue
        picked.append(
            {
                "meaning": fact.meaning,
                "renderings": dict(fact.renderings),
                "tags": list(fact.tags),
                "resume_style": fact.resume_style,
            }
        )
        if len(picked) == _EXAMPLE_COUNT:
            break
    return picked


def _provenance(question: GapQuestionRecord, answer: str) -> str:
    """The fact's evidence: the user's own answer, verbatim, and what it answered."""
    return (
        "Drafted by AI from the user's own answer to a gap question "
        f"(application {question.application_id}, requirement {question.requirement_id}: "
        f'"{question.requirement_text}"). Question: {question.question} '
        f"Answer: {answer}"
    )


class GapQuestionActivation:
    """What the two Operations write, in the runner's activation scope.

    Opens no scope of its own: the runner locked the Application and owns the
    transaction, so the questions, or the fact and the answer beside it, commit
    with the Operation's completion or not at all.
    """

    def __init__(
        self,
        store: GapQuestionStore,
        analyses: AnalysisContextSourceReader,
        facts: FactLifecycleService,
    ):
        self.store = store
        self.analyses = analyses
        self.facts = facts

    def verify_question_sources(
        self, tx: ReadTransaction, owner: Actor, command: AskGapQuestionsCommand
    ) -> None:
        _analysis_source(tx, self.analyses, owner, command.application_id, command.job_analysis_id)

    def verify_answer_sources(
        self, tx: ReadTransaction, owner: Actor, command: DraftGapFactCommand
    ) -> GapQuestionRecord:
        question = self.store.question(
            tx, command.application_id, owner.user_id, command.gap_question_id
        )
        _analysis_source(tx, self.analyses, owner, command.application_id, question.job_analysis_id)
        answers = self.store.answers(tx, command.application_id, owner.user_id, [question.id])
        if question.id in answers:
            raise StateConflict(f"gap question already has an outcome: {question.id}")
        return question

    def activate_questions(
        self,
        tx: WriteTransaction,
        owner: Actor,
        command: AskGapQuestionsCommand,
        prepared: PreparedGapQuestions,
        operation_id: str,
    ) -> list[str]:
        now = utc_now()
        records = [
            GapQuestionRecord(
                id=new_id(),
                application_id=command.application_id,
                job_analysis_id=prepared.job_analysis_id,
                operation_id=operation_id,
                ordinal=ordinal,
                requirement_id=requirement.requirement_id,
                requirement_text=requirement.text,
                importance=requirement.importance,
                coverage=requirement.coverage,
                language=prepared.language,
                question=question,
                created_at=now,
            )
            for ordinal, (requirement, question) in enumerate(prepared.questions, start=1)
        ]
        self.store.insert_questions(tx, command.application_id, owner.user_id, records)
        return [record.id for record in records]

    def activate_fact(
        self,
        tx: WriteTransaction,
        owner: Actor,
        command: DraftGapFactCommand,
        prepared: PreparedGapFact,
        operation_id: str,
    ) -> str:
        question = self.verify_answer_sources(tx, owner, command)
        fact_id = new_id()
        self.facts.add_fact_in(
            tx,
            owner,
            GAP_FACT_SOURCE,
            {**prepared.payload, "fact_id": fact_id},
            reason=f"drafted from the answer to gap question {question.id}",
            application_id=command.application_id,
        )
        self.store.record_answer(
            tx,
            command.application_id,
            owner.user_id,
            GapAnswerRecord(
                gap_question_id=question.id,
                outcome="answered",
                answer=prepared.answer,
                fact_id=fact_id,
                operation_id=operation_id,
                created_at=utc_now(),
            ),
        )
        return fact_id


class GapQuestionService:
    """Queue-time checks, provider preparation, the read, and the skip command."""

    def __init__(
        self,
        *,
        transactions: TransactionManager,
        store: GapQuestionStore,
        analyses: AnalysisContextSourceReader,
        knowledge: AnalysisKnowledgeSource,
        ai_calls: AICallRunner,
        provider: AIProvider | None,
        activation: GapQuestionActivation,
    ):
        self.transactions = transactions
        self.store = store
        self.analyses = analyses
        self._knowledge = knowledge
        self.ai_calls = ai_calls
        self._provider = provider
        self.activation = activation

    @property
    def provider(self) -> AIProvider:
        if self._provider is None:
            raise ProviderNotConfigured("AI mode was requested but no provider is configured")
        return self._provider

    # Queue-time checks.

    def question_targets(
        self, actor: Actor, application_id: str, job_analysis_id: str
    ) -> list[Requirement]:
        """The requirements a new set would ask about; refused unless there are any.

        The analysis must be the Application's newest: the read shows the newest
        analysis's questions, so a set asked about an older one would be invisible.
        """
        with self.transactions.read() as tx:
            source = _analysis_source(tx, self.analyses, actor, application_id, job_analysis_id)
            latest = self.store.latest_analysis_id(tx, application_id, actor.user_id)
        if latest != job_analysis_id:
            raise StateConflict(
                f"a newer analysis exists: expected {job_analysis_id}, found {latest}"
            )
        targets = gap_requirements(source.analysis)
        if not targets:
            raise PreconditionFailed(
                "the analysis has no unsupported or partial requirement to ask about"
            )
        return targets

    def question_source(
        self, actor: Actor, application_id: str, gap_question_id: str
    ) -> GapQuestionRecord:
        """The question an answer is for, refused once it has an outcome."""
        with self.transactions.read() as tx:
            question = self.store.question(tx, application_id, actor.user_id, gap_question_id)
            answers = self.store.answers(tx, application_id, actor.user_id, [question.id])
        if question.id in answers:
            raise StateConflict(f"gap question already has an outcome: {question.id}")
        return question

    # Preparation, outside every scope.

    def prepare_questions(
        self,
        actor: Actor,
        command: AskGapQuestionsCommand,
        *,
        operation_id: str,
        still_owned: Callable[[], bool] = lambda: True,
    ) -> PreparedGapQuestions:
        assert_external_io_allowed("gap question preparation")
        with self.transactions.read() as tx:
            source = _analysis_source(
                tx, self.analyses, actor, command.application_id, command.job_analysis_id
            )
        analysis: JobAnalysis = source.analysis
        targets = gap_requirements(analysis)
        if not targets:
            raise PreconditionFailed(
                "the analysis has no unsupported or partial requirement to ask about"
            )
        knowledge = load_knowledge(self._knowledge, actor)
        facts = knowledge.facts.facts
        context = GapQuestionsContext(
            language=analysis.language,
            track=analysis.track.value,
            requirements=[
                {
                    "requirement_id": requirement.requirement_id,
                    "text": requirement.text,
                    "importance": requirement.importance,
                    "coverage": requirement.coverage,
                    "shortfall_reason": requirement.shortfall_reason,
                    "known_facts": [
                        {"fact_id": fact_id, "meaning": facts[fact_id].meaning}
                        for fact_id in requirement.supporting_fact_ids
                        if fact_id in facts and facts[fact_id].status is FactStatus.CANONICAL
                    ],
                }
                for requirement in targets
            ],
        )
        recorded = self.ai_calls.run(
            operation_id,
            lambda: self.provider.propose_gap_questions(
                context, model=command.model, reasoning_effort=command.reasoning_effort
            ),
            knowledge_context_hash=knowledge.context_hash(),
            still_owned=still_owned,
        )
        asked: dict[str, str] = {}
        for proposed in recorded.proposal.questions:
            text = proposed.question.strip()
            if proposed.requirement_id in asked or not text or len(text) > QUESTION_MAX_CHARACTERS:
                continue
            asked[proposed.requirement_id] = text
        questions = tuple(
            (requirement, asked[requirement.requirement_id])
            for requirement in targets
            if requirement.requirement_id in asked
        )
        if not questions:
            raise ProviderInvalidOutput("the provider asked no usable question")
        return PreparedGapQuestions(
            job_analysis_id=command.job_analysis_id,
            language=analysis.language,
            questions=questions,
        )

    def prepare_fact(
        self,
        actor: Actor,
        command: DraftGapFactCommand,
        *,
        operation_id: str,
        still_owned: Callable[[], bool] = lambda: True,
    ) -> PreparedGapFact:
        assert_external_io_allowed("gap fact preparation")
        answer = command.answer.strip()
        if not answer:
            raise PreconditionFailed("an answer must say something")
        with self.transactions.read() as tx:
            question = self.activation.verify_answer_sources(tx, actor, command)
            source = _analysis_source(
                tx, self.analyses, actor, command.application_id, question.job_analysis_id
            )
        track = source.analysis.track.value
        knowledge = load_knowledge(self._knowledge, actor)
        vocabulary = _canonical_tags(knowledge)
        context = FactFromAnswerContext(
            language=question.language,
            track=track,
            requirement=question.requirement_text,
            question=question.question,
            answer=answer,
            tag_vocabulary=vocabulary,
            examples=_examples(knowledge),
        )
        recorded = self.ai_calls.run(
            operation_id,
            lambda: self.provider.draft_fact_from_answer(
                context, model=command.model, reasoning_effort=command.reasoning_effort
            ),
            knowledge_context_hash=knowledge.context_hash(),
            still_owned=still_owned,
        )
        proposal = recorded.proposal
        meaning = proposal.meaning.strip()
        english = proposal.english.strip()
        hebrew = (proposal.hebrew or "").strip() or None
        wording = [meaning, english, *([hebrew] if hebrew else [])]
        problems, unsupported = fact_draft_problems(answer, wording)
        if question.language == "he" and hebrew is None:
            problems.append("missing-rendering")
        if problems:
            raise FactDraftRejected(
                "the drafted fact says something the answer does not",
                reason=FactDraftReason(problems=problems, unsupported=unsupported),
            )
        renderings = {"en": english, **({"he": hebrew} if hebrew else {})}
        return PreparedGapFact(
            question=question,
            answer=answer,
            payload={
                "meaning": meaning,
                "renderings": renderings,
                "tags": fact_tags(proposal.tags, vocabulary, track),
                "provenance": _provenance(question, answer),
                "resume_style": proposal.resume_style,
                "effective_dates": None,
                "replaces": None,
            },
        )

    # The read and the skip.

    def read(self, actor: Actor, application_id: str) -> GapQuestionSetView:
        """The newest question set of the newest analysis, with each question's outcome."""
        with self.transactions.read() as tx:
            analysis_id = self.store.latest_analysis_id(tx, application_id, actor.user_id)
            questions = (
                self.store.latest_question_set(tx, application_id, actor.user_id, analysis_id)
                if analysis_id is not None
                else []
            )
            ids = [question.id for question in questions]
            answers = self.store.answers(tx, application_id, actor.user_id, ids)
            drafts = self.store.draft_operations(tx, application_id, actor.user_id, ids)
            knowledge = load_knowledge(self._knowledge, actor, tx) if answers else None
        facts: dict[str, Fact] = knowledge.facts.facts if knowledge is not None else {}
        views = []
        for question in questions:
            outcome = answers.get(question.id)
            draft = drafts.get(question.id)
            live = draft is not None and draft.status in {
                OperationStatus.QUEUED,
                OperationStatus.RUNNING,
            }
            if outcome is not None:
                state = outcome.outcome
            elif live:
                state = "drafting"
            else:
                state = "open"
            views.append(
                GapQuestionView(
                    id=question.id,
                    ordinal=question.ordinal,
                    requirement_id=question.requirement_id,
                    requirement_text=question.requirement_text,
                    importance=question.importance,
                    coverage=question.coverage,
                    question=question.question,
                    state=state,
                    answer=outcome.answer if outcome is not None else None,
                    fact=(
                        facts.get(outcome.fact_id)
                        if outcome is not None and outcome.fact_id is not None
                        else None
                    ),
                    draft_operation=as_operation_view(draft) if draft is not None else None,
                )
            )
        first = questions[0] if questions else None
        return GapQuestionSetView(
            application_id=application_id,
            job_analysis_id=analysis_id,
            operation_id=first.operation_id if first is not None else None,
            language=first.language if first is not None else None,
            asked_at=first.created_at if first is not None else None,
            questions=views,
        )

    def skip(self, actor: Actor, application_id: str, gap_question_id: str) -> GapQuestionSetView:
        """Record that the user declined to answer; final, like an answer."""
        with self.transactions.write() as tx:
            question = self.store.question(tx, application_id, actor.user_id, gap_question_id)
            _analysis_source(tx, self.analyses, actor, application_id, question.job_analysis_id)
            self.store.record_answer(
                tx,
                application_id,
                actor.user_id,
                GapAnswerRecord(
                    gap_question_id=question.id,
                    outcome="skipped",
                    answer=None,
                    fact_id=None,
                    operation_id=None,
                    created_at=utc_now(),
                ),
            )
        return self.read(actor, application_id)


__all__ = [
    "GapQuestionActivation",
    "GapQuestionService",
    "PreparedGapFact",
    "PreparedGapQuestions",
]
