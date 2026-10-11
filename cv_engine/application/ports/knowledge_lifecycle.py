"""Persistence boundary for fact events."""

from __future__ import annotations

from typing import Any, Protocol

from .transactions import ReadTransaction, WriteTransaction


class KnowledgeLifecycleStore(Protocol):
    """The fact lifecycle trail and the analyses a fact event may cite."""

    def record_fact_event(self, tx: WriteTransaction, **event: Any) -> str: ...

    def fact_events(
        self, tx: ReadTransaction, user_id: str, fact_id: str | None = ...
    ) -> list[dict[str, Any]]:
        """The user's fact events, oldest first; never another user's."""
        ...

    def latest_fact_statuses(self, tx: ReadTransaction, user_id: str) -> dict[str, str]: ...

    def get_analysis(
        self, tx: ReadTransaction, analysis_id: str, application_id: str
    ) -> dict[str, Any]:
        """One of this Application's analyses; any other is `UnknownRecord`."""
        ...
