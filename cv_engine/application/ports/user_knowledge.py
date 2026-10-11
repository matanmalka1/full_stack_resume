"""A user's Knowledge in PostgreSQL (architecture §18.2): its rows, and the Knowledge they make."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ...domain.facts import FactStore
from ...domain.knowledge import Knowledge
from .transactions import ReadTransaction, WriteTransaction


@dataclass(frozen=True)
class StoredKnowledge:
    """One user's Knowledge rows as stored: what a mutation reads, changes and writes back.

    `facts` are rows in the `facts` column shape (`fact_id`, `status`, `source`,
    `ordinal`, the content and lifecycle fields); `bindings` are keyed by Profile id.
    """

    user_id: str
    facts: list[dict[str, Any]]
    candidate: dict[str, Any]
    bindings: dict[str, dict[str, Any]]
    fact_store_version: int = 0
    binding_versions: dict[str, int] = field(default_factory=dict)


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

    def knowledge_state(self, tx: ReadTransaction, user_id: str) -> StoredKnowledge | None:
        """Everything a mutation needs, with the versions it must advance; None if unimported."""
        ...

    def insert_fact(
        self, tx: WriteTransaction, user_id: str, row: dict[str, Any], *, now: str
    ) -> None: ...

    def update_fact(
        self, tx: WriteTransaction, user_id: str, row: dict[str, Any], *, now: str
    ) -> None:
        """Write a fact's status and content; its identity columns are never written."""
        ...

    def set_binding(
        self,
        tx: WriteTransaction,
        user_id: str,
        profile_id: str,
        binding: dict[str, Any],
        *,
        expected_version: int,
        now: str,
    ) -> None:
        """Replace one binding; `StateConflict` when it moved since `expected_version`."""
        ...

    def advance_fact_store_version(
        self, tx: WriteTransaction, user_id: str, *, expected: int, now: str
    ) -> int:
        """Increment the user's `fact_store_version`; `StateConflict` when it moved."""
        ...


class UserKnowledgeSource(Protocol):
    """The Knowledge every command reads: one user's rows joined with the policy files.

    `tx` is the caller's scope when it already holds one, as the Operation handlers do;
    without it the source opens its own read scope.
    """

    def load(self, user_id: str, tx: ReadTransaction | None = None) -> Knowledge: ...

    def facts(self, user_id: str, tx: ReadTransaction | None = None) -> FactStore: ...

    def state(self, tx: ReadTransaction, user_id: str) -> StoredKnowledge:
        """The user's rows; refused when nothing was imported for them."""
        ...

    def build(self, state: StoredKnowledge) -> Knowledge:
        """The Knowledge `state` makes, validated as a whole: how a mutation is checked."""
        ...
