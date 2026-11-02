"""Stateless transaction-token persistence for gap questions and their outcomes."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import insert, select

from ...application.errors import StateConflict, UnknownRecord
from ...application.operations import OperationType, PersistedOperation
from ...application.ports.gap_questions import GapAnswerRecord, GapQuestionRecord
from ...application.ports.transactions import ReadTransaction, WriteTransaction
from ...util import new_id
from .connection import SqlAlchemyTransactionManager
from .operation_sql import _operation_record
from .ownership import owned
from .tables import applications, gap_answers, gap_questions, job_analyses, operations


def _question(row: Any) -> GapQuestionRecord:
    return GapQuestionRecord(**{name: row[name] for name in GapQuestionRecord.__dataclass_fields__})


def _answer(row: Any) -> GapAnswerRecord:
    return GapAnswerRecord(**{name: row[name] for name in GapAnswerRecord.__dataclass_fields__})


class SqlAlchemyGapQuestionStore:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def _require_owned(self, connection, application_id: str, user_id: str, *, lock=False):
        statement = select(applications.c.id).where(owned(application_id, user_id))
        if lock:
            statement = statement.with_for_update()
        if connection.execute(statement).scalar_one_or_none() is None:
            raise UnknownRecord(f"unknown application: {application_id}")

    @staticmethod
    def _owned_questions(application_id: str, user_id: str):
        """Questions joined to their Application's owner in the same query (§18.3)."""
        return (
            select(gap_questions)
            .join(applications, applications.c.id == gap_questions.c.application_id)
            .where(
                gap_questions.c.application_id == application_id,
                applications.c.user_id == user_id,
            )
        )

    def latest_analysis_id(
        self, tx: ReadTransaction, application_id: str, user_id: str
    ) -> str | None:
        connection = self._transactions.connection_for(tx)
        self._require_owned(connection, application_id, user_id)
        return connection.execute(
            select(job_analyses.c.id)
            .where(job_analyses.c.application_id == application_id)
            .order_by(job_analyses.c.version_number.desc())
            .limit(1)
        ).scalar_one_or_none()

    def latest_question_set(
        self, tx: ReadTransaction, application_id: str, user_id: str, job_analysis_id: str
    ) -> list[GapQuestionRecord]:
        connection = self._transactions.connection_for(tx)
        newest = connection.execute(
            self._owned_questions(application_id, user_id)
            .with_only_columns(gap_questions.c.operation_id)
            .where(gap_questions.c.job_analysis_id == job_analysis_id)
            .order_by(gap_questions.c.created_at.desc(), gap_questions.c.operation_id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if newest is None:
            return []
        rows = connection.execute(
            self._owned_questions(application_id, user_id)
            .where(gap_questions.c.operation_id == newest)
            .order_by(gap_questions.c.ordinal)
        ).mappings()
        return [_question(row) for row in rows]

    def question(
        self, tx: ReadTransaction, application_id: str, user_id: str, gap_question_id: str
    ) -> GapQuestionRecord:
        row = (
            self._transactions.connection_for(tx)
            .execute(
                self._owned_questions(application_id, user_id).where(
                    gap_questions.c.id == gap_question_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(f"unknown gap question: {gap_question_id}")
        return _question(row)

    def answers(
        self,
        tx: ReadTransaction,
        application_id: str,
        user_id: str,
        gap_question_ids: Sequence[str],
    ) -> dict[str, GapAnswerRecord]:
        if not gap_question_ids:
            return {}
        rows = (
            self._transactions.connection_for(tx)
            .execute(
                select(gap_answers)
                .join(applications, applications.c.id == gap_answers.c.application_id)
                .where(
                    gap_answers.c.application_id == application_id,
                    applications.c.user_id == user_id,
                    gap_answers.c.gap_question_id.in_(list(gap_question_ids)),
                )
            )
            .mappings()
        )
        return {row["gap_question_id"]: _answer(row) for row in rows}

    def draft_operations(
        self,
        tx: ReadTransaction,
        application_id: str,
        user_id: str,
        gap_question_ids: Sequence[str],
    ) -> dict[str, PersistedOperation]:
        if not gap_question_ids:
            return {}
        connection = self._transactions.connection_for(tx)
        question_id = operations.c.payload_json["gap_question_id"].astext
        rows = connection.execute(
            select(operations)
            .join(applications, applications.c.id == operations.c.application_id)
            .where(
                operations.c.application_id == application_id,
                applications.c.user_id == user_id,
                operations.c.operation_type == OperationType.DRAFT_GAP_FACT.value,
                question_id.in_(list(gap_question_ids)),
            )
            .order_by(operations.c.created_at.desc(), operations.c.id.desc())
        ).mappings()
        newest: dict[str, PersistedOperation] = {}
        for row in rows:
            key = row["payload_json"]["gap_question_id"]
            if key not in newest:
                newest[key] = _operation_record(row, connection)
        return newest

    def insert_questions(
        self,
        tx: WriteTransaction,
        application_id: str,
        user_id: str,
        records: Sequence[GapQuestionRecord],
    ) -> None:
        connection = self._transactions.connection_for(tx, access="write")
        self._require_owned(connection, application_id, user_id)
        if any(record.application_id != application_id for record in records):
            raise StateConflict("a gap question names another Application")
        if records:
            connection.execute(
                insert(gap_questions),
                [
                    {name: getattr(record, name) for name in GapQuestionRecord.__dataclass_fields__}
                    for record in records
                ],
            )

    def record_answer(
        self,
        tx: WriteTransaction,
        application_id: str,
        user_id: str,
        record: GapAnswerRecord,
    ) -> None:
        connection = self._transactions.connection_for(tx, access="write")
        # The Application lock serializes two outcomes for one question.
        self._require_owned(connection, application_id, user_id, lock=True)
        existing = connection.execute(
            select(gap_answers.c.id).where(gap_answers.c.gap_question_id == record.gap_question_id)
        ).scalar_one_or_none()
        if existing is not None:
            raise StateConflict(f"gap question already has an outcome: {record.gap_question_id}")
        connection.execute(
            insert(gap_answers).values(
                id=new_id(),
                application_id=application_id,
                **{name: getattr(record, name) for name in GapAnswerRecord.__dataclass_fields__},
            )
        )
