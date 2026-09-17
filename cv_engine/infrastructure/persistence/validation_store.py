from __future__ import annotations

from typing import Any

from ...application.ports.transactions import ReadTransaction, WriteTransaction
from ...domain.contracts.records import ValidationRunLineage
from ...domain.contracts.validation import ValidationReport
from .artifacts_sql import (
    _latest_validation_for_working_draft,
    _record_validation,
    _validation_for_artifact,
    _validation_lineage,
    _validation_report,
    _validation_run,
)
from .connection import SqlAlchemyTransactionManager


class SqlAlchemyValidationRepository:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def record_validation(
        self,
        tx: WriteTransaction,
        application_id: str,
        phase: str,
        report: ValidationReport,
        artifact_version_id: str | None = None,
        *,
        lineage: ValidationRunLineage | None = None,
    ) -> str:
        connection = self._transactions.connection_for(tx, access="write")
        return _record_validation(
            connection, application_id, phase, report, artifact_version_id, lineage=lineage
        )

    def validation_lineage(self, tx: ReadTransaction, validation_id: str) -> ValidationRunLineage:
        connection = self._transactions.connection_for(tx)
        return _validation_lineage(connection, validation_id)

    def latest_validation_for_working_draft(
        self, tx: ReadTransaction, working_draft_id: str
    ) -> dict[str, Any] | None:
        connection = self._transactions.connection_for(tx)
        return _latest_validation_for_working_draft(connection, working_draft_id)

    def validation_for_artifact(
        self, tx: ReadTransaction, application_id: str, phase: str, artifact_version_id: str
    ) -> ValidationReport:
        connection = self._transactions.connection_for(tx)
        return _validation_for_artifact(connection, application_id, phase, artifact_version_id)

    def validation_report(self, tx: ReadTransaction, validation_id: str) -> ValidationReport:
        connection = self._transactions.connection_for(tx)
        return _validation_report(connection, validation_id)

    def validation_run(self, tx: ReadTransaction, validation_id: str) -> dict[str, Any]:
        connection = self._transactions.connection_for(tx)
        return _validation_run(connection, validation_id)
