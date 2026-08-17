# v1 to v2 Migration Plan

Status: **Draft for review**

Product authority: `docs/v2-product-spec.md`

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
2. v2 never opens the v1 live Workspace during implementation, Alpha, or Beta.
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

The v1 and v2 development Workspaces use distinct marker/config, SQLite, Knowledge,
artifact, temp, and log roots.

The v2 runtime guard refuses a Workspace marked as:

- workspace version 1 with live data in development mode
- an unknown/missing marker during a mutating migration command
- a Workspace ID or data class that differs from the signed/verified migration input

Guarding is based on marker metadata and expected hashes, not path naming.

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

The pre-migration backup includes:

- SQLite database plus required sidecar handling
- all version-controlled Knowledge sources used by the Workspace
- all immutable and working snapshots/revisions/artifacts in scope
- Workspace/config metadata required for restore
- current source version/tag/commit metadata
- restore instructions
- a manifest with path, type, size, and SHA-256 for every payload
- database/entity count summary

Verification checks archive integrity, manifest completeness, every hash, source counts,
and restore instructions.

Restore extracts to a new temporary directory only. It never overlays a live Workspace.
The restored v1 Workspace is opened with v1-compatible read/integrity/reconciliation
tools and compared with the backup manifest.

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
equivalent. Otherwise create explicit migration events with source references. Do not
invent dates or reasons.

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

There is no ReadyRevision table. Migration may project an ApprovedRevision as Ready only
when it can prove all v2 requirements against exact migrated artifacts:

- exact approved content and claim lineage
- registered HTML/PDF/visual artifacts
- passing render/PDF/ATS validation applicable to those exact artifacts
- successful integrity verification
- JobSnapshot + JobAnalysis compatibility

Otherwise preserve the historical v1 ready claim as metadata/history and derive the
active PreparationState without granting v2 Ready.

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

### Stage A — inventory

- verify source SQLite integrity and foreign keys
- inventory every entity/file/hash
- detect missing/cross-owned/duplicate/unregistered items
- produce signed/hashed inventory report

### Stage B — backup and restore proof

- create complete timestamped backup
- verify manifest and hashes
- restore into a new temporary directory
- open and reconcile restored v1 copy
- prove counts/hashes match inventory

### Stage C — schema mapping tests

- run unit mapping tests
- run representative migration fixtures
- prove deterministic status/entity/artifact mappings
- prove unsafe/incomplete records become explicit historical exceptions rather than
  guessed active entities

### Stage D — full dry run on restored copy

- create a new v2 copy Workspace and marker
- run migration into the target schema/filesystem
- reconcile database, Knowledge, lineage, paths, hashes, and counts
- run v2 application queries and relevant acceptance tests
- produce dry-run report and hash

### Stage E — Beta on a fresh faithful copy

- repeat against a new current copy rather than reusing an old rehearsal
- run the complete Web/CLI v2 acceptance suite
- verify backup/restore of the migrated v2 copy
- investigate every warning/unmapped item
- require `unexplained = 0`

### Stage F — Release Ready report

- record source/target versions
- attach inventory, backup, restore, dry-run, mapping, reconciliation, and acceptance
  evidence
- do not access live v1 for mutation

### Stage G — separately authorized live cutover

- freeze v1 writes
- repeat inventory delta check
- create and verify final backup/restore
- run exact proven migration
- reconcile and run full acceptance
- activate v2 only after every gate passes

## 8. Migration gate report

The apply command requires an exact gate report proving:

- expected source Workspace ID/data class/version
- source inventory hash and counts
- verified backup/archive/manifest hashes
- verified restore path/report hash
- migration code/product/database versions
- passing migration test report hash
- successful full dry-run report hash
- expected source/target entity and file counts
- explicit mapping policy version
- zero unresolved critical warnings
- zero unexplained records/files

The command refuses a different source state, changed inventory, missing artifact,
failed restore proof, stale report, or mismatched Workspace marker.

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

Cutover Complete is separate from Engineering Complete and Release Ready. It requires:

- [ ] v1 writes frozen
- [ ] final source inventory captured
- [ ] final backup verified and restored
- [ ] migration apply gate passed
- [ ] migration completed without partial state
- [ ] reconciliation passed with zero unexplained items
- [ ] full v2 acceptance passed on migrated live Workspace
- [ ] v2 activated
- [ ] user confirmed normal access to expected Applications/artifacts
- [ ] rollback evidence retained

The product is never cut over as an experiment. Release Ready must already be proven on
a faithful copy.
