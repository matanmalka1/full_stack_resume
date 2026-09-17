from __future__ import annotations

from typing import Any, Protocol

from ...domain.contracts.records import DecisionRecord
from .transactions import ReadTransaction, WriteTransaction


class DecisionStore(Protocol):
    def insert_decision(self, tx: WriteTransaction, record: DecisionRecord) -> None: ...

    def latest_decision(self, tx: ReadTransaction, application_id: str) -> dict[str, Any]: ...

    def decision_for_artifact_version(
        self, tx: ReadTransaction, artifact_version_id: str
    ) -> dict[str, Any]: ...

    def decision_for_revision(self, tx: ReadTransaction, revision_id: str) -> dict[str, Any]: ...
