"""Runner-owned operation activation persistence, without claiming/client lifecycle."""

from __future__ import annotations

from sqlalchemy import insert, select, update

from ...application.errors import StateConflict, UnknownRecord
from ...application.operations import (
    OperationFailureCode,
    OperationPhase,
    OperationStatus,
    PersistedOperation,
)
from ...application.ports.transactions import ReadTransaction, WriteTransaction
from ...util import new_id, utc_now
from .analysis_sql import _lock_application
from .connection import SqlAlchemyTransactionManager
from .operation_sql import _operation_record, _outputs, _release
from .tables import operation_outputs, operations


class SqlAlchemyOperationActivationStore:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def lock_application(self, tx: WriteTransaction, application_id: str) -> None:
        _lock_application(self._transactions.connection_for(tx, access="write"), application_id)

    def operation(self, tx: ReadTransaction, operation_id: str) -> PersistedOperation:
        connection = self._transactions.connection_for(tx)
        row = (
            connection.execute(select(operations).where(operations.c.id == operation_id))
            .mappings()
            .one_or_none()
        )
        return _operation_record(row, _outputs(connection, operation_id))

    def set_operation_phase(
        self,
        tx: WriteTransaction,
        operation_id: str,
        phase: OperationPhase,
        *,
        runner_id: str,
        message: str = "",
    ) -> None:
        connection = self._transactions.connection_for(tx, access="write")
        changed = connection.execute(
            update(operations)
            .where(
                operations.c.id == operation_id,
                operations.c.status == "running",
                operations.c.lease_owner == runner_id,
            )
            .values(phase=phase.value, message=message)
        ).rowcount
        if changed != 1:
            raise StateConflict("operation lease is not owned by this runner")

    def cancellation_requested(self, tx: ReadTransaction, operation_id: str) -> bool:
        connection = self._transactions.connection_for(tx)
        row = (
            connection.execute(
                select(operations.c.cancellation_requested_at).where(
                    operations.c.id == operation_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord("operation does not exist")
        return row["cancellation_requested_at"] is not None

    def record_operation_output(
        self,
        tx: WriteTransaction,
        operation_id: str,
        output_type: str,
        output_id: str,
        *,
        active: bool = False,
        created_at: str | None = None,
    ) -> str:
        timestamp = created_at or utc_now()
        identifier = new_id()
        connection = self._transactions.connection_for(tx, access="write")
        operation = (
            connection.execute(
                select(operations.c.status, operations.c.cancellation_requested_at).where(
                    operations.c.id == operation_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if operation is None:
            raise UnknownRecord("operation does not exist")
        if active and (
            operation["status"] != OperationStatus.RUNNING.value
            or operation["cancellation_requested_at"] is not None
        ):
            raise StateConflict("operation output cannot be activated")
        existing = connection.execute(
            select(operation_outputs.c.id).where(
                operation_outputs.c.operation_id == operation_id,
                operation_outputs.c.output_type == output_type,
                operation_outputs.c.output_id == output_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        connection.execute(
            insert(operation_outputs).values(
                id=identifier,
                operation_id=operation_id,
                output_type=output_type,
                output_id=output_id,
                active=active,
                created_at=timestamp,
                activated_at=timestamp if active else None,
            )
        )
        return identifier

    def activate_operation_output(
        self,
        tx: WriteTransaction,
        operation_id: str,
        output_type: str,
        output_id: str,
        *,
        now: str | None = None,
    ) -> None:
        timestamp = now or utc_now()
        connection = self._transactions.connection_for(tx, access="write")
        changed = connection.execute(
            update(operation_outputs)
            .where(
                operation_outputs.c.operation_id == operation_id,
                operation_outputs.c.output_type == output_type,
                operation_outputs.c.output_id == output_id,
                operation_outputs.c.active.is_(False),
            )
            .values(active=True, activated_at=timestamp)
        ).rowcount
        if changed != 1:
            raise StateConflict("operation output cannot be activated")

    def complete_operation(
        self,
        tx: WriteTransaction,
        operation_id: str,
        *,
        runner_id: str,
        now: str | None = None,
    ) -> PersistedOperation:
        timestamp = now or utc_now()
        connection = self._transactions.connection_for(tx, access="write")
        row = (
            connection.execute(
                select(operations).where(
                    operations.c.id == operation_id,
                    operations.c.status == "running",
                    operations.c.lease_owner == runner_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise StateConflict("operation lease is not owned by this runner")
        _release(connection, operation_id)
        if row["cancellation_requested_at"] is not None:
            status = OperationStatus.CANCELLED.value
            failure_code = OperationFailureCode.CANCELLED_BEFORE_ACTIVATION.value
            message = "Cancelled before output activation."
        else:
            status = OperationStatus.SUCCEEDED.value
            failure_code = None
            message = ""
        connection.execute(
            update(operations)
            .where(
                operations.c.id == operation_id,
                operations.c.status == "running",
                operations.c.lease_owner == runner_id,
            )
            .values(
                status=status,
                phase="completed",
                message=message,
                finished_at=timestamp,
                failure_code=failure_code,
                safe_failure_detail=message or None,
                lease_owner=None,
                lease_expires_at=None,
                heartbeat_at=None,
                next_attempt_at=None,
                attempts_completed=operations.c.attempts_completed + 1,
            )
        )
        current = (
            connection.execute(select(operations).where(operations.c.id == operation_id))
            .mappings()
            .one_or_none()
        )
        return _operation_record(current, _outputs(connection, operation_id))
