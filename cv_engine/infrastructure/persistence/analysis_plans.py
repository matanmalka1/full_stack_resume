"""Stateless transaction-token adapter for analysis writes and matching configuration."""

from __future__ import annotations

from sqlalchemy import select, update

from ...application.errors import UnknownRecord
from ...application.ports.transactions import WriteTransaction
from ...domain.contracts.analysis import JobAnalysis
from ...util import utc_now
from .analysis_sql import (
    _refuse_matching_context_operation,
    _save_analysis,
)
from .connection import SqlAlchemyTransactionManager
from .ownership import owned
from .tables import applications


class SqlAlchemyAnalysisPlanRepository:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def lock_application(self, tx: WriteTransaction, application_id: str, user_id: str) -> None:
        locked = (
            self._transactions.connection_for(tx, access="write")
            .execute(
                select(applications.c.id).where(owned(application_id, user_id)).with_for_update()
            )
            .scalar_one_or_none()
        )
        if locked is None:
            raise UnknownRecord(f"unknown application: {application_id}")

    def save_analysis(
        self,
        tx: WriteTransaction,
        application_id: str,
        user_id: str,
        job_text_hash: str,
        analysis: JobAnalysis,
        *,
        provider: str,
        model: str,
        expected_analysis_id: str | None = None,
        refuse_matching_context_operation: bool = False,
    ) -> str:
        self.lock_application(tx, application_id, user_id)
        return _save_analysis(
            self._transactions.connection_for(tx, access="write"),
            application_id,
            job_text_hash,
            analysis,
            provider=provider,
            model=model,
            expected_analysis_id=expected_analysis_id,
            refuse_matching_context_operation=refuse_matching_context_operation,
        )

    def refuse_matching_context_operation(self, tx: WriteTransaction, application_id: str) -> None:
        _refuse_matching_context_operation(
            self._transactions.connection_for(tx, access="write"), application_id
        )

    def set_normalized_role(
        self, tx: WriteTransaction, application_id: str, user_id: str, normalized_role: str
    ) -> None:
        result = self._transactions.connection_for(tx, access="write").execute(
            update(applications)
            .where(owned(application_id, user_id))
            .values(normalized_role=normalized_role, updated_at=utc_now())
        )
        if result.rowcount != 1:
            raise UnknownRecord(application_id)
