# v1 to v2 Migration Plan

Status: **Approved for v2.0 implementation (2026-08-17)**

Product authority: `docs/v2/spec/product-spec.md`

Source baseline: `v1.0.0` / `2cc31c7`

## 1. Migration objective

Move a verified v1 Workspace into the v2 storage, lifecycle, and provenance model while
preserving every source fact, Application, immutable JobSnapshot, analysis, status
event, decision, artifact, submission, and historical meaning. Migration must not
invent approval, Ready qualification, submission, candidate facts, or missing
relationships.

The migration is one-way at the data-schema level. Rollback restores or reuses the
frozen v1 backup and runs v1; it does not downgrade a v2 database.

## 2. Non-negotiable safety rules

1. Development and migration rehearsal use copies only.
2. v2 never opens the v1 live Workspace during implementation or rehearsal.
3. No dual-write, shadow-write, or bidirectional sync is implemented.
4. Live v1 writes are frozen before the cutover backup.
5. A complete backup must exist, verify, restore, open, and reconcile before migration.
6. Migration is tested against a restored/fresh faithful copy before live execution.
7. Existing IDs are preserved only where semantic equivalence exists.
8. Existing files are never overwritten, normalized, renamed, or re-rendered in place.
9. File existence does not grant ApprovedRevision or Ready semantics.
10. Every source record and file must be mapped, explicitly excluded with a reason, or
    reported as an error. The acceptance target is zero unexplained items.
11. Any failed gate stops the procedure before further live mutation.

## 3. Workspace isolation

The v1 and v2 development Workspaces use distinct config, SQLite, Knowledge, artifact,
temp, and log roots. A legacy v1 source is not assumed to have a Workspace marker.

Every normal v2 runtime command fails closed on a missing, legacy, unknown, or unsafe
marker. The dedicated migration source adapter is the only code allowed to inspect an
unmarked v1 root: it receives an explicit source path, opens it read-only, inventories
it, and binds subsequent reads to the inventory hash. It never writes a marker, temp
file, database change, or other payload into the source. The v2 marker is created only
on the separate target copy.

Migration apply also refuses a target marker whose Workspace ID, purpose, or data class
differs from the verified gate input. Guarding is based on target marker metadata and
source inventory hashes, not path naming.

## 4. Source inventory

The migration inventory is regenerated at migration time and does not rely only on old
documented counts. It includes:

- v1 database schema/version and integrity
- Applications and all fields
- JobSnapshots and their original text/hashes/provenance
- JobAnalyses and versions
- status history and application events
- next actions and notes
- artifacts and artifact versions
- decision records
- generation and validation runs
- submissions
- fact lifecycle events
- Knowledge files and hashes
- Candidate/contact facts and filename policy evidence
- all registered artifact paths/hashes
- all unregistered files under relevant historical/active roots
- migration/snapshot/restore evidence already present

The final inventory report records source counts, duplicates, missing references,
orphan files, integrity errors, and an inventory hash.

The v1 baseline evidence at planning time included 127 registered artifact versions and
86 canonical facts, but these are not hardcoded migration expectations. The fresh
inventory is authoritative for the actual copy/cutover.

## 5. Backup contract

Most of the v1 record is version-controlled in this repository. `outputs/`, `jobs/`,
`base/`, and `cv-html/` are tracked, which covers the tailored CVs, the rendered HTML
and PDFs, the job descriptions, and the status timeline. Git is already
content-addressed, already hashes every blob, and already restores into a fresh
directory:

```bash
git worktree add <new-directory> <frozen-v1-commit>
```

That single command is the archive, the manifest, and the restore proof for every
tracked payload. Do not reimplement it as a tar archive with a hand-built manifest and a
separate hash list; a manifest maintained beside Git can only drift away from it.

A separate backup covers only what Git does not track:

- `data/applications.sqlite3` and its WAL sidecars, copied with the SQLite backup API
  rather than `cp`, so the copy is transactionally consistent:

  ```bash
  sqlite3 data/applications.sqlite3 ".backup <target>"
  ```

- any artifact or Knowledge file the Stage A inventory finds outside Git

Verification is the count and hash comparison in section 8, run against the restored
worktree and the restored database. Restore always targets a new directory and never
overlays a live Workspace.

## 6. Target model mapping

### 6.1 CandidateContext and Knowledge

- Create one CandidateContext for the Workspace.
- It references existing canonical name/contact facts and defines Latin recruiter
  filename policy, timezone, and locale.
- Do not duplicate candidate identity into every Application.
- Preserve all v1 semantic fact IDs and source locations.
- New future v2 facts use UUIDv4; migration does not rename old IDs.
- Preserve Profile/policy/prompt/rule files and hashes with any required versioned
  schema conversion performed on copies.
- Record exact source and target Knowledge versions and mapping.

### 6.2 Applications and recruitment status

Preserve Application IDs and ordinary fields where semantics are equivalent.

Status mapping:

```text
v1 preparing -> v2 saved
v1 ready     -> v2 saved
v1 applied   -> v2 applied
v1 recruiter_screen -> v2 recruiter_screen
v1 interview -> v2 interview
v1 assignment -> v2 assignment
v1 final_stage -> v2 final_stage
v1 offer -> v2 offer
v1 accepted -> v2 accepted
v1 rejected -> v2 rejected
v1 withdrawn -> v2 withdrawn
v1 closed -> v2 closed
```

PreparationState is derived from migrated context; it is not blindly mapped from the
old status string. A historical v1 `ready` claim is retained in migration history but
does not qualify as v2 Ready unless the exact v2 qualification can be verified.

Preserve status-history IDs when representation and identity are semantically
equivalent. Every legacy history entry containing `preparing` or `ready`, which are not
valid v2 RecruitmentStatus values, is retained as an append-only migration event with:

```text
actor_type = migration
legacy_event_id
legacy_from_status
legacy_to_status
mapped_from_status = map(legacy_from_status)
mapped_to_status = map(legacy_to_status)
source timestamp and metadata
```

The raw legacy status strings remain textual provenance and are not inserted into the
v2 enum-constrained transition columns. The mapping function is the status table above,
so `preparing -> ready` becomes `saved -> saved`, while `ready -> applied` becomes
`saved -> applied`. Repeated mapped `saved` values do not invent new business
transitions; the migration event appears in the unified timeline while the
Application's current status projection uses the mapping above. No legacy event is
deleted or folded. For all other non-equivalent representations, create explicit
migration events with source references. Do not invent dates or reasons.

For closed Applications, derive terminal outcome only from actual preserved status
history; do not guess.

### 6.3 JobSnapshots

Preserve JobSnapshot IDs, Application ownership, versions, source URL/provenance,
timestamps, prior links, and original content.

v1 snapshot text currently held in SQLite is written as an immutable filesystem payload
under:

`snapshots/{application_id}/{snapshot_id}.txt`

Record the exact v1 text representation accepted from SQLite, SHA-256, normalized
dedupe hash, path, and migration provenance. Do not normalize content before writing.

### 6.4 JobAnalyses

Preserve IDs and structured content where it satisfies the v2 immutable analysis
contract. Record source schema/version and migrate serialization deterministically.

If a v1 analysis lacks a required v2 field that can be deterministically derived without
changing meaning, record the derivation and target schema version. If derivation would
require semantic judgment, preserve the analysis as historical/incomplete and require a
new active analysis rather than guessing.

### 6.5 SelectionPlans

v1 selection manifests may map to v2 SelectionPlans only where the candidate pool,
selected/excluded/pinned facts, policy versions, and ownership can be accounted for.

If exact v2 candidate-context dependencies cannot be reconstructed, preserve the v1
selection evidence as historical provenance and require a new SelectionPlan for active
work. Do not create a falsely complete plan.

### 6.6 WorkingDraft

At most one v1 active working draft may map to the one v2 WorkingDraft for an
Application, and only when Application/JobSnapshot/JobAnalysis ownership and exact
content/claim lineage pass the chain contract.

Unbound, stale, cross-Application, legacy-schema, or otherwise unsafe working content is
preserved as historical evidence rather than activated. Migration never approves a
working draft.

### 6.7 ApprovedRevisions

A v1 approved artifact version maps to an ApprovedRevision only when v1 already
recorded genuine approval and exact Application, JobSnapshot, JobAnalysis, facts,
content hash, claim manifest, decision, and ownership can be reconciled.

Historical migrated files, legacy outputs, or files merely named like a CV do not map to
ApprovedRevision.

For a valid mapping:

- preserve semantically equivalent source IDs where possible
- write immutable revision JSON/Markdown payloads under v2 paths
- preserve original source bytes as registered historical/source artifacts when a
  projection format changes
- record source and target hashes
- record CandidateContext/Knowledge context available at migration
- do not rewrite old content to current facts

### 6.8 Artifacts

Preserve every registered v1 artifact ID where it remains the same conceptual artifact;
otherwise create a target artifact ID and explicit mapping.

Never move or rename source historical files in place. A v2 Workspace copy may either
reference a protected migrated historical location or copy bytes to an immutable v2 ID
path. In either case, source and target hashes must match unless a separately registered
projection was intentionally generated.

HTML/PDF/screenshot/manifest existence and hash are reconciled. A migrated artifact is
not re-rendered merely to fit the v2 path model.

### 6.9 Ready qualification

There is no ReadyRevision table. Migration may establish `ready_qualified` for an
ApprovedRevision only when it can prove the context-independent v2 requirements against
exact migrated artifacts:

- exact approved content and claim lineage
- registered HTML/PDF/visual artifacts
- passing render/PDF/ATS validation applicable to those exact artifacts
- successful integrity verification

JobSnapshot + JobAnalysis compatibility is evaluated separately when deriving the
active PreparationState. A qualified but incompatible revision remains historical for
the active context. If qualification itself cannot be proven, preserve the historical
v1 ready claim as metadata/history without granting `ready_qualified`.

### 6.10 Decisions, runs, and validations

Preserve decision records, generation runs, provider/model/task/prompt versions,
validation reports, and ownership IDs. A v1 run missing a v2 field remains historical;
migration does not invent provider usage, prompt hashes, or validator evidence.

### 6.11 Submissions

Preserve v1 submissions and exact artifact links. A valid existing internal submission
must reference the exact registered artifact that v1 recorded. An application known to
be applied without an internal artifact maps to external-submission semantics rather
than a fake ApprovedRevision/Artifact.

### 6.12 Historical and legacy material

Legacy v1 migration history, historical application artifacts, base artifacts, and any
pre-v1 evidence remain immutable. They receive accurate migrated/historical badges and
source provenance. They are visible by default in Dashboard queries when they represent
Applications; unrelated reference artifacts do not become Applications.

## 7. Migration implementation stages

Five stages. The source is a frozen Git commit and the target is always a fresh
Workspace, so a stage can be re-run from scratch at any time; nothing accumulates state
that a later stage has to clean up.

### Stage A — freeze and inventory

- record the frozen v1 commit; no further v1 writes after it
- verify source SQLite integrity and foreign keys
- inventory every entity, file, and hash, including anything outside Git
- detect missing, cross-owned, duplicate, or unregistered items

### Stage B — copy the source

- `git worktree add` the frozen commit into a new directory
- `.backup` the SQLite database if one exists
- compare counts and hashes against the Stage A inventory

### Stage C — mapping tests

- run unit mapping tests
- run representative migration fixtures
- prove deterministic status/entity/artifact mappings
- prove unsafe or incomplete records become explicit historical exceptions rather than
  guessed active entities

### Stage D — dry run on the copy

- migrate the copy into a new v2 target Workspace
- reconcile database, Knowledge, lineage, paths, hashes, and counts
- run v2 application queries and the relevant acceptance tests
- investigate every warning and unmapped item; require `unexplained = 0`

### Stage E — separately authorized cutover

- confirm the frozen commit is unchanged
- run the exact migration Stage D proved, into the Workspace that will be used
- reconcile and run full acceptance
- activate v2 only after every gate passes

## 8. Migration gate

The apply command refuses to start unless it can prove, from the data itself:

- the frozen source commit and source root identity, plus the exact inventory hash
- the expected target v2 Workspace ID, purpose, data class, and version
- hashes of the backed-up payloads Git does not track
- source and target entity and file counts, reconciled as

  ```text
  source_count == migrated_count + explicitly_excluded_count
  ```

- zero unexplained records or files, and zero unresolved critical warnings

Each item is checked against the source and target at apply time. The gate does not
accept the hash of a report as evidence: hashing a report proves only that the paperwork
is unchanged, not that the data matches. Count parity is enforced in code and raises
rather than logging, because the failure it catches — rows silently dropped by a join or
a filter during a rebuild — leaves no trace in a table that immutability triggers then
protect.

The command refuses a different source state, changed inventory, missing artifact,
failed restore comparison, or mismatched Workspace marker.

## 9. Reconciliation

Reconciliation verifies at least:

- SQLite integrity and foreign keys
- entity ownership and lineage
- current projections versus append-only history
- JobSnapshot and ApprovedRevision payload paths/hashes
- artifact paths, hashes, type, revision, and registration
- submission artifact relationships
- Ready qualification evidence
- Knowledge file identity, versions, and lifecycle/audit agreement
- CandidateContext fact references and hash
- SelectionPlan candidate-context hashes
- mutation-journal terminal state
- Operation output registration/activation
- all inventory items accounted for

Full SHA-256 artifact reconciliation is explicit and is not run on every startup.

## 10. Startup after migration

Normal startup performs a light check:

- Workspace marker and configured roots
- database schema compatibility
- SQLite quick/integrity check appropriate to startup
- expired leases/interrupted Operations
- Knowledge quarantine/journal status
- temp cleanup candidates

It does not silently migrate schema or run a complete artifact hash scan.

## 11. Cutover rollback

If migration, reconciliation, acceptance, or activation fails:

1. stop v2 and preserve its failed Workspace/report for diagnosis
2. do not attempt a reverse SQL migration
3. restore or reuse the verified frozen v1 Workspace
4. restart v1 against that exact state
5. verify v1 integrity and reopen writes only after verification
6. record the failed cutover and reason

No successful v2 writes are merged backward into v1. The no-dual-write rule keeps this
rollback deterministic.

## 12. Live cutover completion

Cutover Complete is separate from Engineering Complete. It requires:

- [ ] v1 writes frozen at a recorded commit
- [ ] source inventory captured and unchanged since Stage A
- [ ] untracked payloads backed up and compared
- [ ] migration apply gate passed
- [ ] migration completed without partial state
- [ ] reconciliation passed with zero unexplained items
- [ ] full v2 acceptance passed on the migrated Workspace
- [ ] v2 activated
- [ ] user confirmed normal access to expected Applications/artifacts

Rollback evidence needs no separate step: the frozen commit and the database backup are
the rollback. The product is never cut over as an experiment — Stage D must already have
proven the exact migration on a copy.
