# v1 Migration Source Restore

These instructions restore the frozen pre-migration v1 source without overwriting the
live repository.

Almost all of the v1 record — `outputs/`, `jobs/`, `base/`, `cv-html/` — is tracked in
Git, so Git is the archive, the manifest, and the restore mechanism. It is
content-addressed, it already hashes every blob, and it restores into a new directory
without touching the source.

1. Read the frozen commit from `data/migration/source.json`.
2. Restore the tracked payloads into a new directory outside the live checkout:

   ```bash
   git worktree add <new-directory> <frozen-commit>
   ```

   The migration tool uses `git archive` instead, because a worktree registers itself
   under `.git/worktrees` and the source must stay untouched. Either produces the same
   bytes.
3. Restore the one payload Git does not track — the SQLite database — from
   `data/migration/source-database.sqlite3`. It was taken with the SQLite backup API
   rather than `cp`, so it is transactionally consistent.
4. Verify the restore:

   ```bash
   python -m cv_engine.cli migrate verify-source
   ```

   This re-derives the frozen commit's tree from Git and re-hashes the database backup.
   It does not trust the recorded values.
5. Inspect the restored `jobs/status.csv`, `base/cv_base.md`, `outputs/`, and
   `other_clients/` before using the copy.
6. To recover from a failed migration, keep the live repository untouched, retain the
   failed database for diagnosis, and use the verified restored copy as the recovery
   source. Never merge a partial database into the restored copy.

The migration tool verifies the restore in a temporary directory before it allows live
apply. Live restoration is intentionally not automated because replacing an existing
repository is destructive and must be an explicit human recovery action.

## Historical snapshots

Timestamped directories under `data/snapshots/` are tar archives from the retired
snapshot format, referenced by `docs/v1/verification.md` and
`docs/v1/retrospective-migration-verification.json` as evidence of runs that already
happened. The tooling that reads them no longer ships. They are historical evidence, not
a restore path.
