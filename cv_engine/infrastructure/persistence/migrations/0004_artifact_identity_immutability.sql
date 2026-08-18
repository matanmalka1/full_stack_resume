-- The artifacts table carries artifact identity: one row per application,
-- artifact type, and logical name. Product specification section 6 invariant 4
-- lists Artifact among the immutable records, and nothing in the engine updates
-- or deletes these rows, but the baseline schema never guarded them: the M1
-- immutability list was written by hand and this table was simply not on it.
--
-- The omission surfaced when the test inverted its default to "immutable unless
-- explicitly exempt", which is the only form of that check able to detect a
-- table nobody remembered.
CREATE TRIGGER IF NOT EXISTS no_update_artifacts BEFORE UPDATE ON artifacts BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_artifacts BEFORE DELETE ON artifacts BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
