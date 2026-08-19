# v1 Migration Snapshot Restore

These instructions restore a verified pre-migration repository snapshot without
overwriting the live repository.

1. Locate the chosen timestamped directory under `data/snapshots/` and verify that it
   contains `repository.tar.gz`, `manifest.json`, and `verification.json`.
2. Run `python -m cv_engine.cli migrate verify-snapshot --snapshot <directory>`.
3. Create a new empty directory outside the live repository.
4. Extract `repository.tar.gz` into that empty directory. Do not extract over the live
   checkout.
5. Compare every extracted file and symlink with `manifest.json` using the same
   `verify-snapshot` command or the recorded `verification.json` procedure.
6. Inspect the restored `jobs/status.csv`, `base/cv_base.md`, `outputs/`, and
   `other_clients/` before using the copy.
7. To recover from a failed migration, keep the live repository untouched, retain the
   failed database for diagnosis, and use the verified extracted copy as the recovery
   source. Never merge a partial database into the restored copy.

The migration tool verifies restoration in a temporary directory before it allows live
apply. Live restoration is intentionally not automated because replacing an existing
repository is destructive and must be an explicit human recovery action.
