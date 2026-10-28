"""Gap questions and their outcomes, as the gap-question service reads and writes them.

Every method names the Application and its owner: a question is reached only
through an Application already resolved for this user (architecture §18.3), so
another user's question is the same miss as one that does not exist.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from ..operations import PersistedOperation
from .transactions import ReadTransaction, WriteTransaction


@dataclass(frozen=True)
class GapQuestionRecord:
    id: str
    application_id: str
    job_analysis_id: str
    operation_id: str
    ordinal: int
    requirement_id: str
    requirement_text: str
    importance: str
    coverage: str
    language: str
    question: str
    created_at: str


@dataclass(frozen=True)
class GapAnswerRecord:
    gap_question_id: str
    outcome: Literal["answered", "skipped"]
    answer: str | None
    fact_id: str | None
    operation_id: str | None
    created_at: str


class GapQuestionStore(Protocol):
    def latest_analysis_id(
        self, tx: ReadTransaction, application_id: str, user_id: str
    ) -> str | None:
        """The Application's newest analysis; `UnknownRecord` unless it is this user's."""
        ...

    def latest_question_set(
        self, tx: ReadTransaction, application_id: str, user_id: str, job_analysis_id: str
    ) -> list[GapQuestionRecord]:
        """The questions the newest `ask_gap_questions` for that analysis asked."""
        ...

    def question(
        self, tx: ReadTransaction, application_id: str, user_id: str, gap_question_id: str
    ) -> GapQuestionRecord:
        """One question of this user's Application, or `UnknownRecord`."""
        ...

    def answers(
        self,
        tx: ReadTransaction,
        application_id: str,
        user_id: str,
        gap_question_ids: Sequence[str],
    ) -> dict[str, GapAnswerRecord]: ...

    def draft_operations(
        self,
        tx: ReadTransaction,
        application_id: str,
        user_id: str,
        gap_question_ids: Sequence[str],
    ) -> dict[str, PersistedOperation]:
        """The newest `draft_gap_fact` Operation for each question that has one."""
        ...

    def insert_questions(
        self,
        tx: WriteTransaction,
        application_id: str,
        user_id: str,
        records: Sequence[GapQuestionRecord],
    ) -> None: ...

    def record_answer(
        self,
        tx: WriteTransaction,
        application_id: str,
        user_id: str,
        record: GapAnswerRecord,
    ) -> None:
        """Append the one outcome of a question; `StateConflict` if it has one already."""
        ...
