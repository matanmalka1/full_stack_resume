from __future__ import annotations

from sqlalchemy import delete, insert, select, update

from ...application.errors import IDEMPOTENCY_KEY_REUSED, StateConflict, UnknownRecord
from ...application.operations import (
    CreateOperation,
    OperationPhase,
    OperationStatus,
    PersistedOperation,
    required_operation_resources,
)
from ...application.ports.transactions import ReadTransaction, WriteTransaction
from ...util import utc_now
from .connection import SqlAlchemyTransactionManager
from .operation_sql import _operation_record, _outputs
from .tables import (
    applications,
    operation_resource_leases,
    operations,
)


class SqlAlchemyOperationClientStore:
    """Stateless SQL adapter for API-facing Operation commands."""

    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def application(self, tx: ReadTransaction, application_id: str) -> dict[str, object]:
        row = (
            self._transactions.connection_for(tx)
            .execute(select(applications).where(applications.c.id == application_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(application_id)
        return dict(row)

    def enqueue(
        self,
        tx: WriteTransaction,
        request: CreateOperation,
        *,
        operation_id: str,
        created_at: str | None = None,
    ) -> PersistedOperation:
        connection = self._transactions.connection_for(tx, access="write")
        timestamp = created_at or utc_now()
        application = (
            connection.execute(
                select(applications.c.id, applications.c.deleted_at)
                .where(applications.c.id == request.application_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if application is None:
            raise UnknownRecord(f"unknown application: {request.application_id}")
        if application["deleted_at"] is not None:
            raise StateConflict(f"application is deleted: {request.application_id}")
        existing = (
            connection.execute(
                select(operations).where(
                    operations.c.operation_type == request.operation_type.value,
                    operations.c.idempotency_key == request.idempotency_key,
                )
            )
            .mappings()
            .one_or_none()
        )
        if existing is not None:
            if existing["payload_hash"] != request.payload_hash:
                raise StateConflict(
                    "idempotency key already used with a different Operation payload",
                    code=IDEMPOTENCY_KEY_REUSED,
                )
            return _operation_record(existing, _outputs(connection, existing["id"]))
        connection.execute(
            insert(operations).values(
                id=operation_id,
                application_id=request.application_id,
                operation_type=request.operation_type.value,
                payload_json=request.payload,
                payload_hash=request.payload_hash,
                idempotency_key=request.idempotency_key,
                sources_json=request.sources.model_dump(mode="json"),
                resources_json=[
                    resource.model_dump(mode="json")
                    for resource in required_operation_resources(request)
                ],
                provider=request.provider,
                model=request.model,
                reasoning_effort=request.reasoning_effort,
                status=OperationStatus.QUEUED.value,
                phase=OperationPhase.QUEUED.value,
                message="",
                created_at=timestamp,
                retry_of_operation_id=request.retry_of_operation_id,
            )
        )
        row = (
            connection.execute(select(operations).where(operations.c.id == operation_id))
            .mappings()
            .one()
        )
        return _operation_record(row, [])

    def operation(self, tx: ReadTransaction, operation_id: str) -> PersistedOperation:
        connection = self._transactions.connection_for(tx)
        row = (
            connection.execute(select(operations).where(operations.c.id == operation_id))
            .mappings()
            .one_or_none()
        )
        return _operation_record(row, _outputs(connection, operation_id))

    def request_cancellation(
        self, tx: WriteTransaction, operation_id: str, *, now: str | None = None
    ) -> PersistedOperation:
        connection = self._transactions.connection_for(tx, access="write")
        timestamp = now or utc_now()
        row = (
            connection.execute(select(operations).where(operations.c.id == operation_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord("operation does not exist")
        if row["status"] == OperationStatus.QUEUED.value:
            connection.execute(
                delete(operation_resource_leases).where(
                    operation_resource_leases.c.operation_id == operation_id
                )
            )
            connection.execute(
                update(operations)
                .where(operations.c.id == operation_id, operations.c.status == "queued")
                .values(
                    status="cancelled",
                    phase="completed",
                    message="Cancelled before execution.",
                    finished_at=timestamp,
                    cancellation_requested_at=timestamp,
                    lease_owner=None,
                    lease_expires_at=None,
                    heartbeat_at=None,
                )
            )
        elif row["status"] == OperationStatus.RUNNING.value:
            connection.execute(
                update(operations)
                .where(
                    operations.c.id == operation_id,
                    operations.c.status == "running",
                    operations.c.cancellation_requested_at.is_(None),
                )
                .values(cancellation_requested_at=timestamp, message="Cancellation requested.")
            )
        current = (
            connection.execute(select(operations).where(operations.c.id == operation_id))
            .mappings()
            .one()
        )
        return _operation_record(current, _outputs(connection, operation_id))
