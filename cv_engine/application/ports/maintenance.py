from __future__ import annotations

from typing import Any, Protocol

from .transactions import ReadTransaction


class MaintenanceInspection(Protocol):
    def user_ids(self, tx: ReadTransaction) -> list[str]: ...

    def integrity_problems(self, tx: ReadTransaction) -> list[str]: ...
    def ai_call_evidence(self, tx: ReadTransaction) -> list[dict[str, Any]]: ...
