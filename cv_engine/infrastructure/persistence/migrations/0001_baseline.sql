-- v2 schema baseline. This is the fresh-Workspace schema: no v2 database has ever
-- existed outside this one migration, so there is nothing to upgrade in place. The
-- former 0001-0010 chain that built this schema incrementally is preserved in git
-- history for anyone who needs the intermediate shapes; this file is what applying
-- that whole chain to an empty database produces, minus the v1-migration-only pieces
-- listed in the phase-2 squash commit message. Per-constraint and per-trigger
-- comments below carry forward the original reasoning where it is not self-evident
-- from the SQL alone.

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- The preparation and recruitment axes are independent in v2: `current_status` is
-- the recruitment-pipeline projection only, never a preparation/render state.
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
    updated_at TEXT NOT NULL,
    terminal_outcome TEXT
        CHECK (terminal_outcome IS NULL OR terminal_outcome IN ('accepted', 'rejected', 'withdrawn'))
);

CREATE TRIGGER IF NOT EXISTS valid_recruitment_status_on_insert
BEFORE INSERT ON applications
WHEN NEW.current_status NOT IN (
    'saved', 'applied', 'recruiter_screen', 'interview', 'assignment',
    'final_stage', 'offer', 'accepted', 'rejected', 'withdrawn', 'closed'
)
BEGIN
    SELECT RAISE(ABORT, 'invalid recruitment status');
END;

CREATE TRIGGER IF NOT EXISTS valid_recruitment_status_on_update
BEFORE UPDATE OF current_status ON applications
WHEN NEW.current_status NOT IN (
    'saved', 'applied', 'recruiter_screen', 'interview', 'assignment',
    'final_stage', 'offer', 'accepted', 'rejected', 'withdrawn', 'closed'
)
BEGIN
    SELECT RAISE(ABORT, 'invalid recruitment status');
END;

CREATE TABLE IF NOT EXISTS job_snapshots (
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
    prior_snapshot_id TEXT REFERENCES job_snapshots(id),
    UNIQUE(application_id, version_number),
    UNIQUE(application_id, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_application ON job_snapshots(application_id);
CREATE TRIGGER IF NOT EXISTS no_update_job_snapshots BEFORE UPDATE ON job_snapshots
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;
CREATE TRIGGER IF NOT EXISTS no_delete_job_snapshots BEFORE DELETE ON job_snapshots
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

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

CREATE INDEX IF NOT EXISTS idx_analyses_application ON job_analyses(application_id);
CREATE TRIGGER IF NOT EXISTS no_update_job_analyses BEFORE UPDATE ON job_analyses BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_job_analyses BEFORE DELETE ON job_analyses BEGIN SELECT RAISE(ABORT, 'immutable record'); END;

CREATE TABLE IF NOT EXISTS selection_plans (
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

CREATE TRIGGER IF NOT EXISTS no_update_selection_plans BEFORE UPDATE ON selection_plans
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

CREATE TRIGGER IF NOT EXISTS no_delete_selection_plans BEFORE DELETE ON selection_plans
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

CREATE TABLE IF NOT EXISTS working_drafts (
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

-- Product invariant 3: one active working draft per application, enforced by a
-- partial unique index rather than by convention.
CREATE UNIQUE INDEX IF NOT EXISTS one_active_working_draft_per_application
ON working_drafts(application_id) WHERE active = 1;

-- `status_history` was here. It recorded the v1 status timeline and was read
-- exactly twice, both by one-time backfills in the old 0006 that built
-- `recruitment_events` from it. recruitment_events replaced it: it carries the
-- same transitions plus actor, client, installation, corrections, and terminal
-- outcome. Nothing has written or read status_history since. It survived into
-- the squashed baseline only because the squash preserved the final schema
-- faithfully, v1 leftovers included, and is dropped here with v1 itself.

CREATE TABLE IF NOT EXISTS application_events (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS no_update_application_events BEFORE UPDATE ON application_events BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_application_events BEFORE DELETE ON application_events BEGIN SELECT RAISE(ABORT, 'immutable record'); END;

-- The single source of truth for recruitment-pipeline transitions. `preparing` and
-- `ready` are not v2 recruitment statuses; they never appear in the CHECK lists
-- below, and the recruitment status enum itself is unaffected by that history.
CREATE TABLE IF NOT EXISTS recruitment_events (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    event_type TEXT NOT NULL CHECK (
        event_type IN ('status_transition', 'status_correction', 'next_action')
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
    actor_type TEXT NOT NULL CHECK (actor_type IN ('user', 'system')),
    client TEXT NOT NULL CHECK (client IN ('web', 'cli', 'worker')),
    installation_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    CHECK (
        event_type != 'status_correction'
        OR (corrects_event_id IS NOT NULL AND length(trim(reason)) > 0)
    ),
    CHECK (event_type = 'status_correction' OR corrects_event_id IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_recruitment_events_application
ON recruitment_events(application_id, occurred_at, id);

CREATE TRIGGER IF NOT EXISTS no_update_recruitment_events
BEFORE UPDATE ON recruitment_events
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

CREATE TRIGGER IF NOT EXISTS no_delete_recruitment_events
BEFORE DELETE ON recruitment_events
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    application_id TEXT REFERENCES applications(id),
    artifact_type TEXT NOT NULL,
    logical_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(application_id, artifact_type, logical_name)
);

CREATE INDEX IF NOT EXISTS idx_artifacts_application ON artifacts(application_id);

-- Product specification section 6 invariant 4 lists Artifact among the immutable
-- records; nothing in the engine updates or deletes these rows.
CREATE TRIGGER IF NOT EXISTS no_update_artifacts BEFORE UPDATE ON artifacts BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_artifacts BEFORE DELETE ON artifacts BEGIN SELECT RAISE(ABORT, 'immutable record'); END;

CREATE TABLE IF NOT EXISTS approved_revisions (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    job_snapshot_id TEXT NOT NULL REFERENCES job_snapshots(id),
    job_analysis_id TEXT NOT NULL REFERENCES job_analyses(id),
    selection_plan_id TEXT NOT NULL REFERENCES selection_plans(id),
    working_draft_id TEXT NOT NULL REFERENCES working_drafts(id),
    draft_edit_version INTEGER NOT NULL CHECK (draft_edit_version > 0),
    draft_content_hash TEXT NOT NULL,
    resume_json_path TEXT NOT NULL UNIQUE,
    resume_json_hash TEXT NOT NULL,
    resume_markdown_path TEXT NOT NULL UNIQUE,
    resume_markdown_hash TEXT NOT NULL,
    candidate_context_version TEXT NOT NULL,
    candidate_context_hash TEXT NOT NULL,
    facts_version TEXT NOT NULL,
    knowledge_context_hash TEXT NOT NULL,
    profile_version TEXT NOT NULL,
    selection_policy_version TEXT NOT NULL,
    track_emphasis_dependencies_json TEXT NOT NULL,
    validation_run_id TEXT NOT NULL UNIQUE REFERENCES validation_runs(id),
    validator_versions_json TEXT NOT NULL,
    decision_provenance_json TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    UNIQUE(application_id, version_number)
);

CREATE TRIGGER IF NOT EXISTS no_update_approved_revisions BEFORE UPDATE ON approved_revisions
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

CREATE TRIGGER IF NOT EXISTS no_delete_approved_revisions BEFORE DELETE ON approved_revisions
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

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
    revision_id TEXT REFERENCES approved_revisions(id),
    UNIQUE(artifact_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_versions_artifact ON artifact_versions(artifact_id);
CREATE INDEX IF NOT EXISTS idx_versions_revision ON artifact_versions(revision_id);
CREATE TRIGGER IF NOT EXISTS no_update_artifact_versions BEFORE UPDATE ON artifact_versions BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_artifact_versions BEFORE DELETE ON artifact_versions BEGIN SELECT RAISE(ABORT, 'immutable record'); END;

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

CREATE TRIGGER IF NOT EXISTS no_update_decision_records BEFORE UPDATE ON decision_records BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_decision_records BEFORE DELETE ON decision_records BEGIN SELECT RAISE(ABORT, 'immutable record'); END;

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

CREATE TRIGGER IF NOT EXISTS no_update_generation_runs BEFORE UPDATE ON generation_runs BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_generation_runs BEFORE DELETE ON generation_runs BEGIN SELECT RAISE(ABORT, 'immutable record'); END;

CREATE TABLE IF NOT EXISTS validation_runs (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    artifact_version_id TEXT REFERENCES artifact_versions(id),
    phase TEXT NOT NULL,
    report_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    working_draft_id TEXT REFERENCES working_drafts(id),
    edit_version INTEGER,
    content_hash TEXT,
    job_snapshot_id TEXT REFERENCES job_snapshots(id),
    job_analysis_id TEXT REFERENCES job_analyses(id),
    selection_plan_id TEXT REFERENCES selection_plans(id),
    knowledge_context_hash TEXT,
    validator_versions_json TEXT
);

CREATE TRIGGER IF NOT EXISTS no_update_validation_runs BEFORE UPDATE ON validation_runs BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_validation_runs BEFORE DELETE ON validation_runs BEGIN SELECT RAISE(ABORT, 'immutable record'); END;

-- Submissions either reference an ApprovedRevision or, when external, have none
-- at all.
--
-- `artifact_version_id` is UNIQUE but nullable, and the two work together. UNIQUE
-- stops one artifact being recorded as submitted twice, which this table cannot
-- undo: it is immutable, so a duplicate is permanent and the history then says a
-- CV was sent twice when it was sent once. Nullable because an external
-- submission may have no artifact — the candidate applied through a form. SQLite
-- allows repeated NULLs under UNIQUE, so both hold at once. It is deliberately
-- not NOT NULL: that was the M1 shape, before external submissions existed, and
-- restoring it would make `record_external_submission` unable to record one.
CREATE TABLE IF NOT EXISTS submissions (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    submission_type TEXT NOT NULL CHECK (submission_type IN ('internal', 'external')),
    approved_revision_id TEXT REFERENCES approved_revisions(id),
    artifact_version_id TEXT UNIQUE REFERENCES artifact_versions(id),
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

CREATE INDEX IF NOT EXISTS idx_submissions_application
ON submissions(application_id, submitted_at, id);

CREATE TRIGGER IF NOT EXISTS no_update_submissions
BEFORE UPDATE ON submissions
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

CREATE TRIGGER IF NOT EXISTS no_delete_submissions
BEFORE DELETE ON submissions
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

CREATE TABLE IF NOT EXISTS audit_records (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('user', 'system')),
    client TEXT NOT NULL CHECK (client IN ('web', 'cli', 'worker')),
    installation_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_audit_records_application
ON audit_records(application_id, occurred_at, id);

CREATE TRIGGER IF NOT EXISTS no_update_audit_records
BEFORE UPDATE ON audit_records
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

CREATE TRIGGER IF NOT EXISTS no_delete_audit_records
BEFORE DELETE ON audit_records
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

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

CREATE INDEX IF NOT EXISTS idx_fact_events_fact ON fact_events(fact_id);
CREATE TRIGGER IF NOT EXISTS no_update_fact_events BEFORE UPDATE ON fact_events BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_fact_events BEFORE DELETE ON fact_events BEGIN SELECT RAISE(ABORT, 'immutable record'); END;

CREATE TABLE IF NOT EXISTS operations (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    installation_id TEXT NOT NULL,
    operation_type TEXT NOT NULL CHECK (operation_type IN (
        'analyze_job', 'propose_selection_plan', 'create_draft',
        'regenerate_section', 'regenerate_claim', 'render_revision'
    )),
    payload_json TEXT NOT NULL,
    payload_hash TEXT NOT NULL CHECK (length(payload_hash) = 64),
    idempotency_key TEXT NOT NULL CHECK (length(trim(idempotency_key)) > 0),
    sources_json TEXT NOT NULL,
    resources_json TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    status TEXT NOT NULL CHECK (
        status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'interrupted')
    ),
    phase TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    lease_owner TEXT,
    lease_expires_at TEXT,
    heartbeat_at TEXT,
    cancellation_requested_at TEXT,
    failure_code TEXT CHECK (failure_code IS NULL OR failure_code IN (
        'SOURCE_CHANGED', 'PROVIDER_TIMEOUT', 'PROVIDER_RATE_LIMITED',
        'PROVIDER_UNAVAILABLE', 'PROVIDER_REFUSED', 'INVALID_OUTPUT',
        'SCHEMA_VIOLATION', 'RENDER_FAILED', 'BROWSER_START_FAILED',
        'VALIDATION_EXECUTION_FAILED', 'CANCELLED_BEFORE_ACTIVATION'
    )),
    safe_failure_detail TEXT,
    technical_log_reference TEXT,
    retry_of_operation_id TEXT REFERENCES operations(id),
    attempts_completed INTEGER NOT NULL DEFAULT 0 CHECK (attempts_completed >= 0),
    next_attempt_at TEXT,
    UNIQUE(installation_id, operation_type, idempotency_key),
    CHECK (
        (lease_owner IS NULL AND lease_expires_at IS NULL AND heartbeat_at IS NULL)
        OR
        (lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL AND heartbeat_at IS NOT NULL)
    ),
    CHECK (status != 'running' OR lease_owner IS NOT NULL),
    CHECK (status NOT IN ('succeeded', 'failed', 'cancelled', 'interrupted')
           OR lease_owner IS NULL),
    CHECK ((status IN ('succeeded', 'failed', 'cancelled', 'interrupted')) =
           (finished_at IS NOT NULL)),
    CHECK (status != 'failed' OR failure_code IS NOT NULL),
    CHECK (failure_code IS NULL OR status IN ('failed', 'cancelled')),
    CHECK (safe_failure_detail IS NULL OR status IN ('failed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_operations_application_status
ON operations(application_id, status, created_at, id);

CREATE INDEX IF NOT EXISTS idx_operations_claimable
ON operations(status, next_attempt_at, created_at, id);

CREATE TABLE IF NOT EXISTS operation_resource_leases (
    resource_kind TEXT NOT NULL CHECK (
        resource_kind IN ('application_mutation', 'render_browser', 'ai')
    ),
    resource_key TEXT NOT NULL,
    slot INTEGER NOT NULL CHECK (slot >= 0),
    operation_id TEXT NOT NULL REFERENCES operations(id),
    lease_owner TEXT NOT NULL,
    lease_expires_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL,
    PRIMARY KEY(resource_kind, resource_key, slot),
    UNIQUE(operation_id, resource_kind, resource_key)
);

CREATE INDEX IF NOT EXISTS idx_operation_resource_leases_operation
ON operation_resource_leases(operation_id);

CREATE TABLE IF NOT EXISTS operation_outputs (
    id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL REFERENCES operations(id),
    output_type TEXT NOT NULL,
    output_id TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 0 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL,
    activated_at TEXT,
    UNIQUE(operation_id, output_type, output_id),
    CHECK ((active = 1) = (activated_at IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_operation_outputs_operation
ON operation_outputs(operation_id, created_at, id);

CREATE TRIGGER IF NOT EXISTS prevent_update_terminal_operations
BEFORE UPDATE ON operations
WHEN OLD.status IN ('succeeded', 'failed', 'cancelled', 'interrupted')
BEGIN
    SELECT RAISE(ABORT, 'immutable terminal operation');
END;

CREATE TRIGGER IF NOT EXISTS prevent_delete_operations
BEFORE DELETE ON operations
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

CREATE TRIGGER IF NOT EXISTS valid_operation_output_activation
BEFORE UPDATE ON operation_outputs
WHEN NOT (
    OLD.active = 0 AND NEW.active = 1 AND NEW.activated_at IS NOT NULL
    AND OLD.id = NEW.id
    AND OLD.operation_id = NEW.operation_id
    AND OLD.output_type = NEW.output_type
    AND OLD.output_id = NEW.output_id
    AND OLD.created_at = NEW.created_at
    AND (SELECT status FROM operations WHERE id = OLD.operation_id) = 'running'
    AND (SELECT cancellation_requested_at FROM operations WHERE id = OLD.operation_id) IS NULL
)
BEGIN
    SELECT RAISE(ABORT, 'invalid operation output update');
END;

CREATE TRIGGER IF NOT EXISTS prevent_delete_operation_outputs
BEFORE DELETE ON operation_outputs
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

CREATE TABLE IF NOT EXISTS idempotency_receipts (
    id TEXT PRIMARY KEY,
    installation_id TEXT NOT NULL,
    command_type TEXT NOT NULL,
    idempotency_key TEXT NOT NULL CHECK (length(trim(idempotency_key)) > 0),
    payload_json TEXT NOT NULL,
    payload_hash TEXT NOT NULL CHECK (length(payload_hash) = 64),
    reserved_entity_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'completed')),
    result_json TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    UNIQUE(installation_id, command_type, idempotency_key),
    CHECK ((status = 'completed') = (result_json IS NOT NULL)),
    CHECK ((status = 'completed') = (completed_at IS NOT NULL))
);

CREATE TRIGGER IF NOT EXISTS valid_idempotency_receipt_completion
BEFORE UPDATE ON idempotency_receipts
WHEN NOT (
    OLD.status = 'pending' AND NEW.status = 'completed'
    AND OLD.id = NEW.id
    AND OLD.installation_id = NEW.installation_id
    AND OLD.command_type = NEW.command_type
    AND OLD.idempotency_key = NEW.idempotency_key
    AND OLD.payload_json = NEW.payload_json
    AND OLD.payload_hash = NEW.payload_hash
    AND OLD.reserved_entity_id = NEW.reserved_entity_id
    AND OLD.created_at = NEW.created_at
    AND NEW.result_json IS NOT NULL
    AND NEW.completed_at IS NOT NULL
)
BEGIN
    SELECT RAISE(ABORT, 'invalid idempotency receipt update');
END;

CREATE TRIGGER IF NOT EXISTS prevent_delete_idempotency_receipts
BEFORE DELETE ON idempotency_receipts
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

CREATE TABLE IF NOT EXISTS knowledge_mutation_journal (
    id TEXT PRIMARY KEY,
    mutation_type TEXT NOT NULL CHECK (length(trim(mutation_type)) > 0),
    state TEXT NOT NULL CHECK (state IN ('PREPARED', 'COMMITTED', 'QUARANTINED')),
    source_reference TEXT NOT NULL CHECK (length(trim(source_reference)) > 0),
    staged_reference TEXT NOT NULL UNIQUE CHECK (length(trim(staged_reference)) > 0),
    old_sha256 TEXT NOT NULL CHECK (length(old_sha256) = 64),
    new_sha256 TEXT NOT NULL CHECK (length(new_sha256) = 64),
    db_mutation_type TEXT NOT NULL CHECK (length(trim(db_mutation_type)) > 0),
    db_mutation_id TEXT NOT NULL CHECK (length(trim(db_mutation_id)) > 0),
    db_mutation_json TEXT NOT NULL,
    recovery_strategy TEXT NOT NULL CHECK (length(trim(recovery_strategy)) > 0),
    prepared_at TEXT NOT NULL,
    committed_at TEXT,
    quarantined_at TEXT,
    quarantine_reason TEXT,
    UNIQUE(db_mutation_type, db_mutation_id),
    CHECK (
        (state = 'PREPARED' AND committed_at IS NULL
         AND quarantined_at IS NULL AND quarantine_reason IS NULL)
        OR
        (state = 'COMMITTED' AND committed_at IS NOT NULL
         AND quarantined_at IS NULL AND quarantine_reason IS NULL)
        OR
        (state = 'QUARANTINED' AND committed_at IS NULL
         AND quarantined_at IS NOT NULL AND length(trim(quarantine_reason)) > 0)
    )
);

CREATE INDEX IF NOT EXISTS idx_knowledge_mutation_journal_state
ON knowledge_mutation_journal(state, prepared_at, id);

CREATE TRIGGER IF NOT EXISTS valid_knowledge_mutation_transition
BEFORE UPDATE ON knowledge_mutation_journal
WHEN NOT (
    OLD.state = 'PREPARED'
    AND NEW.state IN ('COMMITTED', 'QUARANTINED')
    AND OLD.id = NEW.id
    AND OLD.mutation_type = NEW.mutation_type
    AND OLD.source_reference = NEW.source_reference
    AND OLD.staged_reference = NEW.staged_reference
    AND OLD.old_sha256 = NEW.old_sha256
    AND OLD.new_sha256 = NEW.new_sha256
    AND OLD.db_mutation_type = NEW.db_mutation_type
    AND OLD.db_mutation_id = NEW.db_mutation_id
    AND OLD.db_mutation_json = NEW.db_mutation_json
    AND OLD.recovery_strategy = NEW.recovery_strategy
    AND OLD.prepared_at = NEW.prepared_at
)
BEGIN
    SELECT RAISE(ABORT, 'invalid knowledge mutation transition');
END;

CREATE TRIGGER IF NOT EXISTS prevent_delete_knowledge_mutation_journal
BEFORE DELETE ON knowledge_mutation_journal
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

INSERT INTO schema_meta(key, value) VALUES('schema_version', '2')
ON CONFLICT(key) DO UPDATE SET value=excluded.value;
