# M2 Boundary 2 — Domain Records (design and execution brief)

Status: **Designed 2026-08-18; not implemented.** Base commit: `856fc7c`.

Scope: `docs/v2-implementation-plan.md` §4.2, plus the inherited items the boundary 1 brief
assigned here: Stage 7b (ValidationRun report schema version and the draft-side group rename),
A5 (typed decision record), A4 (render/Ready policy into the domain behind a typed evidence
DTO), the A2 residue (`_set_ready` / `_record_submission` / `record_decision` rules), and
per-service repository repointing with the rest of A16's port narrowing.

Authority: `docs/v2-product-spec.md` §6 invariants 3–12 and 16–21, §8, §10, §11, §16;
`docs/v2-state-and-use-cases.md` §2–§5, §12–§18; `docs/v2-architecture.md` §6.1, §6.2, §8;
`docs/v2-migration-plan.md` §6.2, §6.3, §6.6, §6.7, §6.9; `docs/v2-execution-protocol.md`.

Predecessor: `docs/v2-m2-schema-and-repositories.md` (boundary 1, closed at `4796744`).

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
record beside the v1 row it replaces would be a dual-write, which `docs/v2-implementation-plan.md`
§11 lists as an unqualified stop condition; leaving the CLI on v1 records while a later API
writes v2 ones would be the second workflow engine `docs/v2-architecture.md` §1 forbids.

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

**D4 — no backfill; the schema change is a clean break.** `0002` defines the final
`job_snapshots` shape with **no** `original_text` column, so the filesystem owns the payload from
this boundary onward and invariant 19 holds immediately. Nothing needs migrating: `.workspace/`
is gitignored, no code or test references it, and the only v2 databases in existence are three
development Workspaces holding one Application each, reproducible with `cv workspace init` plus
`cv fast`. They are treated as disposable and recreated; boundary 1's version gate refuses them
as they stand, which is the correct behaviour. Real v1 data never travels `0001 → 0002` — it
lands once, at cutover, in whatever schema is then current, and writing its snapshot text to
`snapshots/{application_id}/{snapshot_id}.txt` is already `docs/v2-migration-plan.md` §6.3's
requirement on the v1→v2 mapping. Snapshot-payload writing is therefore implemented once, in
`infrastructure/migration.py`, rather than twice.

*Withdrawn during review:* an earlier draft added nullable columns, an explicit
`cv workspace upgrade` backfill with per-row hash verification, and retention of
`original_text` as inert legacy evidence until §4.6 could drop it behind a verified backup. That
apparatus protected only disposable development data, duplicated the §6.3 mapping, and deferred
invariant 19 for a milestone. It was cut.

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

### 3.1 JobSnapshot (migration `0002`)

`0002` rebuilds `job_snapshots` with `payload_path TEXT NOT NULL`, `source_hash TEXT NOT NULL`,
and `normalized_hash TEXT NOT NULL`, and without `original_text`. The rebuild is the standard
SQLite sequence — drop triggers, create the new table, copy rows, drop the old table, rename,
recreate the trigger pair — inside one transaction, and it is correct for an empty table because
no database carrying rows is upgraded (D4).

The payload lives at `snapshots/{application_id}/{snapshot_id}.txt`, byte-exact, with no
line-ending normalisation (`docs/v2-migration-plan.md` §6.3). `source_hash` is the hash over the
exact received representation — today's `content_hash` value — and `normalized_hash` is the
separate dedupe hash `docs/v2-product-spec.md` §8 requires. Writers follow §7.1: write the
payload through `PayloadStore.commit` first, register second, so a failed registration leaves a
reconcilable orphan rather than a dangling row.

Two writers exist and both must produce identical results: the ingest path in the application
layer, and `infrastructure/migration.py`'s v1→v2 mapping, which currently inserts
`original_text` directly and must instead write the payload and record its path and hashes.

### 3.2 SelectionPlan (new immutable table)

`selection_plans`: `id`, `application_id`, `job_analysis_id`, `version_number`, `plan_json`,
`candidate_context_version`, `candidate_context_hash`, `profile_version`,
`selection_policy_version`, `track_emphasis_dependencies_json`, `created_at`, with
`UNIQUE(application_id, version_number)` and a `no_update_` / `no_delete_` trigger pair.

Every successful analysis creates its initial deterministic plan in the same transaction
(`docs/v2-state-and-use-cases.md` §13), so `save_analysis` becomes one atomic
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

## 5. Waves and ownership — 2a

Lead-only for the whole sub-boundary: `tests/conftest.py`, `tests/test_architecture.py`,
`tests/test_candidate.py`, `tests/test_chain_integrity.py`, `tests/test_ready_integrity.py`,
`tests/test_integration.py`, `tests/test_migration.py`, `cv_engine/cli.py`,
`cv_engine/runtime/**`, `cv_engine/application/services/**`, `cv_engine/application/chain.py`,
`cv_engine/application/ready.py`, `cv_engine/infrastructure/artifacts.py`, `docs/**`.

**Wave 0 — lead alone.** Re-point the fingerprint guard at migration `0001` per D3 and add the
head-schema assertion. Register the new-table checklists of §4 as *failing* placeholders where
possible. Add coverage for the current draft-overwrite behaviour so the `edit_version` change
has a before-state to compare against.

**Wave 1 — two lanes.**

- **Lane A — persistence.** Owns `cv_engine/infrastructure/persistence/**` (migration `0002`,
  registration in `schema.py`, the preparation and draft repositories) and
  `tests/test_persistence.py`. Delivers §3.1's columns, §3.2's table, §3.3's table and partial
  unique index, §3.4's columns, all trigger pairs, and the repository methods with typed
  accessors per D2. Does **not** wire services or the CLI.
- **Lane B — domain records.** Owns `cv_engine/domain/models.py`,
  `cv_engine/domain/validation.py`, `tests/test_domain_contracts.py`,
  `tests/test_drafts_validation.py`. Delivers the typed SelectionPlan and WorkingDraft record
  models, the ValidationRun lineage type, and Stage 7b per D7. Touches no persistence and no
  service.

**Wave 2 — lead alone.** Wire the services: atomic analysis-plus-plan, WorkingDraft reads and
writes through the record with `edit_version`, the payload-store snapshot writer in both the
ingest path and `infrastructure/migration.py`'s §6.3 mapping,
`--selection-plan` plus its compatibility
resolver, `cv sync-draft` redefined per D5, and every §4 checklist updated. Then full
verification.

## 6. Verification — 2a

Canonical interpreter `./.venv/bin/python`. Baseline at `856fc7c`: **154 passed**, including the
browser-required gate.

1. `./.venv/bin/python -m pytest -q` and `env CV_REQUIRE_BROWSER=1 ./.venv/bin/python -m pytest -q`,
   with the count delta explained and no test removed.
2. `tests/test_golden.py` — the Markdown and HTML hashes must not move. The WorkingDraft
   becoming a SQLite record changes where the draft is stored, not what it renders; a golden
   difference means the move changed behaviour.
3. Migration `0002` applies to a fresh database and to a `0001`-only database; the checksum,
   ordering, and version-gate behaviour from boundary 1 still holds.
4. Snapshot payloads, proven on both writers: the CLI ingest path and the legacy-migration
   fixture each produce a payload whose SHA-256 matches its recorded `source_hash`, with the
   payload written before the row is registered. A fresh development Workspace is created from
   scratch to confirm the recreation path the disposal decision depends on.
5. `edit_version` concurrency: two saves from the same expected version — the second is refused
   and changes nothing.
6. One active WorkingDraft per Application enforced by the index, proven by a direct SQL insert
   attempt.
7. Offline CLI end to end on a fresh `development` / `copy` Workspace with `OPENAI_API_KEY`
   unset, through Ready, plus `cv fast`.
8. Live v1 data is never opened.

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
`docs/v2-migration-plan.md` §6.2; and `export_decision_markdown`.

## 8. Stop conditions

Stop and report rather than work around: a golden hash moves; a snapshot payload's SHA-256 does
not match its recorded `source_hash`; a record change would require regenerating the frozen
fingerprint fixture; `edit_version` cannot be introduced without changing an existing refusal message or
exception type; a new immutable table cannot be covered by triggers; the architecture allowlist
would need a new entry; a lane needs a file it does not own; or
`infrastructure/migration.py` cannot write snapshot payloads without restructuring beyond the
§6.3 mapping it already owes.
