CREATE TABLE idempotency_receipts (
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

CREATE TRIGGER valid_idempotency_receipt_completion
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

CREATE TRIGGER prevent_delete_idempotency_receipts
BEFORE DELETE ON idempotency_receipts
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;
