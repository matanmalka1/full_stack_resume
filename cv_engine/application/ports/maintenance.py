from __future__ import annotations

from typing import Any, Protocol

from .transactions import ReadTransaction


class MaintenanceInspection(Protocol):
    def integrity_problems(self, tx: ReadTransaction) -> list[str]: ...
    def artifact_inventory(self, tx: ReadTransaction) -> list[dict[str, Any]]: ...

    def registered_payload_references(self, tx: ReadTransaction) -> set[str]: ...
