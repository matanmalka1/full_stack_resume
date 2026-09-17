from __future__ import annotations

from typing import Any, Protocol

from .transactions import ReadTransaction, WriteTransaction


class IdempotencyStore(Protocol):
    def claim_idempotency_receipt(
        self,
        tx: WriteTransaction,
        command_type: str,
        idempotency_key: str,
        payload: dict[str, Any],
        *,
        reserved_entity_id: str,
        created_at: str | None = None,
    ) -> dict[str, Any]: ...

    def idempotency_receipt(
        self, tx: ReadTransaction, command_type: str, idempotency_key: str
    ) -> dict[str, Any] | None: ...

    def complete_idempotency_receipt(
        self,
        tx: WriteTransaction,
        receipt_id: str,
        result: dict[str, Any],
        *,
        completed_at: str | None = None,
    ) -> None: ...
