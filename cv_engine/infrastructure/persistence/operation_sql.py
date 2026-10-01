from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import exists, func, select
from sqlalchemy.engine import Connection

from ...application.ai_configuration import usd
from ...application.errors import UnknownRecord
from ...application.operations import (
    OperationOutputReference,
    OperationPhase,
    OperationSources,
    OperationStatus,
    OperationType,
    PersistedOperation,
)
from .tables import ai_calls, operation_outputs, operations

_USAGE_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_tokens",
    "output_tokens",
    "total_tokens",
)


def _call_totals(connection: Connection, operation_id: str) -> dict[str, Any]:
    """Usage and cost of every logged provider call of the Operation, summed.

    Every attempt counts once - a refused answer, or one a retry replaced, was still
    billed. An attempt proven never to have reached the provider (`not_delivered`)
    used nothing, so it adds zero rather than an unknown. Any other attempt without a
    value makes that total NULL, rather than a partial sum that reads as the whole;
    with no call logged at all, every total is NULL.
    """
    columns = [*_USAGE_FIELDS, "cost_usd"]
    delivered = ai_calls.c.outcome != "not_delivered"
    row = (
        connection.execute(
            select(
                func.count().label("attempts"),
                func.count().filter(delivered).label("calls"),
                *(
                    func.coalesce(func.sum(ai_calls.c[name]).filter(delivered), 0).label(
                        f"sum_{name}"
                    )
                    for name in columns
                ),
                *(
                    func.count(ai_calls.c[name]).filter(delivered).label(f"known_{name}")
                    for name in columns
                ),
            ).where(ai_calls.c.operation_id == operation_id)
        )
        .mappings()
        .one()
    )
    attempts, calls = row["attempts"], row["calls"]
    totals: dict[str, Any] = {
        name: int(row[f"sum_{name}"]) if attempts and row[f"known_{name}"] == calls else None
        for name in _USAGE_FIELDS
    }
    totals["cost_usd"] = (
        usd(Decimal(row["sum_cost_usd"])) if attempts and row["known_cost_usd"] == calls else None
    )
    return totals


def _phase(connection: Connection, record: dict[str, Any]) -> OperationPhase:
    """The stored phase; for a queued Operation, what it is waiting for right now.

    A claim the database refused writes nothing, so a waiting phase is read from what
    is running - the same two conditions the claim guards enforce - and cannot go
    stale. Queued with neither running means it waits only for a free worker thread.
    """
    stored = OperationPhase(record["phase"])
    if record["status"] != OperationStatus.QUEUED.value:
        return stored
    running = operations.alias("running")
    busy = connection.execute(
        select(
            exists()
            .where(
                running.c.status == OperationStatus.RUNNING.value,
                running.c.application_id == record["application_id"],
            )
            .label("application"),
            exists()
            .where(
                running.c.status == OperationStatus.RUNNING.value,
                running.c.operation_type == OperationType.RENDER_DOCUMENT.value,
            )
            .label("render"),
        )
    ).one()
    if busy.application:
        return OperationPhase.WAITING_FOR_APPLICATION
    if busy.render and record["operation_type"] == OperationType.RENDER_DOCUMENT.value:
        return OperationPhase.WAITING_FOR_RENDER_SLOT
    return stored


def _operation_record(row: Any, connection: Connection) -> PersistedOperation:
    if row is None:
        raise UnknownRecord("operation does not exist")
    record = dict(row)
    outputs = _outputs(connection, record["id"])
    return PersistedOperation(
        id=record["id"],
        application_id=record["application_id"],
        operation_type=record["operation_type"],
        payload=record["payload_json"],
        payload_hash=record["payload_hash"],
        idempotency_key=record["idempotency_key"],
        sources=OperationSources.model_validate(record["sources_json"]),
        provider=record["provider"],
        model=record["model"],
        reasoning_effort=record["reasoning_effort"],
        **_call_totals(connection, record["id"]),
        status=record["status"],
        phase=_phase(connection, record),
        message=record["message"],
        created_at=record["created_at"],
        started_at=record["started_at"],
        finished_at=record["finished_at"],
        lease_owner=record["lease_owner"],
        cancellation_requested_at=record["cancellation_requested_at"],
        failure_code=record["failure_code"],
        safe_failure_detail=record["safe_failure_detail"],
        failure_reason=record["failure_reason"],
        withheld_claims=record["withheld_claims"],
        technical_log_reference=record["technical_log_reference"],
        retry_of_operation_id=record["retry_of_operation_id"],
        attempts_completed=record["attempts_completed"],
        outputs=[
            OperationOutputReference(
                output_type=output["output_type"],
                output_id=output["output_id"],
                active=bool(output["active"]),
            )
            for output in outputs
        ],
    )


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
