from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any

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
    required_operation_resources,
)
from ...util import canonical_json, new_id, sha256_text, utc_now
from .base import SqliteRepositoryBase


class SqliteOperationRepository(SqliteRepositoryBase):
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
            installation_id=record["installation_id"],
            operation_type=record["operation_type"],
            payload=json.loads(record["payload_json"]),
            payload_hash=record["payload_hash"],
            idempotency_key=record["idempotency_key"],
            sources=OperationSources.model_validate_json(record["sources_json"]),
            resources=tuple(json.loads(record["resources_json"])),
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
    def _outputs(connection: Any, operation_id: str) -> list[Any]:
        return connection.execute(
            "SELECT output_type, output_id, active FROM operation_outputs "
            "WHERE operation_id=? ORDER BY created_at, id",
            (operation_id,),
        ).fetchall()

    def create_operation(
        self,
        request: CreateOperation,
        *,
        installation_id: str,
        operation_id: str | None = None,
        created_at: str | None = None,
    ) -> PersistedOperation:
        identifier = operation_id or new_id()
        timestamp = created_at or utc_now()
        resources = required_operation_resources(request)
        with self.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM operations WHERE installation_id=? AND operation_type=? "
                "AND idempotency_key=?",
                (installation_id, request.operation_type.value, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["payload_hash"] != request.payload_hash:
                    raise StateConflict(
                        "idempotency key already used with a different Operation payload",
                        code=IDEMPOTENCY_KEY_REUSED,
                    )
                return self._operation_record(existing, self._outputs(connection, existing["id"]))
            try:
                connection.execute(
                    "INSERT INTO operations("
                    "id, application_id, installation_id, operation_type, payload_json, "
                    "payload_hash, idempotency_key, sources_json, resources_json, provider, "
                    "model, status, phase, message, created_at, retry_of_operation_id"
                    ") VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?)",
                    (
                        identifier,
                        request.application_id,
                        installation_id,
                        request.operation_type.value,
                        canonical_json(request.payload),
                        request.payload_hash,
                        request.idempotency_key,
                        request.sources.model_dump_json(),
                        canonical_json(
                            [resource.model_dump(mode="json") for resource in resources]
                        ),
                        request.provider,
                        request.model,
                        OperationStatus.QUEUED.value,
                        OperationPhase.QUEUED.value,
                        timestamp,
                        request.retry_of_operation_id,
                    ),
                )
            except sqlite3.IntegrityError:
                # Do not translate ownership, retry-reference, or schema violations
                # into an idempotency conflict.
                raise
            row = connection.execute(
                "SELECT * FROM operations WHERE id=?", (identifier,)
            ).fetchone()
            return self._operation_record(row, [])

    def operation(self, operation_id: str) -> PersistedOperation:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM operations WHERE id=?", (operation_id,)
            ).fetchone()
            return self._operation_record(row, self._outputs(connection, operation_id))

    def active_operation(self, application_id: str) -> OperationView | None:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM operations WHERE application_id=? "
                "AND status IN ('queued', 'running') "
                "ORDER BY CASE status WHEN 'running' THEN 0 ELSE 1 END, created_at, id LIMIT 1",
                (application_id,),
            ).fetchone()
            if row is None:
                return None
            return OperationView.model_validate(
                self._operation_record(row, self._outputs(connection, row["id"])),
                from_attributes=True,
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
            row = connection.execute(
                "SELECT * FROM operations WHERE id=?", (operation_id,)
            ).fetchone()
            if row is None:
                raise UnknownRecord("operation does not exist")
            if row["status"] != OperationStatus.QUEUED.value:
                return None
            if row["next_attempt_at"] is not None and row["next_attempt_at"] > timestamp:
                return None

            resources = json.loads(row["resources_json"])
            acquired: list[tuple[str, str, int]] = []
            blocked_kind: str | None = None
            for resource in resources:
                kind = resource["kind"]
                key = resource["key"]
                for slot in range(self._RESOURCE_CAPACITY[kind]):
                    try:
                        connection.execute(
                            "INSERT INTO operation_resource_leases("
                            "resource_kind, resource_key, slot, operation_id, lease_owner, "
                            "lease_expires_at, heartbeat_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
                            (kind, key, slot, operation_id, runner_id, expires_at, timestamp),
                        )
                    except sqlite3.IntegrityError:
                        continue
                    acquired.append((kind, key, slot))
                    break
                else:
                    blocked_kind = kind
                    break

            if blocked_kind is not None:
                connection.execute(
                    "DELETE FROM operation_resource_leases WHERE operation_id=?",
                    (operation_id,),
                )
                phase, message = self._waiting_phase(blocked_kind)
                connection.execute(
                    "UPDATE operations SET phase=?, message=? WHERE id=? AND status='queued'",
                    (phase, message, operation_id),
                )
                return None

            changed = connection.execute(
                "UPDATE operations SET status='running', phase=?, message='', started_at=?, "
                "lease_owner=?, lease_expires_at=?, heartbeat_at=? "
                "WHERE id=? AND status='queued'",
                (
                    OperationPhase.PRE_EXECUTION_CHECK.value,
                    timestamp,
                    runner_id,
                    expires_at,
                    timestamp,
                    operation_id,
                ),
            ).rowcount
            if changed != 1:
                connection.execute(
                    "DELETE FROM operation_resource_leases WHERE operation_id=?",
                    (operation_id,),
                )
                return None
            current = connection.execute(
                "SELECT * FROM operations WHERE id=?", (operation_id,)
            ).fetchone()
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
            candidates = connection.execute(
                "SELECT id FROM operations WHERE status='queued' "
                "AND (next_attempt_at IS NULL OR next_attempt_at<=?) "
                "ORDER BY created_at, id",
                (timestamp,),
            ).fetchall()
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
                "UPDATE operations SET heartbeat_at=?, lease_expires_at=? "
                "WHERE id=? AND status='running' AND lease_owner=?",
                (timestamp, expires_at, operation_id, runner_id),
            ).rowcount
            if changed != 1:
                raise StateConflict("operation lease is not owned by this runner")
            leases = connection.execute(
                "UPDATE operation_resource_leases SET heartbeat_at=?, lease_expires_at=? "
                "WHERE operation_id=? AND lease_owner=?",
                (timestamp, expires_at, operation_id, runner_id),
            ).rowcount
            if leases < 1:
                raise StateConflict("operation resource leases are missing")

    def interrupt_expired_operations(self, *, now: str | None = None) -> list[str]:
        timestamp = now or utc_now()
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT id FROM operations WHERE status IN ('queued', 'running') "
                "AND lease_expires_at IS NOT NULL AND lease_expires_at<=? ORDER BY created_at, id",
                (timestamp,),
            ).fetchall()
            identifiers = [row["id"] for row in rows]
            for identifier in identifiers:
                connection.execute(
                    "DELETE FROM operation_resource_leases WHERE operation_id=?", (identifier,)
                )
                connection.execute(
                    "UPDATE operations SET status='interrupted', phase='completed', "
                    "message='Interrupted after runner lease expired.', finished_at=?, "
                    "lease_owner=NULL, lease_expires_at=NULL, heartbeat_at=NULL "
                    "WHERE id=? AND status IN ('queued', 'running')",
                    (timestamp, identifier),
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
                "UPDATE operations SET phase=?, message=? "
                "WHERE id=? AND status='running' AND lease_owner=?",
                (phase.value, message, operation_id, runner_id),
            ).rowcount
            if changed != 1:
                raise StateConflict("operation lease is not owned by this runner")

    def cancellation_requested(self, operation_id: str) -> bool:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT cancellation_requested_at FROM operations WHERE id=?", (operation_id,)
            ).fetchone()
        if row is None:
            raise UnknownRecord("operation does not exist")
        return row["cancellation_requested_at"] is not None

    def request_operation_cancellation(
        self, operation_id: str, *, now: str | None = None
    ) -> PersistedOperation:
        timestamp = now or utc_now()
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM operations WHERE id=?", (operation_id,)
            ).fetchone()
            if row is None:
                raise UnknownRecord("operation does not exist")
            if row["status"] == OperationStatus.QUEUED.value:
                connection.execute(
                    "DELETE FROM operation_resource_leases WHERE operation_id=?", (operation_id,)
                )
                connection.execute(
                    "UPDATE operations SET status='cancelled', phase='completed', "
                    "message='Cancelled before execution.', finished_at=?, "
                    "cancellation_requested_at=?, lease_owner=NULL, lease_expires_at=NULL, "
                    "heartbeat_at=NULL WHERE id=? AND status='queued'",
                    (timestamp, timestamp, operation_id),
                )
            elif row["status"] == OperationStatus.RUNNING.value:
                connection.execute(
                    "UPDATE operations SET cancellation_requested_at=?, "
                    "message='Cancellation requested.' WHERE id=? AND status='running' "
                    "AND cancellation_requested_at IS NULL",
                    (timestamp, operation_id),
                )
            current = connection.execute(
                "SELECT * FROM operations WHERE id=?", (operation_id,)
            ).fetchone()
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
            operation = connection.execute(
                "SELECT status, cancellation_requested_at FROM operations WHERE id=?",
                (operation_id,),
            ).fetchone()
            if operation is None:
                raise UnknownRecord("operation does not exist")
            if active and (
                operation["status"] != OperationStatus.RUNNING.value
                or operation["cancellation_requested_at"] is not None
            ):
                raise StateConflict("operation output cannot be activated")
            connection.execute(
                "INSERT INTO operation_outputs(id, operation_id, output_type, output_id, "
                "active, created_at, activated_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
                (
                    identifier,
                    operation_id,
                    output_type,
                    output_id,
                    int(active),
                    timestamp,
                    timestamp if active else None,
                ),
            )
        return identifier

    def activate_operation_output(
        self, operation_id: str, output_type: str, output_id: str, *, now: str | None = None
    ) -> None:
        timestamp = now or utc_now()
        with self.transaction() as connection:
            changed = connection.execute(
                "UPDATE operation_outputs SET active=1, activated_at=? "
                "WHERE operation_id=? AND output_type=? AND output_id=? AND active=0",
                (timestamp, operation_id, output_type, output_id),
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
                "UPDATE operations SET attempts_completed=attempts_completed+1, "
                "phase=?, next_attempt_at=? "
                "WHERE id=? AND status='running' AND lease_owner=?",
                (OperationPhase.RETRY_WAIT.value, retry_at, operation_id, runner_id),
            ).rowcount
            if changed != 1:
                raise StateConflict("operation lease is not owned by this runner")
            return connection.execute(
                "SELECT attempts_completed FROM operations WHERE id=?", (operation_id,)
            ).fetchone()[0]

    @staticmethod
    def _release(connection: Any, operation_id: str) -> None:
        connection.execute(
            "DELETE FROM operation_resource_leases WHERE operation_id=?", (operation_id,)
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
            row = connection.execute(
                "SELECT * FROM operations WHERE id=? AND status='running' AND lease_owner=?",
                (operation_id, runner_id),
            ).fetchone()
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
                "UPDATE operations SET status=?, phase='completed', message=?, finished_at=?, "
                "failure_code=?, safe_failure_detail=?, lease_owner=NULL, "
                "lease_expires_at=NULL, heartbeat_at=NULL, next_attempt_at=NULL, "
                "attempts_completed=attempts_completed+1 "
                "WHERE id=? AND status='running' AND lease_owner=?",
                (
                    status,
                    message,
                    timestamp,
                    failure_code,
                    message or None,
                    operation_id,
                    runner_id,
                ),
            )
            current = connection.execute(
                "SELECT * FROM operations WHERE id=?", (operation_id,)
            ).fetchone()
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
                "UPDATE operations SET status='failed', phase='completed', message='', "
                "finished_at=?, failure_code=?, safe_failure_detail=?, "
                "technical_log_reference=?, attempts_completed=attempts_completed+1, "
                "lease_owner=NULL, lease_expires_at=NULL, heartbeat_at=NULL, next_attempt_at=NULL "
                "WHERE id=? AND status='running' AND lease_owner=?",
                (
                    timestamp,
                    code.value,
                    safe_detail,
                    technical_log_reference,
                    operation_id,
                    runner_id,
                ),
            ).rowcount
            if changed != 1:
                raise StateConflict("operation lease is not owned by this runner")
            current = connection.execute(
                "SELECT * FROM operations WHERE id=?", (operation_id,)
            ).fetchone()
            return self._operation_record(current, self._outputs(connection, operation_id))

    def claim_idempotency_receipt(
        self,
        command_type: str,
        idempotency_key: str,
        payload: dict[str, Any],
        *,
        installation_id: str,
        reserved_entity_id: str,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        payload_json = canonical_json(payload)
        payload_hash = sha256_text(payload_json)
        timestamp = created_at or utc_now()
        with self.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM idempotency_receipts WHERE installation_id=? "
                "AND command_type=? AND idempotency_key=?",
                (installation_id, command_type, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["payload_hash"] != payload_hash:
                    raise StateConflict(
                        "idempotency key already used with a different command payload",
                        code=IDEMPOTENCY_KEY_REUSED,
                    )
                record = dict(existing)
                record["payload"] = json.loads(record.pop("payload_json"))
                result_json = record.pop("result_json")
                record["result"] = json.loads(result_json) if result_json is not None else None
                return record
            identifier = new_id()
            connection.execute(
                "INSERT INTO idempotency_receipts("
                "id, installation_id, command_type, idempotency_key, payload_json, "
                "payload_hash, reserved_entity_id, status, created_at"
                ") VALUES(?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
                (
                    identifier,
                    installation_id,
                    command_type,
                    idempotency_key,
                    payload_json,
                    payload_hash,
                    reserved_entity_id,
                    timestamp,
                ),
            )
            return {
                "id": identifier,
                "installation_id": installation_id,
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

    def idempotency_receipt(
        self, command_type: str, idempotency_key: str, *, installation_id: str
    ) -> dict[str, Any] | None:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM idempotency_receipts WHERE installation_id=? "
                "AND command_type=? AND idempotency_key=?",
                (installation_id, command_type, idempotency_key),
            ).fetchone()
        if row is None:
            return None
        record = dict(row)
        record["payload"] = json.loads(record.pop("payload_json"))
        result_json = record.pop("result_json")
        record["result"] = json.loads(result_json) if result_json is not None else None
        return record

    def complete_idempotency_receipt(
        self, receipt_id: str, result: dict[str, Any], *, completed_at: str | None = None
    ) -> None:
        timestamp = completed_at or utc_now()
        with self.transaction() as connection:
            changed = connection.execute(
                "UPDATE idempotency_receipts SET status='completed', result_json=?, "
                "completed_at=? WHERE id=? AND status='pending'",
                (canonical_json(result), timestamp, receipt_id),
            ).rowcount
            if changed != 1:
                row = connection.execute(
                    "SELECT result_json FROM idempotency_receipts WHERE id=? AND status='completed'",
                    (receipt_id,),
                ).fetchone()
                if row is None or json.loads(row["result_json"]) != result:
                    raise StateConflict("idempotency receipt cannot be completed")
