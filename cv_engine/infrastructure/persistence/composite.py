from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .applications import SqliteApplicationRepository
from .artifacts import SqliteArtifactRepository
from .audit import SqliteAuditRepository
from .connection import SqliteUnitOfWork
from .preparation import SqlitePreparationRepository
from .schema import ensure_current_schema
from .tracking import SqliteTrackingRepository


class Repository:
    """Delegation-only composed repository used during the M1-to-M2 transition."""

    _METHOD_OWNERS = {
        "create_application": "preparation",
        "add_job_snapshot": "preparation",
        "latest_snapshot": "preparation",
        "get_snapshot": "preparation",
        "save_analysis": "preparation",
        "get_analysis": "preparation",
        "analyses": "preparation",
        "latest_analysis": "preparation",
        "get_application": "applications",
        "list_applications": "applications",
        "transition_status": "applications",
        "record_event": "applications",
        "set_next_action": "applications",
        "set_normalized_role": "applications",
        "artifact_inventory": "artifacts",
        "register_artifact_version": "artifacts",
        "latest_artifact_version": "artifacts",
        "artifact_versions": "artifacts",
        "record_decision": "artifacts",
        "latest_decision": "artifacts",
        "decision_for_artifact_version": "artifacts",
        "record_generation_run": "artifacts",
        "record_validation": "artifacts",
        "latest_validation": "artifacts",
        "validation_for_artifact": "artifacts",
        "integrity_check": "artifacts",
        "set_ready": "tracking",
        "record_submission": "tracking",
        "_set_ready": "tracking",
        "_record_submission": "tracking",
        "record_fact_event": "audit",
        "fact_events": "audit",
        "latest_fact_statuses": "audit",
    }

    def __init__(self, path: Path, *, _owners: dict[str, Any] | None = None):
        self.path = Path(path)
        if _owners is None:
            ensure_current_schema(self.path)
            applications = SqliteApplicationRepository(self.path)
            self._owners = {
                "applications": applications,
                "preparation": SqlitePreparationRepository(
                    self.path, applications=applications
                ),
                "artifacts": SqliteArtifactRepository(self.path),
                "tracking": SqliteTrackingRepository(
                    self.path, applications=applications
                ),
                "audit": SqliteAuditRepository(self.path),
            }
        else:
            self._owners = _owners

    def __getattr__(self, name: str) -> Any:
        owner_name = self._METHOD_OWNERS.get(name)
        if owner_name is None:
            raise AttributeError(name)
        return getattr(self._owners[owner_name], name)

    def unit_of_work(self) -> SqliteUnitOfWork:
        return SqliteUnitOfWork(self.path)

    def bind(self, uow: SqliteUnitOfWork) -> "Repository":
        applications = self._owners["applications"].bind(uow)
        return Repository(
            self.path,
            _owners={
                "applications": applications,
                "preparation": SqlitePreparationRepository(
                    self.path, uow.connection, applications
                ),
                "artifacts": self._owners["artifacts"].bind(uow),
                "tracking": SqliteTrackingRepository(
                    self.path, uow.connection, applications
                ),
                "audit": self._owners["audit"].bind(uow),
            },
        )

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        with self._owners["applications"].transaction() as connection:
            yield connection
