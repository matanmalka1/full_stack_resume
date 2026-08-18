from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...domain.models import ApplicationStatus
from ...util import canonical_json, utc_now
from .applications import SqliteApplicationRepository
from .base import SqliteRepositoryBase
from .connection import SqliteUnitOfWork
from .primitives import new_id


class SqliteTrackingRepository(SqliteRepositoryBase):
    def __init__(
        self,
        path: Path,
        connection: Any | None = None,
        applications: SqliteApplicationRepository | None = None,
    ):
        super().__init__(path, connection)
        self.applications = applications or SqliteApplicationRepository(path, connection)

    def bind(self, uow: SqliteUnitOfWork) -> "SqliteTrackingRepository":
        if uow.connection is None:
            raise RuntimeError("UnitOfWork is not active")
        if uow.path.resolve() != self.path.resolve():
            raise ValueError("UnitOfWork belongs to another database")
        return type(self)(self.path, uow.connection, self.applications.bind(uow))

    def set_ready(
        self,
        application_id: str,
        pdf_artifact_version_id: str,
        reason: str = "",
    ) -> None:
        self._set_ready(application_id, pdf_artifact_version_id, reason)

    def record_submission(
        self,
        application_id: str,
        pdf_artifact_version_id: str,
        reason: str = "",
    ) -> str:
        return self._record_submission(
            application_id, pdf_artifact_version_id, reason
        )

    def _set_ready(
        self,
        application_id: str,
        pdf_artifact_version_id: str,
        reason: str = "",
    ) -> None:
        now = utc_now()
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT current_status FROM applications WHERE id=?", (application_id,)
            ).fetchone()
            if row is None:
                raise KeyError(application_id)
            current = ApplicationStatus(row["current_status"])
            if current not in (ApplicationStatus.PREPARING, ApplicationStatus.READY):
                raise ValueError(f"ready may only follow preparing, not {current.value}")
            pdf_row = connection.execute(
                "SELECT av.id FROM artifact_versions av JOIN artifacts a ON a.id=av.artifact_id "
                "WHERE av.id=? AND a.application_id=? AND a.artifact_type='resume_pdf' "
                "AND av.lifecycle_status='rendered'",
                (pdf_artifact_version_id, application_id),
            ).fetchone()
            if pdf_row is None:
                raise ValueError(
                    "ready requires an exact rendered resume PDF artifact version belonging to this application"
                )
            validation_row = connection.execute(
                "SELECT report_json FROM validation_runs WHERE application_id=? "
                "AND phase='post-render' AND artifact_version_id=? "
                "ORDER BY created_at DESC LIMIT 1",
                (application_id, pdf_artifact_version_id),
            ).fetchone()
            if validation_row is None:
                raise ValueError(
                    "ready requires a post-render validation referencing this exact PDF artifact version"
                )
            if not json.loads(validation_row["report_json"]).get("passed"):
                raise ValueError(
                    "ready requires a passing post-render validation for this exact PDF artifact version"
                )
            if current is ApplicationStatus.READY:
                return
            self.applications._set_status(
                connection,
                application_id,
                current,
                ApplicationStatus.READY,
                now,
                reason,
            )

    def _record_submission(
        self,
        application_id: str,
        pdf_artifact_version_id: str,
        reason: str = "",
    ) -> str:
        now = utc_now()
        submission_id = new_id()
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT current_status FROM applications WHERE id=?", (application_id,)
            ).fetchone()
            if row is None:
                raise KeyError(application_id)
            current = ApplicationStatus(row["current_status"])
            if current is not ApplicationStatus.READY:
                raise ValueError(f"applied may only follow ready, not {current.value}")
            pdf_row = connection.execute(
                "SELECT av.id FROM artifact_versions av JOIN artifacts a ON a.id=av.artifact_id "
                "WHERE av.id=? AND a.application_id=? AND a.artifact_type='resume_pdf' "
                "AND av.lifecycle_status='rendered'",
                (pdf_artifact_version_id, application_id),
            ).fetchone()
            if pdf_row is None:
                raise ValueError(
                    "submission requires an exact rendered resume PDF artifact version belonging to this application"
                )
            connection.execute(
                "INSERT INTO submissions(id, application_id, artifact_version_id, submitted_at, metadata_json) "
                "VALUES(?, ?, ?, ?, ?)",
                (
                    submission_id,
                    application_id,
                    pdf_artifact_version_id,
                    now,
                    canonical_json({"reason": reason}),
                ),
            )
            self.applications._set_status(
                connection,
                application_id,
                current,
                ApplicationStatus.APPLIED,
                now,
                reason,
            )
        return submission_id
