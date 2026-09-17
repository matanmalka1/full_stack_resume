"""Application labels and disposition consumed by historical draft commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .transactions import ReadTransaction


@dataclass(frozen=True)
class DraftHistoryApplication:
    company: str
    target_role: str
    deleted_at: str | None


class DraftHistoryApplicationReader(Protocol):
    """Consistent history-source labels; disposition guards archival writes."""

    def history_application(
        self, tx: ReadTransaction, application_id: str
    ) -> DraftHistoryApplication: ...
