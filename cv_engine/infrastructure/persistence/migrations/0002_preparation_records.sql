ALTER TABLE job_snapshots ADD COLUMN payload_path TEXT;
ALTER TABLE job_snapshots ADD COLUMN source_hash TEXT;
ALTER TABLE job_snapshots ADD COLUMN normalized_hash TEXT;

CREATE TABLE selection_plans (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    job_analysis_id TEXT NOT NULL REFERENCES job_analyses(id),
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    plan_json TEXT NOT NULL,
    candidate_context_version TEXT NOT NULL,
    candidate_context_hash TEXT NOT NULL,
    profile_version TEXT NOT NULL,
    selection_policy_version TEXT NOT NULL,
    track_emphasis_dependencies_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(application_id, version_number)
);

CREATE TRIGGER no_update_selection_plans BEFORE UPDATE ON selection_plans
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

CREATE TRIGGER no_delete_selection_plans BEFORE DELETE ON selection_plans
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

CREATE TABLE working_drafts (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    job_analysis_id TEXT NOT NULL REFERENCES job_analyses(id),
    selection_plan_id TEXT NOT NULL REFERENCES selection_plans(id),
    parent_revision_id TEXT,
    source_json TEXT NOT NULL,
    edit_version INTEGER NOT NULL CHECK (edit_version > 0),
    content_hash TEXT NOT NULL,
    active INTEGER NOT NULL CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX one_active_working_draft_per_application
ON working_drafts(application_id) WHERE active = 1;

ALTER TABLE validation_runs ADD COLUMN working_draft_id TEXT REFERENCES working_drafts(id);
ALTER TABLE validation_runs ADD COLUMN edit_version INTEGER;
ALTER TABLE validation_runs ADD COLUMN content_hash TEXT;
ALTER TABLE validation_runs ADD COLUMN job_snapshot_id TEXT REFERENCES job_snapshots(id);
ALTER TABLE validation_runs ADD COLUMN job_analysis_id TEXT REFERENCES job_analyses(id);
ALTER TABLE validation_runs ADD COLUMN selection_plan_id TEXT REFERENCES selection_plans(id);
ALTER TABLE validation_runs ADD COLUMN knowledge_context_hash TEXT;
ALTER TABLE validation_runs ADD COLUMN validator_versions_json TEXT;
