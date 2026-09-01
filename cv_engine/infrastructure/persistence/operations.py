from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import case, delete, insert, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from ...application.errors import IDEMPOTENCY_KEY_REUSED, StateConflict, UnknownRecord
from ...application.operations import (
    CreateOperation,
    OperationFailureCode,
    OperationOutputReference,
    OperationPhase,
    OperationSources,
    OperationStatus,
    OperationView,
    PersistedOperation,
    as_operation_view,
    required_operation_resources,
)
from ...util import canonical_json, new_id, sha256_text, utc_now
from .base import SqlAlchemyRepositoryBase
from .tables import (
    idempotency_receipts,
    operation_outputs,
    operation_resource_leases,
    operations,
)


class SqlAlchemyOperationRepository(SqlAlchemyRepositoryBase):
    _RESOURCE_CAPACITY = {
        "application_mutation": 1,
        "render_browser": 1,
        "ai": 2,
    }

    @staticmethod
    def _expiry(now: str, lease_seconds: int) -> str:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        return (datetime.fromisoformat(now) + timedelta(seconds=lease_seconds)).isoformat()

    @staticmethod
    def _operation_record(row: Any, outputs: list[Any]) -> PersistedOperation:
        if row is None:
            raise UnknownRecord("operation does not exist")
        record = dict(row)
        return PersistedOperation(
            id=record["id"],
            application_id=record["application_id"],
            operation_type=record["operation_type"],
            payload=record["payload_json"],
            payload_hash=record["payload_hash"],
            idempotency_key=record["idempotency_key"],
            sources=OperationSources.model_validate(record["sources_json"]),
            resources=tuple(record["resources_json"]),
            provider=record["provider"],
            model=record["model"],
            status=record["status"],
            phase=record["phase"],
            message=record["message"],
            created_at=record["created_at"],
            started_at=record["started_at"],
            finished_at=record["finished_at"],
            lease_owner=record["lease_owner"],
            lease_expires_at=record["lease_expires_at"],
            heartbeat_at=record["heartbeat_at"],
            cancellation_requested_at=record["cancellation_requested_at"],
            failure_code=record["failure_code"],
            safe_failure_detail=record["safe_failure_detail"],
            technical_log_reference=record["technical_log_reference"],
            retry_of_operation_id=record["retry_of_operation_id"],
            attempts_completed=record["attempts_completed"],
            next_attempt_at=record["next_attempt_at"],
            outputs=[
                OperationOutputReference(
                    output_type=output["output_type"],
                    output_id=output["output_id"],
                    active=bool(output["active"]),
                )
                for output in outputs
            ],
        )

    @staticmethod
    def _outputs(connection: Connection, operation_id: str) -> list[Any]:
        statement = (
            select(
                operation_outputs.c.output_type,
                operation_outputs.c.output_id,
                operation_outputs.c.active,
            )
            .where(operation_outputs.c.operation_id == operation_id)
            .order_by(operation_outputs.c.created_at, operation_outputs.c.id)
        )
        return list(connection.execute(statement).mappings())

    def create_operation(
        self,
        request: CreateOperation,
        *,
        operation_id: str | None = None,
        created_at: str | None = None,
    ) -> PersistedOperation:
        identifier = operation_id or new_id()
        timestamp = created_at or utc_now()
        resources = required_operation_resources(request)
        with self.transaction() as connection:
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
                return self._operation_record(existing, self._outputs(connection, existing["id"]))
            try:
                connection.execute(
                    insert(operations).values(
                        id=identifier,
                        application_id=request.application_id,
                        operation_type=request.operation_type.value,
                        payload_json=request.payload,
                        payload_hash=request.payload_hash,
                        idempotency_key=request.idempotency_key,
                        sources_json=request.sources.model_dump(mode="json"),
                        resources_json=[resource.model_dump(mode="json") for resource in resources],
                        provider=request.provider,
                        model=request.model,
                        status=OperationStatus.QUEUED.value,
                        phase=OperationPhase.QUEUED.value,
                        message="",
                        created_at=timestamp,
                        retry_of_operation_id=request.retry_of_operation_id,
                    )
                )
            except IntegrityError:
                # Do not translate ownership, retry-reference, or schema violations
                # into an idempotency conflict.
                raise
            row = (
                connection.execute(select(operations).where(operations.c.id == identifier))
                .mappings()
                .one_or_none()
            )
            return self._operation_record(row, [])

    def operation(self, operation_id: str) -> PersistedOperation:
        with self.read_connection() as connection:
            row = (
                connection.execute(select(operations).where(operations.c.id == operation_id))
                .mappings()
                .one_or_none()
            )
            return self._operation_record(row, self._outputs(connection, operation_id))

    def active_operation(self, application_id: str) -> OperationView | None:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(operations)
                    .where(
                        operations.c.application_id == application_id,
                        operations.c.status.in_(("queued", "running")),
                    )
                    .order_by(
                        case((operations.c.status == "running", 0), else_=1),
                        operations.c.created_at,
                        operations.c.id,
                    )
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            return as_operation_view(
                self._operation_record(row, self._outputs(connection, row["id"]))
            )

    def latest_operation(self, application_id: str) -> OperationView | None:
        """Return the newest lifecycle record, including its terminal outcome.

        ``active_operation`` deliberately drops completed work so it remains a safe
        concurrency and polling signal.  The presentation projection also needs the
        newest record: otherwise a failure vanishes as soon as that active signal does.
        """
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(operations)
                    .where(operations.c.application_id == application_id)
                    .order_by(operations.c.created_at.desc(), operations.c.id.desc())
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            return as_operation_view(
                self._operation_record(row, self._outputs(connection, row["id"]))
            )

    @staticmethod
    def _waiting_phase(resource_kind: str) -> tuple[str, str]:
        if resource_kind == "render_browser":
            return OperationPhase.WAITING_FOR_RENDER_SLOT.value, "Waiting for render slot."
        if resource_kind == "ai":
            return OperationPhase.WAITING_FOR_AI_SLOT.value, "Waiting for AI slot."
        return OperationPhase.WAITING_FOR_APPLICATION.value, "Waiting for application operation."

    def claim_operation(
        self,
        operation_id: str,
        *,
        runner_id: str,
        lease_seconds: int = 30,
        now: str | None = None,
    ) -> PersistedOperation | None:
        timestamp = now or utc_now()
        expires_at = self._expiry(timestamp, lease_seconds)
        with self.transaction() as connection:
            # Lock the Operation row for the whole claim. Two runners that both
            # read `queued` here would both go on to take leases, and the loser
            # would then release them by operation_id - which are the *winner's*
            # rows, since both are claiming the same Operation. The winner kept
            # running with no leases and died at its first heartbeat.
            row = (
                connection.execute(
                    select(operations).where(operations.c.id == operation_id).with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise UnknownRecord("operation does not exist")
            if row["status"] != OperationStatus.QUEUED.value:
                return None
            if row["next_attempt_at"] is not None and row["next_attempt_at"] > timestamp:
                return None

            resources = row["resources_json"]
            acquired: list[tuple[str, str, int]] = []
            blocked_kind: str | None = None
            for resource in resources:
                kind = resource["kind"]
                key = resource["key"]
                for slot in range(self._RESOURCE_CAPACITY[kind]):
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
                self._release_acquired(connection, acquired)
                phase, message = self._waiting_phase(blocked_kind)
                connection.execute(
                    update(operations)
                    .where(
                        operations.c.id == operation_id,
                        operations.c.status == "queued",
                    )
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
                self._release_acquired(connection, acquired)
                return None
            current = (
                connection.execute(select(operations).where(operations.c.id == operation_id))
                .mappings()
                .one_or_none()
            )
            return self._operation_record(current, self._outputs(connection, operation_id))

    def claim_next_operation(
        self,
        *,
        runner_id: str,
        lease_seconds: int = 30,
        now: str | None = None,
    ) -> PersistedOperation | None:
        timestamp = now or utc_now()
        with self.read_connection() as connection:
            candidates = (
                connection.execute(
                    select(operations.c.id)
                    .where(
                        operations.c.status == "queued",
                        (operations.c.next_attempt_at.is_(None))
                        | (operations.c.next_attempt_at <= timestamp),
                    )
                    .order_by(operations.c.created_at, operations.c.id)
                )
                .mappings()
                .all()
            )
        for candidate in candidates:
            claimed = self.claim_operation(
                candidate["id"],
                runner_id=runner_id,
                lease_seconds=lease_seconds,
                now=timestamp,
            )
            if claimed is not None:
                return claimed
        return None

    def heartbeat_operation(
        self,
        operation_id: str,
        *,
        runner_id: str,
        lease_seconds: int = 30,
        now: str | None = None,
    ) -> None:
        timestamp = now or utc_now()
        expires_at = self._expiry(timestamp, lease_seconds)
        with self.transaction() as connection:
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

    def interrupt_expired_operations(self, *, now: str | None = None) -> list[str]:
        timestamp = now or utc_now()
        with self.transaction() as connection:
            rows = (
                connection.execute(
                    select(operations.c.id)
                    .where(
                        operations.c.status.in_(("queued", "running")),
                        operations.c.lease_expires_at.is_not(None),
                        operations.c.lease_expires_at <= timestamp,
                    )
                    .order_by(operations.c.created_at, operations.c.id)
                )
                .mappings()
                .all()
            )
            identifiers = [row["id"] for row in rows]
            for identifier in identifiers:
                connection.execute(
                    delete(operation_resource_leases).where(
                        operation_resource_leases.c.operation_id == identifier
                    )
                )
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

    def set_operation_phase(
        self,
        operation_id: str,
        phase: OperationPhase,
        *,
        runner_id: str,
        message: str = "",
    ) -> None:
        with self.transaction() as connection:
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

    def cancellation_requested(self, operation_id: str) -> bool:
        with self.read_connection() as connection:
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

    def request_operation_cancellation(
        self, operation_id: str, *, now: str | None = None
    ) -> PersistedOperation:
        timestamp = now or utc_now()
        with self.transaction() as connection:
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
                .one_or_none()
            )
            return self._operation_record(current, self._outputs(connection, operation_id))

    def record_operation_output(
        self,
        operation_id: str,
        output_type: str,
        output_id: str,
        *,
        active: bool = False,
        created_at: str | None = None,
    ) -> str:
        timestamp = created_at or utc_now()
        identifier = new_id()
        with self.transaction() as connection:
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
        self, operation_id: str, output_type: str, output_id: str, *, now: str | None = None
    ) -> None:
        timestamp = now or utc_now()
        with self.transaction() as connection:
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
        operation_id: str,
        *,
        runner_id: str,
        retry_at: str | None = None,
    ) -> int:
        with self.transaction() as connection:
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

    @staticmethod
    def _release_acquired(connection: Connection, acquired: list[tuple[str, str, int]]) -> None:
        """Undo exactly the leases one failed claim took, and nothing else.

        Releasing by operation_id would be wrong here: a claim that loses a
        race is looking at rows another claim of the same Operation owns.
        """
        for kind, key, slot in acquired:
            connection.execute(
                delete(operation_resource_leases).where(
                    operation_resource_leases.c.resource_kind == kind,
                    operation_resource_leases.c.resource_key == key,
                    operation_resource_leases.c.slot == slot,
                )
            )

    @staticmethod
    def _release(connection: Connection, operation_id: str) -> None:
        connection.execute(
            delete(operation_resource_leases).where(
                operation_resource_leases.c.operation_id == operation_id
            )
        )

    def complete_operation(
        self,
        operation_id: str,
        *,
        runner_id: str,
        now: str | None = None,
    ) -> PersistedOperation:
        timestamp = now or utc_now()
        with self.transaction() as connection:
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
            self._release(connection, operation_id)
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
            return self._operation_record(current, self._outputs(connection, operation_id))

    def fail_operation(
        self,
        operation_id: str,
        code: OperationFailureCode,
        safe_detail: str,
        *,
        runner_id: str,
        technical_log_reference: str | None = None,
        now: str | None = None,
    ) -> PersistedOperation:
        timestamp = now or utc_now()
        with self.transaction() as connection:
            self._release(connection, operation_id)
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
            return self._operation_record(current, self._outputs(connection, operation_id))

    def claim_idempotency_receipt(
        self,
        command_type: str,
        idempotency_key: str,
        payload: dict[str, Any],
        *,
        reserved_entity_id: str,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        payload_json = canonical_json(payload)
        payload_hash = sha256_text(payload_json)
        timestamp = created_at or utc_now()
        with self.transaction() as connection:
            existing = (
                connection.execute(
                    select(idempotency_receipts).where(
                        idempotency_receipts.c.command_type == command_type,
                        idempotency_receipts.c.idempotency_key == idempotency_key,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if existing is not None:
                if existing["payload_hash"] != payload_hash:
                    raise StateConflict(
                        "idempotency key already used with a different command payload",
                        code=IDEMPOTENCY_KEY_REUSED,
                    )
                record = dict(existing)
                record["payload"] = record.pop("payload_json")
                record["result"] = record.pop("result_json")
                return record
            identifier = new_id()
            connection.execute(
                insert(idempotency_receipts).values(
                    id=identifier,
                    command_type=command_type,
                    idempotency_key=idempotency_key,
                    payload_json=payload,
                    payload_hash=payload_hash,
                    reserved_entity_id=reserved_entity_id,
                    status="pending",
                    created_at=timestamp,
                )
            )
            return {
                "id": identifier,
                "command_type": command_type,
                "idempotency_key": idempotency_key,
                "payload": payload,
                "payload_hash": payload_hash,
                "reserved_entity_id": reserved_entity_id,
                "status": "pending",
                "result": None,
                "created_at": timestamp,
                "completed_at": None,
            }

    def idempotency_receipt(self, command_type: str, idempotency_key: str) -> dict[str, Any] | None:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(idempotency_receipts).where(
                        idempotency_receipts.c.command_type == command_type,
                        idempotency_receipts.c.idempotency_key == idempotency_key,
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return None
        record = dict(row)
        record["payload"] = record.pop("payload_json")
        record["result"] = record.pop("result_json")
        return record

    def complete_idempotency_receipt(
        self, receipt_id: str, result: dict[str, Any], *, completed_at: str | None = None
    ) -> None:
        timestamp = completed_at or utc_now()
        with self.transaction() as connection:
            changed = connection.execute(
                update(idempotency_receipts)
                .where(
                    idempotency_receipts.c.id == receipt_id,
                    idempotency_receipts.c.status == "pending",
                )
                .values(status="completed", result_json=result, completed_at=timestamp)
            ).rowcount
            if changed != 1:
                row = (
                    connection.execute(
                        select(idempotency_receipts.c.result_json).where(
                            idempotency_receipts.c.id == receipt_id,
                            idempotency_receipts.c.status == "completed",
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None or row["result_json"] != result:
                    raise StateConflict("idempotency receipt cannot be completed")
