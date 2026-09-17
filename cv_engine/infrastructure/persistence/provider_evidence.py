"""Register immutable provider-response metadata and its inactive output atomically."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, insert, select

from ...application.errors import LineageBroken, UnknownRecord
from ...application.ports.provider_evidence import StoredProviderResponse
from ...application.ports.transactions import ReadTransaction, WriteTransaction
from ...application.ports.values import SnapshotPayload
from ...domain.contracts.providers import ProviderTaskResult
from ...util import canonical_json, new_id, sha256_text, utc_now
from .analysis_sql import _lock_application
from .connection import SqlAlchemyTransactionManager
from .tables import artifact_versions, artifacts, operation_outputs, operations


def _evidence_key(task: str, provenance: ProviderTaskResult) -> str:
    identity: dict[str, Any] = {
        "task": task,
        "provider": provenance.context.provider,
        "model": provenance.context.model,
        "response_id": provenance.context.response_id,
        "input_hash": provenance.input_hash,
        "output_hash": provenance.output_hash,
        "raw_output_hash": provenance.raw_output_hash,
        "execution": {
            key: value
            for key, value in provenance.context.model_dump(mode="json").items()
            if key not in {"response_id", "usage", "cost", "pricing", "latency_ms"}
        },
    }
    if provenance.context.response_id is None:
        identity["context"] = provenance.context.model_dump(mode="json")
    return sha256_text(canonical_json(identity))


class SqlAlchemyProviderEvidenceStore:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def find_response(
        self,
        tx: ReadTransaction,
        application_id: str,
        operation_id: str,
        task: str,
        provenance: ProviderTaskResult,
    ) -> StoredProviderResponse | None:
        connection = self._transactions.connection_for(tx)
        statement = (
            select(
                artifact_versions.c.id,
                artifact_versions.c.path,
                artifact_versions.c.content_hash,
                artifact_versions.c.metadata_json,
            )
            .join(artifacts)
            .where(
                artifacts.c.application_id == application_id,
                artifacts.c.artifact_type == "provider_response",
                artifacts.c.logical_name == task,
                artifact_versions.c.metadata_json["evidence_key"].astext
                == _evidence_key(task, provenance),
            )
        )
        # A provider-assigned response identity can be reused by a retry; absence
        # of that identity cannot prove that separate executions were the same.
        if provenance.context.response_id is None:
            statement = statement.where(
                artifact_versions.c.id.in_(
                    select(operation_outputs.c.output_id).where(
                        operation_outputs.c.operation_id == operation_id,
                        operation_outputs.c.output_type == "provider_response",
                    )
                )
            )
        row = connection.execute(statement).mappings().one_or_none()
        if row is None:
            return None
        return StoredProviderResponse(
            artifact_version_id=row["id"],
            payload=SnapshotPayload(
                row["path"], row["content_hash"], row["metadata_json"]["payload_size"]
            ),
        )

    def register_inactive(
        self,
        tx: WriteTransaction,
        application_id: str,
        operation_id: str,
        task: str,
        provenance: ProviderTaskResult,
        response: StoredProviderResponse,
    ) -> StoredProviderResponse:
        connection = self._transactions.connection_for(tx, access="write")
        _lock_application(connection, application_id)
        owner = connection.execute(
            select(operations.c.application_id).where(operations.c.id == operation_id)
        ).scalar_one_or_none()
        if owner is None:
            raise UnknownRecord(f"unknown operation: {operation_id}")
        if owner != application_id:
            raise LineageBroken("provider evidence belongs to another application")
        # Resolve races under the application lock without rewriting either record.
        existing = self.find_response(tx, application_id, operation_id, task, provenance)
        if existing is not None:
            output_id = connection.execute(
                select(operation_outputs.c.id).where(
                    operation_outputs.c.operation_id == operation_id,
                    operation_outputs.c.output_type == "provider_response",
                    operation_outputs.c.output_id == existing.artifact_version_id,
                )
            ).scalar_one_or_none()
            if output_id is None:
                connection.execute(
                    insert(operation_outputs).values(
                        id=new_id(),
                        operation_id=operation_id,
                        output_type="provider_response",
                        output_id=existing.artifact_version_id,
                        active=False,
                        created_at=utc_now(),
                    )
                )
            return existing
        now = utc_now()
        artifact_id = connection.execute(
            select(artifacts.c.id).where(
                artifacts.c.application_id == application_id,
                artifacts.c.artifact_type == "provider_response",
                artifacts.c.logical_name == task,
            )
        ).scalar_one_or_none()
        if artifact_id is None:
            artifact_id = new_id()
            connection.execute(
                insert(artifacts).values(
                    id=artifact_id,
                    application_id=application_id,
                    artifact_type="provider_response",
                    logical_name=task,
                    created_at=now,
                )
            )
        version = connection.execute(
            select(func.coalesce(func.max(artifact_versions.c.version_number), 0) + 1).where(
                artifact_versions.c.artifact_id == artifact_id
            )
        ).scalar_one()
        connection.execute(
            insert(artifact_versions).values(
                id=response.artifact_version_id,
                artifact_id=artifact_id,
                version_number=version,
                lifecycle_status="provider-output",
                path=response.payload.reference,
                content_hash=response.payload.sha256,
                created_at=now,
                metadata_json={
                    "task": task,
                    **provenance.context.model_dump(mode="json"),
                    "input_hash": provenance.input_hash,
                    "output_hash": provenance.output_hash,
                    "raw_output_hash": provenance.raw_output_hash,
                    "evidence_key": _evidence_key(task, provenance),
                    "payload_size": response.payload.size,
                },
            )
        )
        connection.execute(
            insert(operation_outputs).values(
                id=new_id(),
                operation_id=operation_id,
                output_type="provider_response",
                output_id=response.artifact_version_id,
                active=False,
                created_at=now,
            )
        )
        return response
