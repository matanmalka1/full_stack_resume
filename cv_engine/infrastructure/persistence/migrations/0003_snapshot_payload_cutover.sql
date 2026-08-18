DROP TRIGGER no_update_job_snapshots;
DROP TRIGGER no_delete_job_snapshots;

CREATE TABLE job_snapshots_new (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    payload_path TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    normalized_hash TEXT NOT NULL,
    source_url TEXT,
    captured_at TEXT NOT NULL,
    source_metadata_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    prior_snapshot_id TEXT REFERENCES job_snapshots_new(id),
    UNIQUE(application_id, version_number),
    UNIQUE(application_id, content_hash)
);

INSERT INTO job_snapshots_new(
    id, application_id, version_number, payload_path, source_hash,
    normalized_hash, source_url, captured_at, source_metadata_json,
    content_hash, prior_snapshot_id
)
SELECT
    id, application_id, version_number, payload_path, source_hash,
    normalized_hash, source_url, captured_at, source_metadata_json,
    content_hash, prior_snapshot_id
FROM job_snapshots;

DROP TABLE job_snapshots;
ALTER TABLE job_snapshots_new RENAME TO job_snapshots;

CREATE INDEX idx_snapshots_application ON job_snapshots(application_id);
CREATE TRIGGER no_update_job_snapshots BEFORE UPDATE ON job_snapshots
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;
CREATE TRIGGER no_delete_job_snapshots BEFORE DELETE ON job_snapshots
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

INSERT INTO schema_meta(key, value) VALUES('schema_version', '2')
ON CONFLICT(key) DO UPDATE SET value=excluded.value;
