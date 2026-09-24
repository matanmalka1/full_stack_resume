from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.engine import Connection

from ...application.errors import UnknownRecord
from ...application.operations import OperationOutputReference, OperationSources, PersistedOperation
from .tables import artifact_versions, operation_outputs, operation_resource_leases


def _operation_record(row: Any, outputs: list[Any]) -> PersistedOperation:
    if row is None:
        raise UnknownRecord("operation does not exist")
    record = dict(row)
    provider_metadata = next(
        (
            output.get("metadata_json") or {}
            for output in outputs
            if output["output_type"] == "provider_response"
        ),
        {},
    )
    usage = provider_metadata.get("usage") or {}
    cost = provider_metadata.get("cost") or {}
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
        reasoning_effort=record["reasoning_effort"],
        input_tokens=usage.get("input_tokens"),
        cached_input_tokens=usage.get("cached_input_tokens"),
        output_tokens=usage.get("output_tokens"),
        total_tokens=usage.get("total_tokens"),
        cost_usd=cost.get("total_usd"),
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
        failure_reason=record["failure_reason"],
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


def _outputs(connection: Connection, operation_id: str) -> list[Any]:
    statement = (
        select(
            operation_outputs.c.output_type,
            operation_outputs.c.output_id,
            operation_outputs.c.active,
            artifact_versions.c.metadata_json,
        )
        .outerjoin(artifact_versions, artifact_versions.c.id == operation_outputs.c.output_id)
        .where(operation_outputs.c.operation_id == operation_id)
        .order_by(operation_outputs.c.created_at, operation_outputs.c.id)
    )
    return list(connection.execute(statement).mappings())


def _release(connection: Connection, operation_id: str) -> None:
    connection.execute(
        delete(operation_resource_leases).where(
            operation_resource_leases.c.operation_id == operation_id
        )
    )
