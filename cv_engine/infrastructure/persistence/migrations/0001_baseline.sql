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

CREATE TABLE IF NOT EXISTS fact_events (
    id TEXT PRIMARY KEY,
    fact_id TEXT NOT NULL,
    source_file TEXT NOT NULL,
    event_type TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    application_id TEXT REFERENCES applications(id),
    claim_id TEXT,
    reason TEXT NOT NULL DEFAULT '',
    fact_json TEXT NOT NULL,
    fact_hash TEXT NOT NULL,
    facts_version TEXT NOT NULL,
    lifecycle_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_application ON job_snapshots(application_id);
CREATE INDEX IF NOT EXISTS idx_fact_events_fact ON fact_events(fact_id);
CREATE INDEX IF NOT EXISTS idx_analyses_application ON job_analyses(application_id);
CREATE INDEX IF NOT EXISTS idx_status_application ON status_history(application_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_application ON artifacts(application_id);
CREATE INDEX IF NOT EXISTS idx_versions_artifact ON artifact_versions(artifact_id);

CREATE TRIGGER IF NOT EXISTS no_update_fact_events BEFORE UPDATE ON fact_events BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_fact_events BEFORE DELETE ON fact_events BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_update_job_snapshots BEFORE UPDATE ON job_snapshots BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_job_snapshots BEFORE DELETE ON job_snapshots BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_update_job_analyses BEFORE UPDATE ON job_analyses BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_job_analyses BEFORE DELETE ON job_analyses BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_update_status_history BEFORE UPDATE ON status_history BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_status_history BEFORE DELETE ON status_history BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_update_application_events BEFORE UPDATE ON application_events BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_application_events BEFORE DELETE ON application_events BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_update_artifact_versions BEFORE UPDATE ON artifact_versions BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_artifact_versions BEFORE DELETE ON artifact_versions BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_update_decision_records BEFORE UPDATE ON decision_records BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_decision_records BEFORE DELETE ON decision_records BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_update_generation_runs BEFORE UPDATE ON generation_runs BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_generation_runs BEFORE DELETE ON generation_runs BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_update_validation_runs BEFORE UPDATE ON validation_runs BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_validation_runs BEFORE DELETE ON validation_runs BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_update_migration_runs BEFORE UPDATE ON migration_runs BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_migration_runs BEFORE DELETE ON migration_runs BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_update_submissions BEFORE UPDATE ON submissions BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_submissions BEFORE DELETE ON submissions BEGIN SELECT RAISE(ABORT, 'immutable record'); END;

INSERT INTO schema_meta(key, value) VALUES('schema_version', '2')
ON CONFLICT(key) DO UPDATE SET value=excluded.value;
