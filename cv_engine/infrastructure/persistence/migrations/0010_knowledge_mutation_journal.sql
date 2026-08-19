CREATE TABLE knowledge_mutation_journal (
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

CREATE INDEX idx_knowledge_mutation_journal_state
ON knowledge_mutation_journal(state, prepared_at, id);

CREATE TRIGGER valid_knowledge_mutation_transition
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

CREATE TRIGGER prevent_delete_knowledge_mutation_journal
BEFORE DELETE ON knowledge_mutation_journal
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;
