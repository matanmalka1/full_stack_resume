"""Stateless transaction-token adapter for analysis writes and matching configuration."""

from __future__ import annotations

from sqlalchemy import update

from ...application.errors import UnknownRecord
from ...application.ports.transactions import WriteTransaction
from ...domain.contracts.analysis import JobAnalysis
from ...util import utc_now
from .analysis_sql import (
    _lock_application,
    _refuse_matching_context_operation,
    _save_analysis,
)
from .connection import SqlAlchemyTransactionManager
from .tables import applications


class SqlAlchemyAnalysisPlanRepository:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def lock_application(self, tx: WriteTransaction, application_id: str) -> None:
        _lock_application(self._transactions.connection_for(tx, access="write"), application_id)

    def save_analysis(
        self,
        tx: WriteTransaction,
        application_id: str,
        job_text_hash: str,
        analysis: JobAnalysis,
        *,
        provider: str,
        model: str,
        expected_analysis_id: str | None = None,
        refuse_matching_context_operation: bool = False,
    ) -> str:
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
        self, tx: WriteTransaction, application_id: str, normalized_role: str
    ) -> None:
        result = self._transactions.connection_for(tx, access="write").execute(
            update(applications)
            .where(applications.c.id == application_id)
            .values(normalized_role=normalized_role, updated_at=utc_now())
        )
        if result.rowcount != 1:
            raise UnknownRecord(application_id)
