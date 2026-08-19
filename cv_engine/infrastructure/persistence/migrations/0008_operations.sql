CREATE TABLE operations (
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

CREATE INDEX idx_operations_application_status
ON operations(application_id, status, created_at, id);

CREATE INDEX idx_operations_claimable
ON operations(status, next_attempt_at, created_at, id);

CREATE TABLE operation_resource_leases (
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

CREATE INDEX idx_operation_resource_leases_operation
ON operation_resource_leases(operation_id);

CREATE TABLE operation_outputs (
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

CREATE INDEX idx_operation_outputs_operation
ON operation_outputs(operation_id, created_at, id);

CREATE TRIGGER prevent_update_terminal_operations
BEFORE UPDATE ON operations
WHEN OLD.status IN ('succeeded', 'failed', 'cancelled', 'interrupted')
BEGIN
    SELECT RAISE(ABORT, 'immutable terminal operation');
END;

CREATE TRIGGER prevent_delete_operations
BEFORE DELETE ON operations
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

CREATE TRIGGER valid_operation_output_activation
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

CREATE TRIGGER prevent_delete_operation_outputs
BEFORE DELETE ON operation_outputs
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;
