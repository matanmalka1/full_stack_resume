from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .models import ApplicationStatus, JobAnalysis, ValidationReport
from .util import canonical_json, sha256_text, utc_now


SCHEMA_VERSION = "1"

IMMUTABLE_TABLES = (
    "job_snapshots",
    "job_analyses",
    "status_history",
    "application_events",
    "artifact_versions",
    "decision_records",
    "generation_runs",
    "validation_runs",
    "migration_runs",
    "submissions",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS applications (
    id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    target_role TEXT NOT NULL,
    normalized_role TEXT,
    source_url TEXT,
    language TEXT CHECK (language IN ('en', 'he')),
    track TEXT,
    profile TEXT,
    emphasis TEXT,
    classification_confidence REAL,
    fit_level TEXT,
    current_status TEXT NOT NULL,
    last_contact_date TEXT,
    next_action TEXT,
    next_action_date TEXT,
    notes TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_snapshots (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    original_text TEXT NOT NULL,
    source_url TEXT,
    captured_at TEXT NOT NULL,
    source_metadata_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    prior_snapshot_id TEXT REFERENCES job_snapshots(id),
    UNIQUE(application_id, version_number),
    UNIQUE(application_id, content_hash)
);

CREATE TABLE IF NOT EXISTS job_analyses (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    job_snapshot_id TEXT NOT NULL REFERENCES job_snapshots(id),
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    structured_json TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(application_id, version_number)
);

CREATE TABLE IF NOT EXISTS status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id TEXT NOT NULL REFERENCES applications(id),
    from_status TEXT,
    to_status TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS application_events (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    application_id TEXT REFERENCES applications(id),
    artifact_type TEXT NOT NULL,
    logical_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(application_id, artifact_type, logical_name)
);

CREATE TABLE IF NOT EXISTS artifact_versions (
    id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL REFERENCES artifacts(id),
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    lifecycle_status TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    approved_at TEXT,
    submitted_at TEXT,
    track TEXT,
    profile TEXT,
    emphasis TEXT,
    facts_version TEXT,
    job_snapshot_id TEXT REFERENCES job_snapshots(id),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(artifact_id, version_number)
);

CREATE TABLE IF NOT EXISTS decision_records (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    artifact_version_id TEXT REFERENCES artifact_versions(id),
    job_snapshot_id TEXT NOT NULL REFERENCES job_snapshots(id),
    job_analysis_id TEXT NOT NULL REFERENCES job_analyses(id),
    structured_json TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generation_runs (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    created_at TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    profile_version TEXT NOT NULL,
    rendering_rules_version TEXT NOT NULL,
    facts_version TEXT NOT NULL,
    ai_provider TEXT NOT NULL,
    ai_model TEXT NOT NULL,
    task_contract_version TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    job_analysis_version TEXT NOT NULL,
    instruction_overrides_json TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS validation_runs (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    artifact_version_id TEXT REFERENCES artifact_versions(id),
    phase TEXT NOT NULL,
    report_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS migration_runs (
    id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL,
    manifest_hash TEXT NOT NULL,
    dry_run_report_hash TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    artifact_count INTEGER NOT NULL,
    report_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS submissions (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    artifact_version_id TEXT NOT NULL UNIQUE REFERENCES artifact_versions(id),
    submitted_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_snapshots_application ON job_snapshots(application_id);
CREATE INDEX IF NOT EXISTS idx_analyses_application ON job_analyses(application_id);
CREATE INDEX IF NOT EXISTS idx_status_application ON status_history(application_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_application ON artifacts(application_id);
CREATE INDEX IF NOT EXISTS idx_versions_artifact ON artifact_versions(artifact_id);
"""


ALLOWED_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.SAVED: {ApplicationStatus.PREPARING, ApplicationStatus.WITHDRAWN, ApplicationStatus.CLOSED},
    ApplicationStatus.PREPARING: {ApplicationStatus.READY, ApplicationStatus.WITHDRAWN, ApplicationStatus.CLOSED},
    ApplicationStatus.READY: {ApplicationStatus.PREPARING, ApplicationStatus.APPLIED, ApplicationStatus.WITHDRAWN, ApplicationStatus.CLOSED},
    ApplicationStatus.APPLIED: {ApplicationStatus.RECRUITER_SCREEN, ApplicationStatus.INTERVIEW, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN, ApplicationStatus.CLOSED},
    ApplicationStatus.RECRUITER_SCREEN: {ApplicationStatus.INTERVIEW, ApplicationStatus.ASSIGNMENT, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN, ApplicationStatus.CLOSED},
    ApplicationStatus.INTERVIEW: {ApplicationStatus.ASSIGNMENT, ApplicationStatus.FINAL_STAGE, ApplicationStatus.OFFER, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN, ApplicationStatus.CLOSED},
    ApplicationStatus.ASSIGNMENT: {ApplicationStatus.INTERVIEW, ApplicationStatus.FINAL_STAGE, ApplicationStatus.OFFER, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN, ApplicationStatus.CLOSED},
    ApplicationStatus.FINAL_STAGE: {ApplicationStatus.OFFER, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN, ApplicationStatus.CLOSED},
    ApplicationStatus.OFFER: {ApplicationStatus.ACCEPTED, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN, ApplicationStatus.CLOSED},
    ApplicationStatus.ACCEPTED: {ApplicationStatus.CLOSED},
    ApplicationStatus.REJECTED: {ApplicationStatus.CLOSED},
    ApplicationStatus.WITHDRAWN: {ApplicationStatus.CLOSED},
    ApplicationStatus.CLOSED: set(),
}


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def initialize(path: Path) -> None:
    with connect(path) as connection:
        connection.executescript(SCHEMA)
        connection.execute(
            "INSERT INTO schema_meta(key, value) VALUES('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (SCHEMA_VERSION,),
        )
        for table in IMMUTABLE_TABLES:
            connection.execute(
                f"CREATE TRIGGER IF NOT EXISTS no_update_{table} BEFORE UPDATE ON {table} "
                "BEGIN SELECT RAISE(ABORT, 'immutable record'); END"
            )
            connection.execute(
                f"CREATE TRIGGER IF NOT EXISTS no_delete_{table} BEFORE DELETE ON {table} "
                "BEGIN SELECT RAISE(ABORT, 'immutable record'); END"
            )


class Repository:
    def __init__(self, path: Path):
        self.path = path
        initialize(path)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = connect(self.path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create_application(
        self,
        *,
        company: str,
        target_role: str,
        original_job_text: str,
        source_url: str | None = None,
        source: str = "manual",
        notes: str = "",
        application_id: str | None = None,
        snapshot_id: str | None = None,
        captured_at: str | None = None,
        source_metadata: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        if not company.strip() or not target_role.strip() or not original_job_text.strip():
            raise ValueError("company, target role, and full job text are required")
        app_id = application_id or str(uuid.uuid4())
        snap_id = snapshot_id or str(uuid.uuid4())
        now = captured_at or utc_now()
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO applications(id, company, target_role, source_url, current_status, notes, source, created_at, updated_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (app_id, company.strip(), target_role.strip(), source_url, ApplicationStatus.SAVED.value, notes, source, now, now),
            )
            connection.execute(
                "INSERT INTO job_snapshots(id, application_id, version_number, original_text, source_url, captured_at, source_metadata_json, content_hash, prior_snapshot_id) "
                "VALUES(?, ?, 1, ?, ?, ?, ?, ?, NULL)",
                (snap_id, app_id, original_job_text, source_url, now, canonical_json(source_metadata or {}), sha256_text(original_job_text)),
            )
            connection.execute(
                "INSERT INTO status_history(application_id, from_status, to_status, changed_at, reason) VALUES(?, NULL, ?, ?, ?)",
                (app_id, ApplicationStatus.SAVED.value, now, "application created"),
            )
        return app_id, snap_id

    def add_job_snapshot(
        self,
        application_id: str,
        original_text: str,
        source_url: str | None = None,
        source_metadata: dict[str, Any] | None = None,
    ) -> str:
        with self.transaction() as connection:
            prior = connection.execute(
                "SELECT id, version_number FROM job_snapshots WHERE application_id=? ORDER BY version_number DESC LIMIT 1",
                (application_id,),
            ).fetchone()
            if prior is None:
                raise KeyError(application_id)
            snapshot_id = str(uuid.uuid4())
            connection.execute(
                "INSERT INTO job_snapshots(id, application_id, version_number, original_text, source_url, captured_at, source_metadata_json, content_hash, prior_snapshot_id) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (snapshot_id, application_id, prior["version_number"] + 1, original_text, source_url, utc_now(), canonical_json(source_metadata or {}), sha256_text(original_text), prior["id"]),
            )
        return snapshot_id

    def get_application(self, application_id: str) -> dict[str, Any]:
        with connect(self.path) as connection:
            row = connection.execute("SELECT * FROM applications WHERE id=?", (application_id,)).fetchone()
        if row is None:
            raise KeyError(application_id)
        return dict(row)

    def list_applications(self) -> list[dict[str, Any]]:
        with connect(self.path) as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM applications ORDER BY created_at, id")]

    def latest_snapshot(self, application_id: str) -> dict[str, Any]:
        with connect(self.path) as connection:
            row = connection.execute(
                "SELECT * FROM job_snapshots WHERE application_id=? ORDER BY version_number DESC LIMIT 1",
                (application_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"no snapshot for application {application_id}")
        return dict(row)

    def save_analysis(
        self,
        application_id: str,
        snapshot_id: str,
        analysis: JobAnalysis,
        *,
        provider: str = "deterministic",
        model: str = "rules-v1",
    ) -> str:
        analysis_id = str(uuid.uuid4())
        now = utc_now()
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 AS version FROM job_analyses WHERE application_id=?",
                (application_id,),
            ).fetchone()
            connection.execute(
                "INSERT INTO job_analyses(id, application_id, job_snapshot_id, version_number, structured_json, provider, model, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (analysis_id, application_id, snapshot_id, row["version"], analysis.model_dump_json(), provider, model, now),
            )
            connection.execute(
                "UPDATE applications SET language=?, track=?, profile=?, emphasis=?, classification_confidence=?, fit_level=?, updated_at=? WHERE id=?",
                (analysis.language, analysis.track.value, analysis.profile.value, analysis.emphasis.value, analysis.confidence, analysis.fit.value, now, application_id),
            )
        current = ApplicationStatus(self.get_application(application_id)["current_status"])
        if current is ApplicationStatus.SAVED:
            self.transition_status(application_id, ApplicationStatus.PREPARING, "analysis created")
        return analysis_id

    def latest_analysis(self, application_id: str) -> tuple[str, JobAnalysis]:
        with connect(self.path) as connection:
            row = connection.execute(
                "SELECT id, structured_json FROM job_analyses WHERE application_id=? ORDER BY version_number DESC LIMIT 1",
                (application_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"no analysis for application {application_id}")
        return row["id"], JobAnalysis.model_validate_json(row["structured_json"])

    def transition_status(self, application_id: str, target: ApplicationStatus | str, reason: str = "") -> None:
        target_status = ApplicationStatus(target)
        if target_status is ApplicationStatus.READY:
            raise ValueError(
                "ready is an engine-owned state derived from a passing render/ready "
                "pipeline; it cannot be set through the generic status transition. "
                "Use the render pipeline (Engine.render)."
            )
        if target_status is ApplicationStatus.APPLIED:
            raise ValueError(
                "applied is submission-owned; it can only be reached through "
                "Engine.submit(), which performs fresh ready integrity verification "
                "and binds the submission to the exact validated PDF artifact version. "
                "The generic status transition never accepts applied, even with a real "
                "rendered PDF artifact version id, because it cannot perform that "
                "verification itself."
            )
        now = utc_now()
        with self.transaction() as connection:
            row = connection.execute("SELECT current_status FROM applications WHERE id=?", (application_id,)).fetchone()
            if row is None:
                raise KeyError(application_id)
            current = ApplicationStatus(row["current_status"])
            if target_status is current:
                return
            if target_status not in ALLOWED_TRANSITIONS[current]:
                raise ValueError(f"invalid status transition: {current.value} -> {target_status.value}")
            connection.execute(
                "UPDATE applications SET current_status=?, updated_at=? WHERE id=?",
                (target_status.value, now, application_id),
            )
            connection.execute(
                "INSERT INTO status_history(application_id, from_status, to_status, changed_at, reason) VALUES(?, ?, ?, ?, ?)",
                (application_id, current.value, target_status.value, now, reason),
            )

    def _set_ready(self, application_id: str, pdf_artifact_version_id: str, reason: str = "") -> None:
        """Internal persistence primitive. NOT a verification API.

        This is not part of the supported Repository contract and must only be
        called by Engine.render(), immediately after Engine.render() has itself
        run cv_engine.ready.verify_ready_integrity() fresh (with filesystem
        access this DB-only method does not have) and confirmed it passed for
        the PDF artifact version Engine.render() just created in the same call.

        The DB-only checks below (a passing post-render validation referencing
        this exact PDF artifact version) are necessary but NOT sufficient proof
        of readiness on their own: a historical passing validation row does not
        prove the referenced files still exist unmodified, or that no newer
        approved version/job snapshot/analysis has since superseded them. That
        freshness burden belongs entirely to the caller. Calling this method
        directly with a stale-but-historically-valid id bypasses that guarantee
        the same way raw SQL against an immutable table would; it is not a
        reachable path from the CLI or any other public Engine method.
        """
        now = utc_now()
        with self.transaction() as connection:
            row = connection.execute("SELECT current_status FROM applications WHERE id=?", (application_id,)).fetchone()
            if row is None:
                raise KeyError(application_id)
            current = ApplicationStatus(row["current_status"])
            if current not in (ApplicationStatus.PREPARING, ApplicationStatus.READY):
                raise ValueError(f"ready may only follow preparing, not {current.value}")
            pdf_row = connection.execute(
                "SELECT av.id FROM artifact_versions av JOIN artifacts a ON a.id=av.artifact_id "
                "WHERE av.id=? AND a.application_id=? AND a.artifact_type='resume_pdf' AND av.lifecycle_status='rendered'",
                (pdf_artifact_version_id, application_id),
            ).fetchone()
            if pdf_row is None:
                raise ValueError("ready requires an exact rendered resume PDF artifact version belonging to this application")
            validation_row = connection.execute(
                "SELECT report_json FROM validation_runs WHERE application_id=? AND phase='post-render' AND artifact_version_id=? "
                "ORDER BY created_at DESC LIMIT 1",
                (application_id, pdf_artifact_version_id),
            ).fetchone()
            if validation_row is None:
                raise ValueError("ready requires a post-render validation referencing this exact PDF artifact version")
            if not json.loads(validation_row["report_json"]).get("passed"):
                raise ValueError("ready requires a passing post-render validation for this exact PDF artifact version")
            if current is ApplicationStatus.READY:
                return
            connection.execute(
                "UPDATE applications SET current_status=?, updated_at=? WHERE id=?",
                (ApplicationStatus.READY.value, now, application_id),
            )
            connection.execute(
                "INSERT INTO status_history(application_id, from_status, to_status, changed_at, reason) VALUES(?, ?, ?, ?, ?)",
                (application_id, current.value, ApplicationStatus.READY.value, now, reason),
            )

    def _record_submission(self, application_id: str, pdf_artifact_version_id: str, reason: str = "") -> str:
        """Internal persistence primitive. NOT a verification API.

        Not part of the supported Repository contract; must only be called by
        Engine.submit() immediately after Engine.submit() has run
        cv_engine.ready.verify_ready_integrity() fresh and confirmed the exact
        PDF artifact version it is about to bind. The DB-only check here (the
        PDF artifact version belongs to this application and is a rendered
        resume PDF) does not by itself prove that version is the CURRENT ready
        one: an older PDF's lifecycle_status stays 'rendered' forever even
        after a newer approved version supersedes it. That freshness and
        currency burden belongs entirely to the caller.
        """
        now = utc_now()
        submission_id = str(uuid.uuid4())
        with self.transaction() as connection:
            row = connection.execute("SELECT current_status FROM applications WHERE id=?", (application_id,)).fetchone()
            if row is None:
                raise KeyError(application_id)
            current = ApplicationStatus(row["current_status"])
            if current is not ApplicationStatus.READY:
                raise ValueError(f"applied may only follow ready, not {current.value}")
            pdf_row = connection.execute(
                "SELECT av.id FROM artifact_versions av JOIN artifacts a ON a.id=av.artifact_id "
                "WHERE av.id=? AND a.application_id=? AND a.artifact_type='resume_pdf' AND av.lifecycle_status='rendered'",
                (pdf_artifact_version_id, application_id),
            ).fetchone()
            if pdf_row is None:
                raise ValueError(
                    "submission requires an exact rendered resume PDF artifact version belonging to this application"
                )
            connection.execute(
                "INSERT INTO submissions(id, application_id, artifact_version_id, submitted_at, metadata_json) VALUES(?, ?, ?, ?, ?)",
                (submission_id, application_id, pdf_artifact_version_id, now, canonical_json({"reason": reason})),
            )
            connection.execute(
                "UPDATE applications SET current_status=?, updated_at=? WHERE id=?",
                (ApplicationStatus.APPLIED.value, now, application_id),
            )
            connection.execute(
                "INSERT INTO status_history(application_id, from_status, to_status, changed_at, reason) VALUES(?, ?, ?, ?, ?)",
                (application_id, current.value, ApplicationStatus.APPLIED.value, now, reason),
            )
        return submission_id

    def record_event(self, application_id: str, event_type: str, payload: dict[str, Any]) -> str:
        event_id = str(uuid.uuid4())
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO application_events(id, application_id, event_type, payload_json, created_at) VALUES(?, ?, ?, ?, ?)",
                (event_id, application_id, event_type, canonical_json(payload), utc_now()),
            )
        return event_id

    def set_next_action(self, application_id: str, action: str | None, action_date: str | None) -> None:
        with self.transaction() as connection:
            result = connection.execute(
                "UPDATE applications SET next_action=?, next_action_date=?, updated_at=? WHERE id=?",
                (action, action_date, utc_now(), application_id),
            )
            if result.rowcount != 1:
                raise KeyError(application_id)
        self.record_event(application_id, "next_action_set", {"next_action": action, "next_action_date": action_date})

    def set_normalized_role(self, application_id: str, normalized_role: str) -> None:
        with self.transaction() as connection:
            result = connection.execute(
                "UPDATE applications SET normalized_role=?, updated_at=? WHERE id=?",
                (normalized_role, utc_now(), application_id),
            )
            if result.rowcount != 1:
                raise KeyError(application_id)

    def register_artifact_version(
        self,
        application_id: str | None,
        artifact_type: str,
        logical_name: str,
        path: str,
        content_hash: str,
        lifecycle_status: str,
        *,
        job_snapshot_id: str | None = None,
        track: str | None = None,
        profile: str | None = None,
        emphasis: str | None = None,
        facts_version: str | None = None,
        metadata: dict[str, Any] | None = None,
        approved_at: str | None = None,
        submitted_at: str | None = None,
    ) -> str:
        version_id = str(uuid.uuid4())
        now = utc_now()
        with self.transaction() as connection:
            artifact = connection.execute(
                "SELECT id FROM artifacts WHERE application_id IS ? AND artifact_type=? AND logical_name=?",
                (application_id, artifact_type, logical_name),
            ).fetchone()
            if artifact is None:
                artifact_id = str(uuid.uuid4())
                connection.execute(
                    "INSERT INTO artifacts(id, application_id, artifact_type, logical_name, created_at) VALUES(?, ?, ?, ?, ?)",
                    (artifact_id, application_id, artifact_type, logical_name, now),
                )
            else:
                artifact_id = artifact["id"]
            version = connection.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 AS version FROM artifact_versions WHERE artifact_id=?",
                (artifact_id,),
            ).fetchone()["version"]
            connection.execute(
                "INSERT INTO artifact_versions(id, artifact_id, version_number, lifecycle_status, path, content_hash, created_at, approved_at, submitted_at, track, profile, emphasis, facts_version, job_snapshot_id, metadata_json) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (version_id, artifact_id, version, lifecycle_status, path, content_hash, now, approved_at, submitted_at, track, profile, emphasis, facts_version, job_snapshot_id, canonical_json(metadata or {})),
            )
        return version_id

    def latest_artifact_version(
        self,
        application_id: str,
        artifact_type: str,
        lifecycle_status: str | None = None,
    ) -> dict[str, Any]:
        query = (
            "SELECT av.*, a.artifact_type, a.logical_name FROM artifact_versions av "
            "JOIN artifacts a ON a.id=av.artifact_id "
            "WHERE a.application_id=? AND a.artifact_type=?"
        )
        params: list[Any] = [application_id, artifact_type]
        if lifecycle_status:
            query += " AND av.lifecycle_status=?"
            params.append(lifecycle_status)
        query += " ORDER BY av.created_at DESC, av.version_number DESC LIMIT 1"
        with connect(self.path) as connection:
            row = connection.execute(query, params).fetchone()
        if row is None:
            raise KeyError(f"no {artifact_type} artifact for application {application_id}")
        return dict(row)

    def artifact_versions(self, application_id: str) -> list[dict[str, Any]]:
        with connect(self.path) as connection:
            rows = connection.execute(
                "SELECT av.*, a.artifact_type, a.logical_name FROM artifact_versions av "
                "JOIN artifacts a ON a.id=av.artifact_id WHERE a.application_id=? "
                "ORDER BY av.created_at, av.version_number",
                (application_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_decision(
        self,
        application_id: str,
        artifact_version_id: str,
        job_snapshot_id: str,
        job_analysis_id: str,
        structured: dict[str, Any],
        summary: str,
    ) -> str:
        decision_id = str(uuid.uuid4())
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO decision_records(id, application_id, artifact_version_id, job_snapshot_id, job_analysis_id, structured_json, summary, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (decision_id, application_id, artifact_version_id, job_snapshot_id, job_analysis_id, canonical_json(structured), summary, utc_now()),
            )
        return decision_id

    def latest_decision(self, application_id: str) -> dict[str, Any]:
        with connect(self.path) as connection:
            row = connection.execute(
                "SELECT * FROM decision_records WHERE application_id=? ORDER BY created_at DESC LIMIT 1",
                (application_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"no decision record for application {application_id}")
        return dict(row)

    def decision_for_artifact_version(self, artifact_version_id: str) -> dict[str, Any]:
        with connect(self.path) as connection:
            row = connection.execute(
                "SELECT * FROM decision_records WHERE artifact_version_id=? ORDER BY created_at DESC LIMIT 1",
                (artifact_version_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"no decision record for artifact version {artifact_version_id}")
        return dict(row)

    def record_generation_run(self, values: dict[str, Any]) -> str:
        run_id = values.get("id") or str(uuid.uuid4())
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO generation_runs(id, application_id, created_at, engine_version, profile_version, rendering_rules_version, facts_version, ai_provider, ai_model, task_contract_version, prompt_version, job_analysis_version, instruction_overrides_json, status) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    values["application_id"],
                    values.get("created_at", utc_now()),
                    values["engine_version"],
                    values["profile_version"],
                    values["rendering_rules_version"],
                    values["facts_version"],
                    values["ai_provider"],
                    values["ai_model"],
                    values["task_contract_version"],
                    values["prompt_version"],
                    values["job_analysis_version"],
                    canonical_json(values.get("instruction_overrides", {})),
                    values.get("status", "completed"),
                ),
            )
        return run_id

    def record_validation(
        self,
        application_id: str,
        phase: str,
        report: ValidationReport,
        artifact_version_id: str | None = None,
    ) -> str:
        validation_id = str(uuid.uuid4())
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO validation_runs(id, application_id, artifact_version_id, phase, report_json, created_at) VALUES(?, ?, ?, ?, ?, ?)",
                (validation_id, application_id, artifact_version_id, phase, report.model_dump_json(), utc_now()),
            )
        return validation_id

    def latest_validation(self, application_id: str, phase: str | None = None) -> ValidationReport:
        query = "SELECT report_json FROM validation_runs WHERE application_id=?"
        params: list[Any] = [application_id]
        if phase:
            query += " AND phase=?"
            params.append(phase)
        query += " ORDER BY created_at DESC LIMIT 1"
        with connect(self.path) as connection:
            row = connection.execute(query, params).fetchone()
        if row is None:
            raise KeyError(f"no validation report for application {application_id}")
        return ValidationReport.model_validate_json(row["report_json"])

    def validation_for_artifact(self, application_id: str, phase: str, artifact_version_id: str) -> ValidationReport:
        with connect(self.path) as connection:
            row = connection.execute(
                "SELECT report_json FROM validation_runs WHERE application_id=? AND phase=? AND artifact_version_id=? "
                "ORDER BY created_at DESC LIMIT 1",
                (application_id, phase, artifact_version_id),
            ).fetchone()
        if row is None:
            raise KeyError(f"no {phase} validation references artifact version {artifact_version_id}")
        return ValidationReport.model_validate_json(row["report_json"])

    def integrity_check(self) -> list[str]:
        problems: list[str] = []
        with connect(self.path) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if result != "ok":
                problems.append(f"SQLite integrity_check: {result}")
            fk_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
            problems.extend(f"foreign key violation: {tuple(row)}" for row in fk_rows)
        return problems
