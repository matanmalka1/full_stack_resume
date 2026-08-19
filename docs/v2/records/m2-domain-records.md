# M2 Boundary 2 — Domain Records (design and execution brief)

Status: **Designed 2026-08-18; not implemented.** Base commit: `856fc7c`.

Scope: `docs/v2/spec/implementation-plan.md` §4.2, plus the inherited items the boundary 1 brief
assigned here: Stage 7b (ValidationRun report schema version and the draft-side group rename),
A5 (typed decision record), A4 (render/Ready policy into the domain behind a typed evidence
DTO), the A2 residue (`_set_ready` / `_record_submission` / `record_decision` rules), and
per-service repository repointing with the rest of A16's port narrowing.

Authority: `docs/v2/spec/product-spec.md` §6 invariants 3–12 and 16–21, §8, §10, §11, §16;
`docs/v2/spec/state-and-use-cases.md` §2–§5, §12–§18; `docs/v2/spec/architecture.md` §6.1, §6.2, §8;
`docs/v2/spec/migration-plan.md` §6.2, §6.3, §6.6, §6.7, §6.9; `docs/v2/process/execution-protocol.md`.

Predecessor: `docs/v2/records/m2-schema-and-repositories.md` (boundary 1, closed at `4796744`).

## 0. What the review established

Two independent read-only surveys ran against `856fc7c`. Findings that shape this design:

1. **No v2 record exists.** `selection_plan`, `approved_revision`, `edit_version`,
   `ready_qualified`, `terminal_outcome`, `recruitment_status` have zero occurrences in
   `cv_engine/`. This boundary is additive, not a refactor of existing records.
2. **The payload store has no writer.** `cv_engine/infrastructure/payloads.py` implements the
   §6.2 layout and the §7.1 commit protocol, and nothing outside its own tests imports it.
   `PayloadStore._approved_destination` actively rejects the current
   `{artifacts_root}/{application_id}/v{NNN}/` layout, so approvals cannot be pointed at it
   without moving to `revisions/{application_id}/{revision_id}/`.
3. **SelectionPlan has no equivalent.** `SelectionManifest` exists only as an embedded field on
   `DraftDocument.selection`, versioned by a `superseded_by_manual_edit` flag rather than by
   creating a replacement record.
4. **The WorkingDraft is filesystem-only and has no concurrency token.**
   `FilesystemArtifactStore.write_working_draft` overwrites `working/{application_id}/resume.md`
   unconditionally; `DraftDocument.content_hash` is a field the domain sets by convention. There
   is nothing for `expected_version` to compare against.
5. **A v1 approval is two artifact rows, numbered by counting.** `DraftService.approve`
   registers `resume_markdown` and `claim_manifest` independently and derives the version as
   `len(existing) + 1`. v2 wants one ApprovedRevision owning its payloads with artifact
   metadata hanging off it.
6. **READY is stored in `applications.current_status`.** v2 invariant 6 forbids storing Ready at
   all, and the v1 enum carries `preparing` and `ready`, which are not among the eleven v2
   `RecruitmentStatus` values.
7. **Every repository port returns `dict[str, Any]`,** and the services index those rows by
   string key in roughly forty places (`chain.py` and `application/ready.py` are the densest).
8. **Three separate validation group vocabularies already exist**: four groups in
   `domain/validation.py:69`, eight in `infrastructure/rendering.py:189-198`, six in
   `application/ready.py:28-35`. Only the first is touched by Stage 7b.

## 1. Sub-boundaries

The §4.2 list is too large for one green boundary, so it splits in dependency order.

**2a — preparation records.** JobSnapshot payload and metadata; SelectionPlan as a first-class
immutable version; the one mutable WorkingDraft with `edit_version` and `content_hash`;
ValidationRun lineage plus Stage 7b.

**2b — approval, qualification, and tracking records.** ApprovedRevision; artifact metadata;
the `ready_qualified` projection with A4's typed render evidence; the A2 residue; immutable
submissions including external submissions; recruitment events with corrections,
`terminal_outcome`, and the retirement of `preparing`/`ready` from the recruitment axis; audit
records and the human-readable provenance export (A5).

2b is designed in outline here (§7) and detailed when 2a closes green.

## 2. Decisions

**D1 — records are additive; the read path moves per record, never duplicated.** Each record
cuts over to exactly one home as its slice lands, with the CLI as the sole writer. Writing a v2
record beside the v1 row it replaces would be a dual-write, which `docs/v2/spec/implementation-plan.md`
§11 lists as an unqualified stop condition; leaving the CLI on v1 records while a later API
writes v2 ones would be the second workflow engine `docs/v2/spec/architecture.md` §1 forbids.

**D2 — ports keep returning row mappings; new records get typed accessors.** Converting the
existing `dict[str, Any]` port surface to typed records would break every service and test at
once for no product gain. Existing accessors keep their shape. New record accessors
(`selection_plan`, `working_draft`, later `approved_revision`) return typed models from the
start, and the dict-returning accessors are converted per record in later boundaries when their
consumers are already being edited.

**D3 — the M1 fingerprint guard becomes a guard on migration `0001`, not on head.** Moving
snapshot text requires rebuilding an immutable table, which changes the DDL a fresh database
produces. `test_m1_sqlite_master_fingerprint_is_frozen` must therefore build a database with
**only `0001` applied** and compare that to the frozen fixture, with a separate assertion for
the head schema. **Regenerating `tests/fixtures/m1_sqlite_master.tsv` remains forbidden**; it is
the parity evidence that `0001_baseline.sql` reproduces the M1 schema.

**D4 — no backfill, and the column is removed in two steps inside this boundary.** Nothing needs
migrating: `.workspace/` is gitignored, no code or test references it, and the only v2 databases
in existence are three development Workspaces holding one Application each, reproducible with
`cv workspace init` plus `cv fast`. They are disposable and recreated. Real v1 data never travels
`0001 → 0002`; it lands once, at cutover, in whatever schema is then current, and writing its
snapshot text to `snapshots/{application_id}/{snapshot_id}.txt` is already
`docs/v2/spec/migration-plan.md` §6.3's requirement on the v1→v2 mapping, so payload writing is
implemented once, in `infrastructure/migration.py`.

The removal itself is staged: **`0002` adds `payload_path`, `source_hash`, and `normalized_hash`
and keeps `original_text`; `0003` drops `original_text` after the readers have moved.** Both
migrations land inside this boundary. The retained column exists for one execution stage, is
never written after the cutover commit, and is not a second source of truth at any point: during
`0002` it is still the only source, and after the cutover the payload is.

*Why it is staged, recorded so the reasoning is not lost:* the first version of this design had
`0002` remove the column outright. `original_text` has four production consumers —
`infrastructure/persistence/preparation.py`, `application/queries.py`,
`application/services/analysis.py`, and `infrastructure/migration.py`. Removing the column while
three of those still read it makes the suite fail, and no single work package could repair it
without reaching across the ownership boundary. The staged form is the protocol's §4 interface
contract applied to storage shape rather than to imports: preserve the old read path for the
duration of the package that changes the shape.

*Also withdrawn earlier:* an explicit `cv workspace upgrade` backfill with per-row hash
verification and retention of `original_text` until §4.6. That protected only disposable
development data, duplicated the §6.3 mapping, and deferred invariant 19 by a milestone.

**D5 — the on-disk Markdown becomes a declared projection, and `cv sync-draft` becomes an
explicit import.** SQLite owns the WorkingDraft structured source per architecture §6.1, so
`resume.md` under `working/` stops being a source of truth. The v1 manual-edit workflow is
preserved rather than removed: `cv sync-draft` reads the projection file, classifies the
claims exactly as today, and commits the result as a new `edit_version`. Nothing else promotes
file edits.

**D6 — `UNIQUE(application_id, content_hash)` on `job_snapshots` stays.** v2 says duplicates are
warnings, never blockers, but that is duplicate-detection policy for Applications and belongs
with the warning model in M3. Changing a constraint that currently refuses an insert is a
behaviour change this boundary has no reason to make.

**D7 — Stage 7b touches exactly one vocabulary.** The draft-side group `filename` becomes
`headline_safety` in `domain/validation.py` only. The render report keeps its `filename` group
and the Ready-integrity report keeps its six groups. `report_schema_version` is added in-report;
an absent version means legacy; historical rows are never rewritten.

## 3. Record model — 2a

### 3.1 JobSnapshot (migrations `0002` and `0003`)

`0002` adds `payload_path TEXT`, `source_hash TEXT`, and `normalized_hash TEXT` to
`job_snapshots` as nullable columns and leaves `original_text` in place, so every existing reader
keeps working while the payload writers are built. `0003`, after the readers have moved, rebuilds
the table without `original_text` and with the three new columns `NOT NULL` — the standard SQLite
sequence in one transaction: drop triggers, create the new table, copy rows, drop the old, rename,
recreate the `no_update_`/`no_delete_` pair. `UNIQUE(application_id, version_number)` and
`UNIQUE(application_id, content_hash)` survive both migrations; D6 keeps the latter deliberately.

The payload lives at `snapshots/{application_id}/{snapshot_id}.txt`, byte-exact, with no
line-ending normalisation (`docs/v2/spec/migration-plan.md` §6.3). `source_hash` is the hash over the
exact received representation — today's `content_hash` value — and `normalized_hash` is the
separate dedupe hash `docs/v2/spec/product-spec.md` §8 requires. Writers follow §7.1: write the payload
through `PayloadStore.commit` first, register second, so a failed registration leaves a
reconcilable orphan rather than a dangling row.

Two writers exist and both must produce identical results: the ingest path in the application
layer, and `infrastructure/migration.py`'s v1→v2 mapping, which currently inserts `original_text`
directly.

### 3.2 SelectionPlan (new immutable table)

`selection_plans`: `id`, `application_id`, `job_analysis_id`, `version_number`, `plan_json`,
`candidate_context_version`, `candidate_context_hash`, `profile_version`,
`selection_policy_version`, `track_emphasis_dependencies_json`, `created_at`, with
`UNIQUE(application_id, version_number)` and a `no_update_` / `no_delete_` trigger pair.

Every successful analysis creates its initial deterministic plan in the same transaction
(`docs/v2/spec/state-and-use-cases.md` §13), so `save_analysis` becomes one atomic
analysis-plus-plan write. `create_draft` takes an explicit `selection_plan_id`; the CLI gains
`--selection-plan` with a compatibility resolver for the omitted-argument case, matching the two
sanctioned resolvers already in `compat.py`.

### 3.3 WorkingDraft (new mutable table, one active per Application)

`working_drafts`: `id`, `application_id`, `job_analysis_id`, `selection_plan_id`,
`parent_revision_id` (null until 2b), `source_json`, `edit_version INTEGER NOT NULL`,
`content_hash TEXT NOT NULL`, `active INTEGER NOT NULL`, `created_at`, `updated_at`. One active
draft per Application is enforced by a partial unique index
(`CREATE UNIQUE INDEX ... ON working_drafts(application_id) WHERE active = 1`), not by a
filesystem path. No immutability triggers — this is the one mutable record.

`update_working_draft(id, expected_version, patch)` increments `edit_version`, recomputes
`content_hash`, and returns both; a mismatch is refused and changes nothing. The Markdown and
claim-manifest files remain as projections written beside the record (D5).

### 3.4 ValidationRun lineage and Stage 7b

Columns added to `validation_runs`: `working_draft_id`, `edit_version`, `content_hash`,
`job_snapshot_id`, `job_analysis_id`, `selection_plan_id`, `knowledge_context_hash`,
`validator_versions_json`. `phase` and `report_json` keep their current names and values. This
is what finally makes invariant 10 enforceable — one changed character moves `content_hash`, and
the run stops matching the draft it validated.

Stage 7b adds `report_schema_version` inside the report payload and renames the draft-side
group per D7.

## 4. Guard and test surface this boundary must maintain

The coupling survey identified five places where a new record silently weakens an existing
guarantee unless it is registered by hand. Each is part of the definition of done, not cleanup:

| Surface | Required action |
| --- | --- |
| `tests/test_persistence.py` `IMMUTABLE_TABLES` + `_seed_immutable_tables` | every new immutable table added to both, and to the migration's trigger pairs — otherwise immutability silently does not hold for it |
| `tests/test_chain_integrity.py` `PERSISTED_TABLES` | every new table added, or the "nothing was written" assertions pass while the new table gained a row |
| `tests/test_candidate.py` `POLICY_MODULES` | any new policy-bearing module added, and it must contain no candidate literal |
| `tests/test_application_contracts.py` | new boundary DTOs must expose no `path` field and no `Path`-typed annotation, and new ports must leak no private or adapter names |
| `tests/test_migration.py` | the hardcoded `semantic_counts` and entity counts change when tables are added; update them deliberately, with the new expectations justified |

Architecture rules that will bite by design: no `sqlite3`, filesystem call, or composed storage
path in `domain/` or `application/`; all SQL under `infrastructure/persistence/`; containment
only in `infrastructure/paths.py`; every new migration numbered and registered;
`ValidationReport.from_findings` remains the sole construction authority.

## 5. Execution shape — 2a runs serially

**2a has no parallel lanes, and no wave 0.** Both conclusions were reached the hard way and are
recorded here so the next boundary inherits the reasoning rather than the habit.

*No wave 0*: boundary 1 needed one because its work was a **move**, where a guard written
afterwards cannot fail on the move it was meant to catch, and where dead symbols had to go before
a lane adopted them. 2a is additive. Of the three candidate wave-0 items, one belonged to the
package that forces it, one was impossible before its tables existed (`_persisted()` runs
`SELECT 1 FROM {table}` per entry, and `IMMUTABLE_TABLES` is iterated to seed and tamper each
one), and one was a commit-ordering constraint.

*No lanes*: the first attempt split persistence from domain records and deadlocked. Two distinct
dependencies made the split unsound. The schema package could not reach the three lead-owned
`original_text` readers it had just invalidated, so its own green gate was unreachable (see D4).
And the typed accessors were assigned to the schema package while the models they return were
assigned to the domain package, so neither could be tested meaningfully alone. The dependency
graph here is a **chain**, not a fan, and the parallel half was small — models plus one rename.
Per `docs/v2/process/execution-protocol.md` §7, serial is the honest shape.

One executor works three stages in order, on one branch, in one worktree. Every stage ends green
before the next begins, which is the property the lane split destroyed.

**Stage 1 — domain records.** The typed SelectionPlan and WorkingDraft models and the
ValidationRun lineage type per §3.2–§3.4, plus Stage 7b per D7. Pure models: no filesystem call,
no composed storage path, no `sqlite3`. `SelectionManifest` and its `superseded_by_manual_edit`
flag stay as they are.

**Stage 2 — schema, additive.** Migration `0002` registered in `schema.py`: `job_snapshots` gains
`payload_path`, `source_hash`, `normalized_hash` and **keeps** `original_text`; `selection_plans`
and `working_drafts` are created, the latter with its partial unique index and no immutability
triggers; `validation_runs` gains its lineage columns. Repository methods return the Stage 1
models for the new records; existing dict-returning accessors are untouched. Because the change
is additive, every current reader still works and the suite stays green.

**Stage 3 — cutover and integration.** In order: the before-state test pinning today's
unconditional draft overwrite; PayloadStore wired into the ingest path and into
`infrastructure/migration.py`'s §6.3 mapping, both writing the payload before registering the
row; `application/services/analysis.py` and `application/queries.py` moved onto the payload;
atomic analysis-plus-plan; WorkingDraft reads and writes through the record with `edit_version`;
the CLI's `--selection-plan` resolver and `cv sync-draft` redefined per D5; the §4 guard
checklists now that the tables exist; migration `0003` dropping `original_text`; then full
verification per §6.

Salvage from the abandoned lane attempt: the fingerprint-guard re-point (D3) stands as committed
and is stage-independent. The additive rework replaces the schema commit that removed the column.
Uncommitted domain work becomes Stage 1.

## 6. Verification — 2a

Canonical interpreter `./.venv/bin/python`. Baseline at `5c2407d`: **154 passed**, including the
browser-required gate.

1. `./.venv/bin/python -m pytest -q` and `env CV_REQUIRE_BROWSER=1 ./.venv/bin/python -m pytest -q`,
   with the count delta explained and no test removed.
2. `tests/test_golden.py` — the Markdown and HTML hashes must not move. The WorkingDraft
   becoming a SQLite record changes where the draft is stored, not what it renders; a golden
   difference means the move changed behaviour.
3. Each stage ends with `./.venv/bin/python -m pytest -q` green before the next begins — the
   property the abandoned lane split destroyed.
4. Migrations `0002` and `0003` each apply to a fresh database and in sequence from a
   `0001`-only database; the checksum, ordering, and version-gate behaviour from boundary 1 still
   holds, and no database carrying rows is upgraded (D4).
5. After `0003`, no production module references `original_text`; proven by grep.
6. Snapshot payloads, proven on both writers: the CLI ingest path and the legacy-migration
   fixture each produce a payload whose SHA-256 matches its recorded `source_hash`, with the
   payload written before the row is registered. A fresh development Workspace is created from
   scratch to confirm the recreation path the disposal decision depends on.
7. `edit_version` concurrency: two saves from the same expected version — the second is refused
   and changes nothing.
8. One active WorkingDraft per Application enforced by the index, proven by a direct SQL insert
   attempt.
9. Offline CLI end to end on a fresh `development` / `copy` Workspace with `OPENAI_API_KEY`
   unset, through Ready, plus `cv fast`.
10. Live v1 data is never opened.

## 7. 2b outline

ApprovedRevision owning `revisions/{application_id}/{revision_id}/resume.{json,md}` through the
payload store, with artifact metadata rows for every rendered output under
`outputs/{application_id}/{revision_id}/`; the A5 typed decision record; A4's `RenderEvidence`
DTO moving the eight render groups into `domain/render_validation.py` so `ready_qualified` is
computed from stored evidence rather than a renderer call — which also breaks the two
`monkeypatch.setattr` targets in `tests/conftest.py` and requires the render group vocabulary to
stay byte-identical in both the production module and the fixture double; the `ready_qualified`
projection replacing stored READY, with the A2 residue moving out of the repository; immutable
submissions bound to a revision and its exact PDF artifact, plus `record_external_submission`;
recruitment events with `corrects_event_id` and a mandatory reason, `terminal_outcome`, and the
mapping of legacy `preparing` / `ready` history to migration events per
`docs/v2/spec/migration-plan.md` §6.2; and `export_decision_markdown`.

## 8. Stop conditions

Stop and report rather than work around: a golden hash moves; a snapshot payload's SHA-256 does
not match its recorded `source_hash`; a record change would require regenerating the frozen
fingerprint fixture; `edit_version` cannot be introduced without changing an existing refusal message or
exception type; a new immutable table cannot be covered by triggers; the architecture allowlist
would need a new entry; a lane needs a file it does not own; or
`infrastructure/migration.py` cannot write snapshot payloads without restructuring beyond the
§6.3 mapping it already owes.

## 9. 2a closure record

Boundary 2a implementation merged at `a9cc63a`; close-out and the two repairs below by the lead.
Independently verified on 2026-08-18 with this worktree's `./.venv/bin/python`.

| Gate | Result |
| --- | --- |
| `env CV_REQUIRE_BROWSER=1 … pytest -q` | **164 passed**, no test removed |
| `tests/test_golden.py` | hashes unmoved; a second case now guards the persisted-plan path |
| Migrations | a `0001`-only database upgrades through `0002` and `0003`; the resulting `job_snapshots` shape is identical to a fresh head database |
| `original_text` | no production module references it after `0003` |
| Snapshot payloads | written at the §6.2 path before registration, SHA-256 matching `source_hash`, normalized hash present |
| `edit_version` | a stale write raises `edit version mismatch` and leaves the record unchanged |
| One active WorkingDraft | the partial unique index refuses a second active row through raw SQL (fdb3515) |
| Offline CLI | fresh development/copy Workspace, `OPENAI_API_KEY` unset: ingest → analyze → draft → validate → approve → render → ready → reconcile, plus `cv fast`; both PDFs one page with the correct recruiter filename |
| Architecture allowlist | still one entry (`infrastructure/migration.py: imports subprocess`) |
| Frozen fingerprint | `tests/fixtures/m1_sqlite_master.tsv` byte-identical; the guard now builds a `0001`-only database, per D3 |

### Two repairs the verification required

**Approval was destroying unimported manual edits silently** (`21906be`). SQLite became
authoritative here and approval rebuilds the Markdown projection from it, so a manual file edit
that had not been imported was overwritten without a word — something v1 never did. Approval now
refuses while the projection disagrees with the stored draft and names `cv sync-draft`.
`validate` deliberately does not refuse: its report on the stored draft is true, and approval is
the trust boundary. A foreign projection copied over a working file consequently cannot reach a
revision at all.

**A plan frozen under a different Profile version was silently reused** (`21906be`). Reusing it
re-derives section assignment from a Profile the plan never saw, so the draft would not be the
plan's decision. Drafting now refuses; §4.3 replaces the refusal with a stale reason.

### Verification gap that was closed, not merely noted

`tests/test_golden.py` proved parity for the *computed* selection path while production had moved
to the *persisted-plan* path. The two could have drifted in section assignment or claim order with
every golden hash still matching. They are now asserted equal across all four cases (`95942b8`).

### Carried forward

- `cv fact attach` requires a re-analysis before a plan can select the new fact;
  `confirm_and_use_fact` (§4.5) is the proper command.
- `selection_plans.selection_policy_version` freezes the manifest's own policy version while the
  knowledge store reports a content hash, so the column cannot be compared against current state.
  §4.3 needs one comparable value before `POLICY_CHANGED` can rely on it.
- Codex committed one documentation change (`2abd23b`) despite `docs/**` being lead-only. Harmless
  and accurate; noted so the ownership rule is not quietly eroded.

