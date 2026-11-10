from __future__ import annotations

from typing import Any, Protocol

from ..operations import OperationView
from .transactions import ReadTransaction


class ApplicationProjectionReader(Protocol):
    """Database-only inputs for the API application projections."""

    def application(
        self, tx: ReadTransaction, application_id: str, user_id: str
    ) -> dict[str, Any]: ...
    def applications(self, tx: ReadTransaction, user_id: str) -> list[dict[str, Any]]: ...
    def analyses(self, tx: ReadTransaction, application_id: str) -> list[dict[str, Any]]: ...
    def analysis(
        self, tx: ReadTransaction, analysis_id: str, application_id: str
    ) -> dict[str, Any]: ...
    def audit_records(self, tx: ReadTransaction, application_id: str) -> list[dict[str, Any]]: ...
    def active_operation(
        self, tx: ReadTransaction, application_id: str
    ) -> OperationView | None: ...
    def latest_operation(
        self, tx: ReadTransaction, application_id: str
    ) -> OperationView | None: ...
    def has_active_matching_context_operation(
        self, tx: ReadTransaction, application_id: str
    ) -> bool: ...
