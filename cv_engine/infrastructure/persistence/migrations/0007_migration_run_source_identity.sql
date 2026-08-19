-- A migration run is now identified by the frozen Git commit it read from, not
-- by a tar snapshot id and manifest hash. Git already stores and hashes every
-- tracked payload, so the snapshot archive it named no longer exists.
-- `dry_run_report_hash` is dropped outright: hashing a report proves only that
-- the paperwork is unchanged, never that the data matches.
ALTER TABLE migration_runs RENAME TO legacy_migration_runs_0007;

CREATE TABLE migration_runs (
    id TEXT PRIMARY KEY,
    source_commit TEXT NOT NULL,
    source_tree_hash TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    artifact_count INTEGER NOT NULL,
    report_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Any pre-existing run predates the Git-identified source, so its commit and
-- tree cannot be derived. Never invent an identity that was never recorded:
-- the legacy snapshot id is preserved verbatim and the tree hash stays unknown.
INSERT INTO migration_runs(
    id, source_commit, source_tree_hash, row_count, artifact_count, report_json, created_at
)
SELECT
    id,
    'legacy-snapshot:' || snapshot_id,
    'unknown',
    row_count,
    artifact_count,
    report_json,
    created_at
FROM legacy_migration_runs_0007;

-- Count parity, enforced rather than reported. A rebuild that silently drops
-- rows leaves no trace once the source table is dropped, so the check has to
-- run before the drop and has to abort rather than record a problem. The failing
-- CHECK is the abort: `RAISE` is only available inside a trigger body.
CREATE TABLE migration_run_parity_0007 (counts_match INTEGER NOT NULL CHECK (counts_match = 1));

INSERT INTO migration_run_parity_0007(counts_match)
SELECT (SELECT COUNT(*) FROM legacy_migration_runs_0007) = (SELECT COUNT(*) FROM migration_runs);

DROP TABLE migration_run_parity_0007;
DROP TABLE legacy_migration_runs_0007;

-- Rebuilding the table dropped the triggers that were attached to it. A
-- migration run is a record of what was done to the historical data; it is
-- immutable for the same reason the data is.
CREATE TRIGGER no_update_migration_runs
BEFORE UPDATE ON migration_runs
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

CREATE TRIGGER no_delete_migration_runs
BEFORE DELETE ON migration_runs
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;
