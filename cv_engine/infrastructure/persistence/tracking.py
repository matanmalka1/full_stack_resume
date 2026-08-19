from __future__ import annotations

from typing import Any

from ...util import canonical_json
from .base import SqliteRepositoryBase


class SqliteTrackingRepository(SqliteRepositoryBase):
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
