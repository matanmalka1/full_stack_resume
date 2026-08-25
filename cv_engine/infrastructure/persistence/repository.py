from __future__ import annotations

from sqlalchemy.engine import Connection, Engine

from .applications import SqlAlchemyApplicationRepository
from .artifacts import SqlAlchemyArtifactRepository
from .audit import SqlAlchemyAuditRepository
from .connection import SqlAlchemyUnitOfWork
from .drafts import SqlAlchemyDraftRepository
from .knowledge import SqlAlchemyKnowledgeMutationRepository
from .operations import SqlAlchemyOperationRepository
from .preparation import SqlAlchemyPreparationRepository
from .settings import SqlAlchemySettingsRepository
from .tracking import SqlAlchemyTrackingRepository


class Repository(
    SqlAlchemyPreparationRepository,
    SqlAlchemyApplicationRepository,
    SqlAlchemyArtifactRepository,
    SqlAlchemyDraftRepository,
    SqlAlchemyTrackingRepository,
    SqlAlchemyAuditRepository,
    SqlAlchemyOperationRepository,
    SqlAlchemyKnowledgeMutationRepository,
    SqlAlchemySettingsRepository,
):
    """The SQLAlchemy adapter, composed from the ownership repositories.

    Each repository keeps its own tables and its own SQL; this class only
    states which of them make up the composition root's view of storage. The
    composition is inherited rather than delegated, so a method added to an
    owner is reachable here without being registered anywhere.
    """

    def __init__(
        self,
        engine: Engine,
        connection: Connection | None = None,
        applications: SqlAlchemyApplicationRepository | None = None,
    ):
        super().__init__(engine, connection, applications)

    def unit_of_work(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self.engine)
