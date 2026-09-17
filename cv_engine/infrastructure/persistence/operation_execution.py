"""Runner-owned Operation execution persistence."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

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
from .tables import operation_outputs, operation_resource_leases, operations

_RESOURCE_CAPACITY = {"application_mutation": 1, "render_browser": 1, "ai": 2}


def _expiry(now: str, lease_seconds: int) -> str:
    if lease_seconds < 1:
        raise ValueError("lease_seconds must be positive")
    return (datetime.fromisoformat(now) + timedelta(seconds=lease_seconds)).isoformat()


def _waiting_phase(resource_kind: str) -> tuple[str, str]:
    if resource_kind == "render_browser":
        return OperationPhase.WAITING_FOR_RENDER_SLOT.value, "Waiting for render slot."
    if resource_kind == "ai":
        return OperationPhase.WAITING_FOR_AI_SLOT.value, "Waiting for AI slot."
    return OperationPhase.WAITING_FOR_APPLICATION.value, "Waiting for application operation."


def _release_acquired(connection: Connection, acquired: list[tuple[str, str, int]]) -> None:
    for kind, key, slot in acquired:
        connection.execute(
            delete(operation_resource_leases).where(
                operation_resource_leases.c.resource_kind == kind,
                operation_resource_leases.c.resource_key == key,
                operation_resource_leases.c.slot == slot,
            )
        )


class SqlAlchemyOperationExecutionStore:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def lock_application(self, tx: WriteTransaction, application_id: str) -> None:
        _lock_application(self._transactions.connection_for(tx, access="write"), application_id)

    def claim_operation(
        self,
        tx: WriteTransaction,
        operation_id: str,
        *,
        runner_id: str,
        lease_seconds: int = 30,
        now: str | None = None,
    ) -> PersistedOperation | None:
        timestamp = now or utc_now()
        expires_at = _expiry(timestamp, lease_seconds)
        connection = self._transactions.connection_for(tx, access="write")
        row = (
            connection.execute(
                select(operations)
                .where(operations.c.id == operation_id)
                .with_for_update(skip_locked=True)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            # A concurrent runner may already hold this row. Waiting for it at
            # REPEATABLE READ turns the normal claim race into PostgreSQL's
            # ``could not serialize access due to concurrent update``. A
            # skipped existing row is simply a lost claim; only an actually
            # unknown identifier is an error.
            exists = connection.execute(
                select(operations.c.id).where(operations.c.id == operation_id)
            ).scalar_one_or_none()
            if exists is None:
                raise UnknownRecord("operation does not exist")
            return None
        if row["status"] != OperationStatus.QUEUED.value:
            return None
        if row["next_attempt_at"] is not None and row["next_attempt_at"] > timestamp:
            return None
        acquired: list[tuple[str, str, int]] = []
        blocked_kind = None
        for resource in row["resources_json"]:
            kind, key = resource["kind"], resource["key"]
            for slot in range(_RESOURCE_CAPACITY[kind]):
                try:
                    with connection.begin_nested():
                        connection.execute(
                            insert(operation_resource_leases).values(
                                resource_kind=kind,
                                resource_key=key,
                                slot=slot,
                                operation_id=operation_id,
                                lease_owner=runner_id,
                                lease_expires_at=expires_at,
                                heartbeat_at=timestamp,
                            )
                        )
                except IntegrityError:
                    continue
                acquired.append((kind, key, slot))
                break
            else:
                blocked_kind = kind
                break
        if blocked_kind is not None:
            _release_acquired(connection, acquired)
            phase, message = _waiting_phase(blocked_kind)
            connection.execute(
                update(operations)
                .where(operations.c.id == operation_id, operations.c.status == "queued")
                .values(phase=phase, message=message)
            )
            return None
        changed = connection.execute(
            update(operations)
            .where(operations.c.id == operation_id, operations.c.status == "queued")
            .values(
                status="running",
                phase=OperationPhase.PRE_EXECUTION_CHECK.value,
                message="",
                started_at=timestamp,
                lease_owner=runner_id,
                lease_expires_at=expires_at,
                heartbeat_at=timestamp,
            )
        ).rowcount
        if changed != 1:
            _release_acquired(connection, acquired)
            return None
        current = (
            connection.execute(select(operations).where(operations.c.id == operation_id))
            .mappings()
            .one_or_none()
        )
        return _operation_record(current, _outputs(connection, operation_id))

    def claim_next_operation(
        self,
        tx: WriteTransaction,
        *,
        runner_id: str,
        lease_seconds: int = 30,
        now: str | None = None,
    ) -> PersistedOperation | None:
        timestamp = now or utc_now()
        connection = self._transactions.connection_for(tx, access="write")
        candidates = (
            connection.execute(
                select(operations.c.id)
                .where(
                    operations.c.status == "queued",
                    operations.c.next_attempt_at.is_(None)
                    | (operations.c.next_attempt_at <= timestamp),
                )
                .order_by(operations.c.created_at, operations.c.id)
            )
            .scalars()
            .all()
        )
        for operation_id in candidates:
            claimed = self.claim_operation(
                tx, operation_id, runner_id=runner_id, lease_seconds=lease_seconds, now=timestamp
            )
            if claimed is not None:
                return claimed
        return None

    def heartbeat_operation(
        self,
        tx: WriteTransaction,
        operation_id: str,
        *,
        runner_id: str,
        lease_seconds: int = 30,
        now: str | None = None,
    ) -> None:
        timestamp = now or utc_now()
        expires_at = _expiry(timestamp, lease_seconds)
        connection = self._transactions.connection_for(tx, access="write")
        changed = connection.execute(
            update(operations)
            .where(
                operations.c.id == operation_id,
                operations.c.status == "running",
                operations.c.lease_owner == runner_id,
            )
            .values(heartbeat_at=timestamp, lease_expires_at=expires_at)
        ).rowcount
        if changed != 1:
            raise StateConflict("operation lease is not owned by this runner")
        leases = connection.execute(
            update(operation_resource_leases)
            .where(
                operation_resource_leases.c.operation_id == operation_id,
                operation_resource_leases.c.lease_owner == runner_id,
            )
            .values(heartbeat_at=timestamp, lease_expires_at=expires_at)
        ).rowcount
        if leases < 1:
            raise StateConflict("operation resource leases are missing")

    def interrupt_expired_operations(
        self, tx: WriteTransaction, *, now: str | None = None
    ) -> list[str]:
        timestamp = now or utc_now()
        connection = self._transactions.connection_for(tx, access="write")
        identifiers = list(
            connection.execute(
                select(operations.c.id)
                .where(
                    operations.c.status.in_(("queued", "running")),
                    operations.c.lease_expires_at.is_not(None),
                    operations.c.lease_expires_at <= timestamp,
                )
                .order_by(operations.c.created_at, operations.c.id)
            ).scalars()
        )
        for identifier in identifiers:
            _release(connection, identifier)
            connection.execute(
                update(operations)
                .where(
                    operations.c.id == identifier,
                    operations.c.status.in_(("queued", "running")),
                )
                .values(
                    status="interrupted",
                    phase="completed",
                    message="Interrupted after runner lease expired.",
                    finished_at=timestamp,
                    lease_owner=None,
                    lease_expires_at=None,
                    heartbeat_at=None,
                )
            )
        return identifiers

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

    def record_operation_attempt(
        self,
        tx: WriteTransaction,
        operation_id: str,
        *,
        runner_id: str,
        retry_at: str | None = None,
    ) -> int:
        connection = self._transactions.connection_for(tx, access="write")
        changed = connection.execute(
            update(operations)
            .where(
                operations.c.id == operation_id,
                operations.c.status == "running",
                operations.c.lease_owner == runner_id,
            )
            .values(
                attempts_completed=operations.c.attempts_completed + 1,
                phase=OperationPhase.RETRY_WAIT.value,
                next_attempt_at=retry_at,
            )
        ).rowcount
        if changed != 1:
            raise StateConflict("operation lease is not owned by this runner")
        return connection.execute(
            select(operations.c.attempts_completed).where(operations.c.id == operation_id)
        ).scalar_one()

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

    def fail_operation(
        self,
        tx: WriteTransaction,
        operation_id: str,
        code: OperationFailureCode,
        safe_detail: str,
        *,
        runner_id: str,
        technical_log_reference: str | None = None,
        now: str | None = None,
    ) -> PersistedOperation:
        timestamp = now or utc_now()
        connection = self._transactions.connection_for(tx, access="write")
        _release(connection, operation_id)
        changed = connection.execute(
            update(operations)
            .where(
                operations.c.id == operation_id,
                operations.c.status == "running",
                operations.c.lease_owner == runner_id,
            )
            .values(
                status="failed",
                phase="completed",
                message="",
                finished_at=timestamp,
                failure_code=code.value,
                safe_failure_detail=safe_detail,
                technical_log_reference=technical_log_reference,
                attempts_completed=operations.c.attempts_completed + 1,
                lease_owner=None,
                lease_expires_at=None,
                heartbeat_at=None,
                next_attempt_at=None,
            )
        ).rowcount
        if changed != 1:
            raise StateConflict("operation lease is not owned by this runner")
        current = (
            connection.execute(select(operations).where(operations.c.id == operation_id))
            .mappings()
            .one_or_none()
        )
        return _operation_record(current, _outputs(connection, operation_id))
