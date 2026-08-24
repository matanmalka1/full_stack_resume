from __future__ import annotations

from pathlib import Path
from typing import Any

from .applications import SqliteApplicationRepository
from .artifacts import SqliteArtifactRepository
from .audit import SqliteAuditRepository
from .connection import SqliteUnitOfWork
from .drafts import SqliteDraftRepository
from .knowledge import SqliteKnowledgeMutationRepository
from .operations import SqliteOperationRepository
from .preparation import SqlitePreparationRepository
from .schema import ensure_current_schema
from .settings import SqliteSettingsRepository
from .tracking import SqliteTrackingRepository


class Repository(
    SqlitePreparationRepository,
    SqliteApplicationRepository,
    SqliteArtifactRepository,
    SqliteDraftRepository,
    SqliteTrackingRepository,
    SqliteAuditRepository,
    SqliteOperationRepository,
    SqliteKnowledgeMutationRepository,
    SqliteSettingsRepository,
):
    """The SQLite adapter, composed from the five ownership repositories.

    Each repository keeps its own tables and its own SQL; this class only
    states which of them make up the composition root's view of storage. The
    composition is inherited rather than delegated, so a method added to an
    owner is reachable here without being registered anywhere.
    """

    def __init__(
        self,
        path: Path,
        connection: Any | None = None,
        applications: SqliteApplicationRepository | None = None,
    ):
        if connection is None:
            ensure_current_schema(Path(path))
        super().__init__(path, connection, applications)

    def unit_of_work(self) -> SqliteUnitOfWork:
        return SqliteUnitOfWork(self.path)
