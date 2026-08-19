-- The preparation and recruitment axes are independent in v2. `preparing`
-- and `ready` are retained only as raw legacy provenance in migration events.
ALTER TABLE applications
ADD COLUMN terminal_outcome TEXT
CHECK (terminal_outcome IS NULL OR terminal_outcome IN ('accepted', 'rejected', 'withdrawn'));

UPDATE applications
SET terminal_outcome = CASE
    WHEN current_status IN ('accepted', 'rejected', 'withdrawn') THEN current_status
    WHEN current_status = 'closed' THEN (
        SELECT history.to_status
        FROM status_history AS history
        WHERE history.application_id = applications.id
          AND history.to_status IN ('accepted', 'rejected', 'withdrawn')
        ORDER BY history.id DESC
        LIMIT 1
    )
    ELSE NULL
END;

UPDATE applications
SET current_status = 'saved'
WHERE current_status IN ('preparing', 'ready');

CREATE TRIGGER valid_recruitment_status_on_insert
BEFORE INSERT ON applications
WHEN NEW.current_status NOT IN (
    'saved', 'applied', 'recruiter_screen', 'interview', 'assignment',
    'final_stage', 'offer', 'accepted', 'rejected', 'withdrawn', 'closed'
)
BEGIN
    SELECT RAISE(ABORT, 'invalid recruitment status');
END;

CREATE TRIGGER valid_recruitment_status_on_update
BEFORE UPDATE OF current_status ON applications
WHEN NEW.current_status NOT IN (
    'saved', 'applied', 'recruiter_screen', 'interview', 'assignment',
    'final_stage', 'offer', 'accepted', 'rejected', 'withdrawn', 'closed'
)
BEGIN
    SELECT RAISE(ABORT, 'invalid recruitment status');
END;

CREATE TABLE recruitment_events (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    event_type TEXT NOT NULL CHECK (
        event_type IN ('status_transition', 'status_correction', 'next_action', 'migration')
    ),
    from_status TEXT CHECK (
        from_status IS NULL OR from_status IN (
            'saved', 'applied', 'recruiter_screen', 'interview', 'assignment',
            'final_stage', 'offer', 'accepted', 'rejected', 'withdrawn', 'closed'
        )
    ),
    to_status TEXT CHECK (
        to_status IS NULL OR to_status IN (
            'saved', 'applied', 'recruiter_screen', 'interview', 'assignment',
            'final_stage', 'offer', 'accepted', 'rejected', 'withdrawn', 'closed'
        )
    ),
    corrects_event_id TEXT REFERENCES recruitment_events(id),
    reason TEXT NOT NULL DEFAULT '',
    actor_type TEXT NOT NULL CHECK (actor_type IN ('user', 'system', 'migration')),
    client TEXT NOT NULL CHECK (client IN ('web', 'cli', 'worker')),
    installation_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    legacy_event_id TEXT,
    legacy_from_status TEXT,
    legacy_to_status TEXT,
    created_at TEXT NOT NULL,
    CHECK (
        event_type != 'status_correction'
        OR (corrects_event_id IS NOT NULL AND length(trim(reason)) > 0)
    ),
    CHECK (event_type = 'status_correction' OR corrects_event_id IS NULL)
);

CREATE INDEX idx_recruitment_events_application
ON recruitment_events(application_id, occurred_at, id);

-- Preserve every old status row. Invalid v2-axis strings remain only in the
-- dedicated legacy columns; mapped columns always obey the v2 enum.
INSERT INTO recruitment_events(
    id, application_id, event_type, from_status, to_status, reason,
    actor_type, client, installation_id, occurred_at, payload_json,
    legacy_event_id, legacy_from_status, legacy_to_status, created_at
)
SELECT
    CAST(id AS TEXT),
    application_id,
    CASE
        WHEN from_status IN ('preparing', 'ready') OR to_status IN ('preparing', 'ready')
        THEN 'migration'
        ELSE 'status_transition'
    END,
    CASE from_status
        WHEN 'preparing' THEN 'saved'
        WHEN 'ready' THEN 'saved'
        ELSE from_status
    END,
    CASE to_status
        WHEN 'preparing' THEN 'saved'
        WHEN 'ready' THEN 'saved'
        ELSE to_status
    END,
    reason,
    'migration',
    'worker',
    'schema-migration',
    changed_at,
    '{}',
    CASE
        WHEN from_status IN ('preparing', 'ready') OR to_status IN ('preparing', 'ready')
        THEN CAST(id AS TEXT)
        ELSE NULL
    END,
    CASE
        WHEN from_status IN ('preparing', 'ready') OR to_status IN ('preparing', 'ready')
        THEN from_status
        ELSE NULL
    END,
    CASE
        WHEN from_status IN ('preparing', 'ready') OR to_status IN ('preparing', 'ready')
        THEN to_status
        ELSE NULL
    END,
    changed_at
FROM status_history
ORDER BY id;

CREATE TRIGGER no_update_recruitment_events
BEFORE UPDATE ON recruitment_events
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

CREATE TRIGGER no_delete_recruitment_events
BEFORE DELETE ON recruitment_events
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

-- Rebuild submissions because historical rows may not have a recorded
-- ApprovedRevision identity. Such rows become external submissions while
-- retaining the exact artifact reference that was actually recorded.
ALTER TABLE submissions RENAME TO legacy_submissions_0006;

CREATE TABLE submissions (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    submission_type TEXT NOT NULL CHECK (submission_type IN ('internal', 'external')),
    approved_revision_id TEXT REFERENCES approved_revisions(id),
    artifact_version_id TEXT REFERENCES artifact_versions(id),
    submitted_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    CHECK (
        (submission_type = 'internal'
         AND approved_revision_id IS NOT NULL
         AND artifact_version_id IS NOT NULL)
        OR
        (submission_type = 'external' AND approved_revision_id IS NULL)
    )
);

INSERT INTO submissions(
    id, application_id, submission_type, approved_revision_id,
    artifact_version_id, submitted_at, metadata_json
)
SELECT
    legacy.id,
    legacy.application_id,
    CASE WHEN versions.revision_id IS NULL THEN 'external' ELSE 'internal' END,
    versions.revision_id,
    legacy.artifact_version_id,
    legacy.submitted_at,
    legacy.metadata_json
FROM legacy_submissions_0006 AS legacy
JOIN artifact_versions AS versions ON versions.id = legacy.artifact_version_id;

DROP TABLE legacy_submissions_0006;

CREATE INDEX idx_submissions_application
ON submissions(application_id, submitted_at, id);

CREATE TRIGGER no_update_submissions
BEFORE UPDATE ON submissions
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

CREATE TRIGGER no_delete_submissions
BEFORE DELETE ON submissions
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

CREATE TABLE audit_records (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('user', 'system', 'migration')),
    client TEXT NOT NULL CHECK (client IN ('web', 'cli', 'worker')),
    installation_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_audit_records_application
ON audit_records(application_id, occurred_at, id);

CREATE TRIGGER no_update_audit_records
BEFORE UPDATE ON audit_records
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

CREATE TRIGGER no_delete_audit_records
BEFORE DELETE ON audit_records
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;
