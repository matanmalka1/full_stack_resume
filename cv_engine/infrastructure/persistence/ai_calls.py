"""Append-only SQL storage for the AI call log."""

from __future__ import annotations

from sqlalchemy import func, insert, null, select

from ...application.errors import UnknownRecord
from ...application.ports.ai_calls import LoggedAICall
from ...application.ports.transactions import WriteTransaction
from ...domain.contracts.providers import AICallRecord
from ...util import new_id
from .connection import SqlAlchemyTransactionManager
from .tables import ai_calls, operations


class SqlAlchemyAICallLog:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def append(
        self,
        tx: WriteTransaction,
        operation_id: str,
        record: AICallRecord,
        *,
        knowledge_context_hash: str,
    ) -> LoggedAICall:
        connection = self._transactions.connection_for(tx, access="write")
        # The row lock orders appends for one Operation, so the ordinal below cannot
        # be taken twice; UNIQUE(operation_id, task, attempt) is the backstop.
        locked = connection.execute(
            select(operations.c.id).where(operations.c.id == operation_id).with_for_update()
        ).scalar_one_or_none()
        if locked is None:
            raise UnknownRecord(f"unknown operation: {operation_id}")
        attempt = connection.execute(
            select(func.coalesce(func.max(ai_calls.c.attempt), 0) + 1).where(
                ai_calls.c.operation_id == operation_id, ai_calls.c.task == record.task
            )
        ).scalar_one()
        usage = record.usage
        identifier = new_id()
        connection.execute(
            insert(ai_calls).values(
                id=identifier,
                operation_id=operation_id,
                task=record.task,
                attempt=attempt,
                provider=record.provider,
                model=record.model,
                reasoning_effort=record.reasoning_effort,
                task_contract_version=record.task_contract_version,
                input_schema_version=record.input_schema_version,
                input_schema_hash=record.input_schema_hash,
                output_schema_version=record.output_schema_version,
                output_schema_hash=record.output_schema_hash,
                prompt_version=record.prompt_version,
                prompt_hash=record.prompt_hash,
                input_hash=record.input_hash,
                knowledge_context_hash=knowledge_context_hash,
                outcome=record.outcome,
                http_status=record.http_status,
                error_type=record.error_type,
                error_code=record.error_code,
                retry_after_seconds=record.retry_after_seconds,
                response_id=record.response_id,
                # SQL NULL, not the JSON `null` a bare None becomes in a JSONB column.
                sanitized_response=(
                    null() if record.sanitized_response is None else record.sanitized_response
                ),
                sanitized_response_hash=record.sanitized_response_hash,
                output_hash=record.output_hash,
                input_tokens=None if usage is None else usage.input_tokens,
                cached_input_tokens=None if usage is None else usage.cached_input_tokens,
                cache_write_tokens=None if usage is None else usage.cache_write_tokens,
                output_tokens=None if usage is None else usage.output_tokens,
                total_tokens=None if usage is None else usage.total_tokens,
                pricing=null()
                if record.pricing is None
                else record.pricing.model_dump(mode="json"),
                cost_usd=None if record.cost is None else record.cost.total_usd,
                latency_ms=record.latency_ms,
                started_at=record.started_at,
                finished_at=record.finished_at,
            )
        )
        return LoggedAICall(ai_call_id=identifier, attempt=attempt)
