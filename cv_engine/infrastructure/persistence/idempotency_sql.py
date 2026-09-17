from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from ...application.errors import IDEMPOTENCY_KEY_REUSED, StateConflict
from ...util import canonical_json, new_id, sha256_text, utc_now
from .tables import idempotency_receipts


def _claim_idempotency_receipt(
    connection: Connection,
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


def _idempotency_receipt(
    connection: Connection, command_type: str, idempotency_key: str
) -> dict[str, Any] | None:
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


def _complete_idempotency_receipt(
    connection: Connection,
    receipt_id: str,
    result: dict[str, Any],
    *,
    completed_at: str | None = None,
) -> None:
    timestamp = completed_at or utc_now()
    changed = connection.execute(
        update(idempotency_receipts)
        .where(idempotency_receipts.c.id == receipt_id, idempotency_receipts.c.status == "pending")
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
