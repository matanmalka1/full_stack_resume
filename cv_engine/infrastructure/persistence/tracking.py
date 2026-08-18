from __future__ import annotations

from pathlib import Path
from typing import Any

from ...util import canonical_json
from .base import SqliteRepositoryBase
from .connection import SqliteUnitOfWork


class SqliteTrackingRepository(SqliteRepositoryBase):
    def __init__(
        self,
        path: Path,
        connection: Any | None = None,
    ):
        super().__init__(path, connection)

    def bind(self, uow: SqliteUnitOfWork) -> SqliteTrackingRepository:
        if uow.connection is None:
            raise RuntimeError("UnitOfWork is not active")
        if uow.path.resolve() != self.path.resolve():
            raise ValueError("UnitOfWork belongs to another database")
        return type(self)(self.path, uow.connection)

    def insert_submission(
        self,
        submission_id: str,
        application_id: str,
        artifact_version_id: str,
        submitted_at: str,
        metadata: dict[str, Any],
    ) -> None:
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO submissions(id, application_id, artifact_version_id, submitted_at, metadata_json) "
                "VALUES(?, ?, ?, ?, ?)",
                (
                    submission_id,
                    application_id,
                    artifact_version_id,
                    submitted_at,
                    canonical_json(metadata),
                ),
            )
