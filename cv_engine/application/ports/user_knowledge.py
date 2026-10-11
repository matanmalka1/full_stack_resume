"""A user's Knowledge in PostgreSQL (architecture §18.2), as `import-knowledge` writes it."""

from __future__ import annotations

from typing import Any, Protocol

from .transactions import ReadTransaction, WriteTransaction


class UserKnowledgeRepository(Protocol):
    def has_knowledge(self, tx: ReadTransaction, user_id: str) -> bool:
        """Whether the user has any fact, candidate context, or Profile binding."""
        ...

    def insert_knowledge(
        self,
        tx: WriteTransaction,
        user_id: str,
        *,
        facts: list[dict[str, Any]],
        candidate: dict[str, Any],
        bindings: dict[str, dict[str, Any]],
        imported_at: str,
    ) -> None:
        """Raise `StateConflict` when the user's Knowledge was written concurrently."""
        ...

    def stored_knowledge(
        self, tx: ReadTransaction, user_id: str
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None, dict[str, dict[str, Any]]]:
        """Facts in (source, ordinal) order, the candidate payload, and bindings by profile."""
        ...
