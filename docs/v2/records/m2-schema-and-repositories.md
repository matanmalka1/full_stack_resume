# M2 Boundary 1 — Schema and Repositories (design and execution brief)

Status: **Implemented and independently verified 2026-08-18.** Designed at `d835ca9`; implementation closed at `4796744`. Evidence in §13.

Scope: `docs/v2/spec/implementation-plan.md` §4.1 (schema, numbered migrations, connection policy,
repositories by transactional ownership, UnitOfWork, filesystem payload stores, ID/timestamp/
hash/serialization primitives), plus the M2 §4.1 carry-forward the architecture audit parked
here: A26, A27, A29, A23's containment duplication, and the two Stage 8 items that live inside
`infrastructure/db.py` — A2 and A7.

Authority: `docs/v2/spec/product-spec.md` §6/§16, `docs/v2/spec/state-and-use-cases.md` §2,
`docs/v2/spec/architecture.md` §3.3/§4/§6/§7, `docs/v2/spec/implementation-plan.md` §4.1/§4.7,
`docs/v2/spec/test-and-acceptance-plan.md` §2.3, `docs/v2/spec/migration-plan.md` §3/§10,
`docs/v2/records/architecture-audit.md` §3/§4/§6, `docs/v2/process/execution-protocol.md` for process.

This document changes no behaviour by itself. It is the design the executing agents implement
and the bar the verifying agent checks against.

## 0. Why this boundary exists

M1 deliberately left persistence as v1 left it. `cv_engine/infrastructure/db.py` (940 lines)
holds schema DDL, connection policy, a UnitOfWork, every repository SQL accessor, and part of
the recruitment lifecycle. The schema is created as a side effect of constructing
`Repository(...)` — `CREATE TABLE IF NOT EXISTS` on every open — which architecture §6.1
forbids ("does not depend on application startup side effects to perform an unguarded
migration") and which gives no way to evolve the schema for M2's records.

Everything in §4.2–§4.6 writes through this layer. It is therefore split once, first, with the
enforcement in place before the moves.

## 1. In scope / out of scope

In scope:

1. Numbered SQL migrations, a migration runner, `schema_migrations` bookkeeping, verified
   adoption of an existing database, and an explicit version gate on open.
2. One connection policy module: foreign keys, WAL, busy timeout, `BEGIN IMMEDIATE` writes,
   short transactions, `SqliteUnitOfWork`.
3. Five SQLite repositories split by transactional ownership plus a delegation-only composite.
4. The §6.2 immutable payload store and the §7.1 commit protocol.
5. UUIDv4 IDs, UTC timestamps, and SHA-256 hashes.
6. One path-containment policy; A26, A27, A29 closed.
7. A2 (narrowed, see §8) and A7.

Out of scope, with declared homes:

| Item | Home |
| --- | --- |
| `working_drafts`, `selection_plans`, `approved_revisions`, ValidationRun/ApprovedRevision records, Stage 7b (`"headline_safety"` rename, `report_schema_version`) | §4.2 domain records |
| `PreparationState` / `WorkingDraftState` / action policy; relocation of the `_set_ready` / `_record_submission` / `record_decision` rules (A2 residue) | §4.3 state and permissions |
| `operations`, leases, idempotency, heartbeat, worker | §4.4 operations |
| Knowledge mutation journal, quarantine | §4.5 knowledge consistency |
| Backup/manifest/restore; migration gate redesign, including A24's pytest subprocess | §4.6 backup/migration scaffolding |
| A3 (Profile-backed default emphasis), A4 (render/Ready policy to the domain), A5 (typed decision record), A6 (CLI confirm/promote policy) | Stage 8 items in §4.2/§4.3 |
| Per-service repository repointing and the rest of A16's port narrowing | §4.2, when each service gains its own v2 records |

## 2. Decisions

**D1 — `--db` / `CV_DATABASE` is contained (A26).** The setting stays, and its resolved path
must lie inside `state_root` after symlink resolution. Anything else is a fail-closed error.
Compatibility tests cover an accepted in-root relative form, an accepted in-root absolute
form, an out-of-root refusal, and a symlinked-escape refusal. Nothing in the tests, the
README, or CLI help documents the escaping behaviour, so no consumer regresses.

**D2 — no empty v2 entity tables now.** This boundary ships the mechanism plus
`0001_baseline.sql`. Later entity tables arrive as `0002+` with the records that use them.
Speculative empty tables would drift from the records before anything wrote to them.

**D3 — create is not migrate.** An absent or empty database is still created on first open
(today's behaviour; no data at risk). An existing database whose applied version is *lower*
than the code's refuses to open and names the explicit upgrade command. An unknown or newer
version refuses outright. No command silently migrates.

**D4 — adoption is fingerprint-verified.** An existing v1-shaped database is stamped as
`0001`-applied only when its normalised `sqlite_master` fingerprint equals the baseline
fingerprint. A mismatch is a hard refusal naming the difference.

**D5 — no stored-shape change.** `schema_meta.schema_version` keeps its current `"2"` value;
`schema_migrations` becomes the authority. A serialization version is introduced only with a
concrete payload schema and its reader/writer; path allocation alone does not create a versioned
payload contract. `structured_json`, `report_json`, and decision payloads are untouched, and no
historical row is rewritten.

**D6 — naming.** Concrete classes are `Sqlite*Repository` under
`infrastructure/persistence/`; the composed object handed to the composition root keeps the
name `Repository`. The port names in `application/ports.py` mean composed views and stay as
they are, so they do not collide with the §3.3 concrete repository names.

**D7 — table ownership is schema authority, not a write monopoly.** A use-case whose atomicity
spans two owners composes repositories inside one UnitOfWork (`repo.bind(uow)`); it does not
open a second transaction. Reads across owners are unrestricted.

**D8 — `migration_runs` gets no repository yet.** `infrastructure/migration.py` keeps its raw
SQL (audit §5.2: fix only its real defects, do not restructure). Its DDL lives in
`0001_baseline.sql`; ownership is assigned in §4.6.

## 3. Target schema map

Present today, moved verbatim into `0001_baseline.sql` (fourteen declared tables, six indexes,
and the eleven immutable tables' 22 triggers as explicit DDL rather than a Python loop):

`schema_meta`, `applications`, `job_snapshots`, `job_analyses`, `status_history`,
`application_events`, `artifacts`, `artifact_versions`, `decision_records`, `generation_runs`,
`validation_runs`, `migration_runs`, `submissions`, `fact_events`.

Added by this boundary: `schema_migrations(version TEXT PRIMARY KEY, name TEXT NOT NULL,
checksum TEXT NOT NULL, applied_at TEXT NOT NULL)`, bootstrapped by the runner itself rather
than by a numbered file.

**Two facts the fingerprint guard makes load-bearing** (`tests/fixtures/m1_sqlite_master.tsv`,
43 rows: 15 tables, 6 indexes, 22 triggers):

1. The fifteenth table is SQLite's own `sqlite_sequence`, which exists only because
   `status_history.id` is `INTEGER PRIMARY KEY AUTOINCREMENT`. `0001_baseline.sql` must not
   declare it and must not drop that `AUTOINCREMENT`, or the fingerprint changes.
2. `schema_migrations` is a **new** row in `sqlite_master`, so a database built by the runner
   has 44 rows against a 43-row fixture. The fingerprint comparison therefore excludes the
   bookkeeping table by name, explicitly and with a comment saying why. **Regenerating the
   fixture is forbidden** — it is the parity evidence that `0001_baseline.sql` reproduces the
   M1 schema, and a regenerated fixture proves only that the new code agrees with itself. If
   the fingerprint differs for any other reason, that is a stop condition.

Planned, so later migrations are additive:

| Migration | Adds | Boundary |
| --- | --- | --- |
| `0002` | `selection_plans`, `working_drafts` (+ `edit_version`, `content_hash`), `approved_revisions`, `validation_runs` v2 columns, `historical_draft_snapshots` | §4.2 |
| `0003` | recruitment events/corrections, current-status projection, terminal outcome, next action, v2 `submissions` shape, audit records | §4.2/§4.3 |
| `0004` | `operations`, `operation_leases`, `idempotency_keys`, `operation_outputs` | §4.4 |
| `0005` | `knowledge_mutation_journal`, quarantine state, knowledge audit | §4.5 |
| `0006` | `settings`, `installation_metadata`, `workspace_metadata` | §4.6 |

Numbering is advisory; the constraint is that `0001` is the baseline and every later file is
additive, checksummed, and applied in order.

## 4. Connection and migration mechanics

`persistence/connection.py` is the only module that issues `PRAGMA` or opens `sqlite3`:

- `PRAGMA foreign_keys = ON`, `PRAGMA journal_mode = WAL`, `PRAGMA busy_timeout = 5000`.
- Durability pragmas keep their current effective values; this boundary does not change
  durability silently.
- Writes use `BEGIN IMMEDIATE`; `SqliteUnitOfWork` keeps its current contract exactly — exiting
  without an explicit `commit()` rolls back even with no exception raised.

`persistence/schema.py` owns: bootstrap of `schema_migrations`; ordered application of pending
files, one transaction per file; checksum recording and refusal on a changed checksum; the
fingerprint helper; adoption (D4); the version gate (D3); and the current schema version
surface for `cv workspace status`.

## 5. Repository ownership

| Repository | Owns | Notes |
| --- | --- | --- |
| `SqliteApplicationRepository` | `applications`, `status_history`, `application_events` | identity, generic transitions, next action, events |
| `SqlitePreparationRepository` | `job_snapshots`, `job_analyses` | keeps `_require_owned_snapshot` as its guard, callable by other repositories inside one transaction |
| `SqliteArtifactRepository` | `artifacts`, `artifact_versions`, `decision_records`, `generation_runs`, `validation_runs` | plus `artifact_inventory()` and `integrity_check()` |
| `SqliteTrackingRepository` | `submissions` | `set_ready` / `record_submission` compose the application repository under one UnitOfWork (D7) |
| `SqliteAuditRepository` | `fact_events` | fact lifecycle trail |
| `Repository` (`repository.py`) | nothing | inherits the five owners; holds no SQL and registers no method names, so an owner's new method is reachable without being listed anywhere |

`DraftRepository` (§4.2) and `OperationRepository` (§4.4) are created with their tables, not
now. The READY/APPLIED refusals in the generic transition stay in the repository as
defence-in-depth against bypass; the immutability triggers remain the database-level backstop.

Port typing done here (the A16 slice this boundary owns): `register_artifact_version`,
`record_decision`, `record_validation`, and `latest_artifact_version` lose their
`(*args: Any, **kwargs: Any)` signatures so §4.2's payloads are contract-checked.

## 6. Payload store (§6.2 + §7.1)

`infrastructure/payloads.py`, new, with no dependency on SQLite:

```text
snapshots/{application_id}/{snapshot_id}.txt
revisions/{application_id}/{revision_id}/resume.json|resume.md
outputs/{application_id}/{revision_id}/{artifact_id}.html|.pdf|.png
provider/{application_id}/{operation_id}/{artifact_id}.json
manifests: immutable UUID-based names
temp: under temp_root
```

One commit method implements `write temp -> validate -> hash -> atomic rename -> register`,
returning `StoredPayload(path, workspace_relative, sha256, size)`. **Registration in SQLite
stays with the caller** — that is what keeps the store independent of the repositories and
what makes an unregistered file a safe orphan for reconciliation. Overwriting an existing
immutable payload is refused. Temp orphans are reported, not deleted.

The M1 `FilesystemArtifactStore` layout (`working/`, `{app}/v001/`) is untouched: existing
artifact rows keep resolving through workspace-relative paths, and no historical artifact is
moved, renamed, or re-rendered. §4.2's revisions supersede it.

## 7. Containment policy (A23, A26, A27, A29)

`infrastructure/paths.py` becomes the single implementation: `resolve_within(root, candidate)`
and `relative_within(root, path)`, both resolving symlinks before the containment test. The
four current implementations with three different symlink semantics
(`legacy_source.py`, `runtime/workspace.py`, `infrastructure/migration.py`, and the containment
inside `Workspace.relative()`) are repointed onto it.

- **A27**: the four default child roots (`data`, `artifacts`, `tmp`, `logs`) are resolved and
  containment-checked before any write, and a symlinked default child is refused. Today only
  marker-declared roots are checked.
- **A29**: the Workspace root is resolved from CLI and environment only, the marker is
  validated, and *then* Workspace config is read. Config is no longer read before the marker
  that authorises the directory.
- **A26**: per D1.

## 8. A2 and A7 in this boundary

**A2, narrowed.** Done here: one owner for the READY-demotion rule; the demotion becomes
atomic with the write that triggers it; `Repository.save_analysis` stops re-reading status
after its own transaction has closed. Both existing trigger reasons are preserved
byte-for-byte:

```text
new analysis invalidated the prior ready version
new approved version requires fresh rendering and ready validation
```

Deferred to §4.3, deliberately and against the audit's Stage 8 grouping: relocating the
`_set_ready` / `_record_submission` / `record_decision` rules. §4.3 replaces those rules with
the `PreparationState` and `ready_qualified` projections, so moving them here would mean
writing them twice.

**A7.** One primitive — `verify_payload(path, expected_hash) -> ok | missing | tampered` —
behind the four current copies: `cli.generic_reconcile`, `migration.reconcile_migration`,
`migration`'s live historical-artifact check, and `application/ready.py`. Each caller keeps its
own message strings and issue codes, so no reconcile or Ready output text changes.

## 9. Waves, ownership, and definition of done

Lead-only for the whole boundary: `tests/conftest.py`, `tests/test_architecture.py`,
`cv_engine/cli.py`, `cv_engine/runtime/composition.py`, `cv_engine/runtime/workspace.py`,
`cv_engine/runtime/config.py`, `cv_engine/infrastructure/migration.py`, `docs/**`.

**Wave 0 — lead alone.** `infrastructure/paths.py` and its repointing; architecture guardrails
(`sqlite3`/SQL/`PRAGMA` only inside `persistence/`, with `migration.py` and `legacy_source.py`
as the existing allowlisted offenders; containment implemented only in `paths.py`; every
`migrations/*.sql` numbered, unique, and registered; the composite holds no SQL; the two-entry
debt allowlist does not grow); the schema-fingerprint baseline captured from today's database;
and coverage for the `db.py` behaviour later waves move (generic-transition refusals,
`set_ready` / `record_submission` preconditions, `record_decision` ownership refusals,
`register_artifact_version` versioning, `artifact_inventory`, `integrity_check`,
`set_next_action` through the service).

**Wave 1 — two lanes, one worktree each, same base commit.**

- **Lane A** owns `infrastructure/db.py` → `infrastructure/persistence/**`,
  `application/ports.py`, `tests/test_database.py`, new `tests/test_persistence.py`. It keeps
  `db.py` as an explicit temporary re-export
  (`# temporary re-export: removed in Wave 2`) so its diff stays inside its own files.
- **Lane B** owns new `infrastructure/payloads.py` and new `tests/test_payload_store.py`, reads
  `paths.py`, and touches nothing else.

**Wave 2 — lead alone.** Merge A → B, running the lane subset and the full suite after each
merge; then, as separate scoped commits: delete the re-export and repoint every importer
(`composition.py`, `migration.py`, `cli.py`, and the eight test modules importing
`cv_engine.infrastructure.db`), proving by grep that nothing imports the old path; A26 + A27 +
A29 wiring; A2; A7; then this document's evidence section, the audit's remaining-work update,
and the applicable §4.7 ticks.

No wave 3: nothing here is approval-gated.

Per-lane done, with command output quoted: own subset passes; the full suite passes; the
architecture test passes with an allowlist that has not grown; `git diff --stat` lists only
owned files; and an explicit statement that no threshold, message string, exception type,
validation-group name, status, callable signature, stored shape, artifact-path policy, or fact
semantic changed. Anything not achievable mechanically is reported as a finding, not worked
around.

## 10. Verification contract

Canonical interpreter: this worktree's `./.venv/bin/python` (audit §6). Evidence from another
worktree's environment is not accepted. Pre-change baseline: **124 collected**.

1. `./.venv/bin/python -m pytest -q` and
   `env CV_REQUIRE_BROWSER=1 ./.venv/bin/python -m pytest -q` — at least 124, with the count
   delta explained (new persistence, payload, and containment tests only).
2. `tests/test_golden.py` — no semantic difference in selected facts, rendered claims,
   validation outcomes, Ready eligibility, or decision behaviour.
3. Schema fingerprint: a database built from `0001_baseline.sql` is structurally identical to
   the captured M1 baseline.
4. Real SQLite integration (§4.7 items 1–2): migration application and re-application,
   checksum-change refusal, lower/higher version gates, UnitOfWork commit/rollback including
   the A2 atomic demotion, update/delete rejection on all eleven immutable tables, foreign-key
   enforcement, and WAL/busy-timeout behaviour with two concurrent writers.
5. Payload store: layout, atomic rename, hash, overwrite refusal, traversal and symlink-escape
   refusal, temp-orphan reporting.
6. Containment and CLI compatibility: `--db` accepted in-root (relative and absolute), refused
   out-of-root and through a symlink; `CV_DATABASE` likewise; config read only after marker
   validation; symlinked default child root refused.
7. Offline CLI end to end on a **fresh** `purpose=development` / `data_class=copy` Workspace
   with `OPENAI_API_KEY` unset: `workspace status` → ingest → analyze → draft → validate →
   approve → render → `cv ready` → `cv reconcile`, and `cv fast`, both reaching Ready with a
   one-page PDF.
8. Baseline-adoption drill on a **copy** of `.workspace/dev`: adoption stamps `0001` after a
   fingerprint match; application, snapshot, and artifact-version counts and every artifact
   hash are unchanged; `cv reconcile` passes.

No command in any lane opens live v1 data at `/Users/matanmalka/Projects/resume_python`.

## 11. Stop conditions

Stop and report rather than work around:

- a move needs a stored shape, message string, exception type, validation-group name, or
  status semantic to change;
- the adoption fingerprint mismatches on the dev copy;
- `--db` compatibility needs behaviour beyond "reject outside `state_root`";
- the architecture debt allowlist would need a new entry;
- a lane needs a file it does not own;
- `tests/test_golden.py` reports any semantic difference;
- an M2 §4.7 criterion cannot be honestly assessed.

## 12. Wave 0 verification findings

Wave 0 (`2e7b06f`, `4660f28`, `97c9cf4`, `0cc4b63`) was independently reproduced: 131 passed
under `./.venv/bin/python -m pytest -q`, +7 from the 124 baseline and fully accounted for (four
architecture guards, three database/service scenarios, no test removed); the debt allowlist is
unchanged at two entries; the containment repointing preserves every existing error type and
message; the frozen fixture matches a freshly built database exactly (43 rows recounted
independently); and both live new guards were confirmed to **fail** on an injected SQL string
and an injected containment predicate before the probe was reverted.

Four items to close, none of them blocking wave 1:

1. **The SQL/PRAGMA guard is narrower than §4 requires.**
   `test_sqlite_and_sql_are_owned_by_persistence` iterates `_modules("infrastructure")` only, so
   a raw SQL string or `PRAGMA` added to `cli.py`, `runtime/**`, or `application/**` passes
   undetected. Widen it to the whole package, keeping the same skip list
   (`persistence/`, `migration.py`, `legacy_source.py`, and the temporary `db.py` exemption).
2. **Two guards are inert until Lane A creates their targets.**
   `test_numbered_migrations_are_registered_once` and `test_composite_repository_contains_no_sql`
   both return early when `persistence/migrations/` and `persistence/composite.py` do not exist.
   That is correct for wave 0, but wave 2 must prove they are live — a differently named
   directory would leave them silently vacuous forever.
3. **`Workspace.relative()` widened for relative input.** It previously resolved a non-absolute
   path against the process CWD, which almost always raised
   `WorkspaceError: path is outside the Workspace`; `relative_within` now interprets it as
   root-relative and returns it. Artifact rows are built from this method, so a CWD-relative
   accident must not become a valid-looking Workspace-relative record: restore the refusal for
   non-absolute input, or state explicitly why root-relative is now correct.
4. **The `db.py` SQL exemption is time-boxed.** `PERSISTENCE_MOVE_SOURCE = "db.py"` in
   `tests/test_architecture.py` must be deleted in wave 2 together with the file, so a future
   `infrastructure/db.py` cannot reappear pre-exempted.

## 13. Evidence

Boundary 1 implementation closed at `4796744` on 2026-08-18. Waves 0–2 landed; no wave 3 work
was required. Commits, in order: `2e7b06f`, `4660f28`, `97c9cf4`, `0cc4b63` (wave 0);
`abbda75`, `44d1289`, `22548d7`, `368e471` (wave 1 and its A → B integration); `b326ced`,
`2f09c76`, `5e85eaf`, `eda7364`, `4796744` (wave 2). `f51ff07` committed this brief's §3 and
§12 amendments.

### Independent verification (Claude, 2026-08-18, `4796744`)

Reproduced under this worktree's `./.venv/bin/python`, the canonical interpreter:

| Gate | Result |
| --- | --- |
| `./.venv/bin/python -m pytest -q` | 154 passed |
| `env CV_REQUIRE_BROWSER=1 ./.venv/bin/python -m pytest -q` | **154 passed, exit 0** — the gate the executing session could not recover |
| `-m browser` selection under `CV_REQUIRE_BROWSER=1` | 4 passed, 150 deselected — real rendering/PDF/ATS coverage executed, not merely collected |
| `tests/test_golden.py` | 1 passed; no semantic difference in selected facts, rendered claims, validation outcomes, Ready eligibility, or decision behaviour |
| Test-count accounting | 124 → 154. 25 new test functions, **zero removed** (`git grep` of test function names at `d835ca9` versus `4796744` diffs empty in the removal direction); the +30 collected delta is those 25 plus parameterisation |
| Debt allowlist | shrank from two entries to one (`infrastructure/migration.py: imports subprocess`, A24, deferred to §4.6) |
| Frozen fingerprint fixture | byte-for-byte unchanged since `97c9cf4`; `schema_migrations` excluded by name with the reason in a comment |
| `0001_baseline.sql` | 14 declared tables, 22 triggers, 6 indexes; `status_history.id` keeps `AUTOINCREMENT`; `sqlite_sequence` not declared |
| Guard live-ness | `persistence/migrations/0001_baseline.sql` and `persistence/composite.py` both exist, so neither previously-inert guard is vacuous |
| Lane isolation | `infrastructure/payloads.py` imports only `..util` and `.paths` — nothing from `persistence`, no `sqlite3` |
| Old import path | `infrastructure/db.py` deleted; no production module or test imports it; only the guard's own detector strings name it |

Guards were **negative-tested**, not merely observed passing. An injected SQL string in
`cli.py` and an injected `PRAGMA` in `runtime/composition.py` both failed
`test_sqlite_and_sql_are_owned_by_persistence` (proving the wave-2 widening reaches beyond
`infrastructure/`); an injected SQL string and an injected containment predicate in
`infrastructure/artifacts.py` failed their respective guards during wave 0. Every probe was
reverted and the worktree confirmed clean.

### Baseline-adoption drill, reproduced independently

On a scratch copy of `.workspace/dev` (the original was never opened):

- `cv workspace status` → `purpose=development`, `data_class=copy`;
- `cv reconcile` → `passed: true`, 5 artifact versions checked, no problems, fact lifecycle
  `passed: true`;
- application, job-snapshot, job-analysis, artifact-version, and status-history counts
  identical before and after (1 / 1 / 1 / 5 / 3);
- all five registered artifact hashes byte-identical before and after;
- `sqlite_master` table count 15 → 16, the single addition being `schema_migrations`, stamped
  `('0001', '0001_baseline.sql')`.

Live v1 data at `/Users/matanmalka/Projects/resume_python` was not opened at any point.

### §4.7 status — deliberately not ticked

No `docs/v2/spec/implementation-plan.md` §4.7 checkbox is claimed by this boundary. Item 1
(repositories/UoW under real SQLite) and item 2 (immutable entities reject bypasses) are
covered *for the M1 table set only*; the v2 entities they will finally be judged against arrive
in §4.2. Item 7 (no M2 code points to live v1 paths) holds so far but is a standing constraint
rather than a boundary deliverable. Ticking partial coverage would misreport the milestone.

### Follow-up for boundary 3 (§4.3)

Cross-owner atomicity inside the persistence package is implemented by private reach-ins
(`applications._insert_application`, `._transition_status`, `._set_status` called from
`preparation.py` and `tracking.py`) rather than the `bind(uow)` composition D7 describes, which
does exist on `SqliteRepositoryBase`. Behaviour is unchanged and every call site is
same-package, so this is not a defect. What it costs is defence in depth: the public
`transition_status` refuses READY and APPLIED, but `_transition_status` does not, and
`_set_status` performs no `transition_allowed` check at all, so those invariants now rest on
convention. §4.3 replaces these rules with the `PreparationState` / `ready_qualified`
projections; when it does, either give the internal primitives their own invariant or route
cross-owner writes through `bind(uow)`.

`cv workspace status` reports `schema_version: null` until the database has been created or
adopted, and `"0001"` afterwards. That is correct — status must not create or adopt a database
as a side effect — but the null is worth keeping in mind when reading a fresh Workspace's
status output.
