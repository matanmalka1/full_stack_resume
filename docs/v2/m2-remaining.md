# M2 — remaining work

> **Superseded on 2026-08-23.** M2 closed with all seven §4.7 items met. The single
> record of state is now `docs/v2/m3-remaining.md`. This file is M2's closed tracker:
> it keeps its own evidence and is not updated with later state. This banner is the
> only edit it received after close.

Status tracker. Updated as boundaries close. Authority for scope remains
`docs/v2/spec/implementation-plan.md` §4.1–§4.7; this file only tracks state.

## Where things are written

One fact, one place. This file is the only record of *state*.

| Question | Answer lives in |
| --- | --- |
| What is done, what remains, what is blocked | **this file** |
| What was decided and why | that boundary's design brief |
| What was found in the code, historically | `docs/v2/records/architecture-audit.md`, frozen at M1 close |
| Non-milestone cleanup items | `docs/v2/cleanup-todos.md` |
| Proof that something ran | the boundary's close-out section, the commit, the test run |
| Stages and gates per milestone | `docs/v2/spec/implementation-plan.md`, stable |

Evidence is not copied here. A closed item names its commit and, where one exists, its
close-out section; the numbers live there.

Closed: **§4.1 schema and repositories** (boundary 1, `4796744`, record in
`docs/v2/records/m2-schema-and-repositories.md`).

Closed: **§4.5 Knowledge consistency** (`122b957`, record in
`docs/v2/records/m2-knowledge-consistency.md`).

## A. 2a — preparation records

**Closed.** Implementation merged at `a9cc63a`; close-out record in
`docs/v2/records/m2-domain-records.md` §9, which holds the gates and their numbers.

Two repairs the verification required, both fail-closed, both at `21906be`: approval refuses
while the Markdown projection holds unimported edits, and drafting refuses a SelectionPlan frozen
under a different Profile version. Parity for the persisted-plan path guarded at `95942b8`; one
active working draft asserted at storage level at `fdb3515`.

Carried forward (the `cv fact attach` item moved to section E, its §4.5 home):

- [x] `selection_plans.selection_policy_version` now freezes the store's content hash rather than
      the declared label, and drafting compares it alongside the profile version, at `c5105b8`.
      §4.3 replaces both refusals with a stale reason.

## B. 2b — remainder of §4.2

- [x] `ApprovedRevision` owning `revisions/{application_id}/{revision_id}/resume.{json,md}`
      through the payload store (`3f030ad`).
- [x] Artifact metadata rows keyed to the revision: approval artifacts plus rendered HTML, PDF,
      and screenshot (`3f030ad`). Provenance export remains under its open item below.
- [x] Rendered HTML/PDF/screenshot bytes for new writes live at
      `outputs/{application_id}/{revision_id}/{artifact_version_id}.{ext}`; the recruiter PDF
      filename remains presentation metadata (`4c1005b`). Existing immutable payloads were not
      moved, rewritten, or deleted.
- [x] **A4** — the eight render groups and filename/ATS rules live in
      `domain/render_validation.py` behind typed `RenderEvidence`/`RenderGeometry` DTOs; the
      infrastructure adapter only collects evidence, and the test double supplies evidence
      instead of a fabricated passing report (`c02b8bf`).
- [x] `ready_qualified` is a context-independent computed projection over an exact
      ApprovedRevision, its immutable source/render artifacts, approval validation lineage, and
      exact PDF post-render validation; rendering no longer stores READY (`0f9eb94`).
- [x] **A2 residue** — `_set_ready`, `_record_submission`, and `record_decision` left the
      repository. Submission and approval rules now live in application services; persistence
      exposes storage-only inserts (`0f9eb94`).
- [x] **A5** — approval passes a typed `DecisionRecord` into persistence (`0f9eb94`).
- [x] v2 submissions bound to a revision and its exact PDF artifact, plus
      `record_external_submission` (`682985d`).
- [x] Recruitment events with corrections (`corrects_event_id`, mandatory reason) and
      `terminal_outcome` (`682985d`).
- [x] Retire `preparing` and `ready` from the recruitment axis; legacy history became migration
      events per the then-current migration plan, §6.2 (`682985d`). That plan is now
      `docs/v1/migration-plan-superseded.md` and the migration-event carrier is being removed.
- [x] Audit records and `export_decision_markdown` (`682985d`).

Stage 7b landed in 2a and does not recur.

## C. §4.3 State and permissions

**Closed.** Implementation landed at `fe1e92c`. One central policy derives stale/review
reasons, warnings, both state axes, Ready compatibility, milestone visibility, and the
available/blocked/recommended actions from a typed `ProjectionContext`. Application Detail and
list projections use the same policy, with their SQLite inputs read through one transaction and
small repository queries rather than a combined SQL read model. §4.4 now supplies the nullable
`active_operation` value when queued or running work exists.

Inherited checks resolved before this section starts:

- [x] The A2 residue is closed: `_set_ready`, repository `_record_submission`, and
      `record_decision` are gone; submission rules are application-owned and readiness is the
      `ready_qualified` projection (`0f9eb94`, `682985d`).
- [x] The boundary-1 cross-owner follow-up is closed: the unchecked status primitives are gone.
      The sole remaining internal creation primitive hard-codes the valid initial `saved` state
      and its recruitment event, and preparation invokes it through a repository bound to the
      same UnitOfWork, satisfying D7 (`682985d`).

## D. §4.4 Operations — the largest remaining package

**Closed.** The durable runner foundation landed at `7400870`, analyze/draft/render CLI
integration at `d0e54f1`, and recovery plus the completed Class C gate at `bfbd64d`. The frozen
close-out record is `docs/v2/records/m2-operations.md`.

- [x] Operation schema, atomic claims, bounded resource leases, heartbeat, phases,
      cancellation, manual retry, safe failure metadata, and inactive outputs.
- [x] Idempotent Operation creation and idempotent approval with a durable reserved revision ID.
- [x] Low-concurrency worker and the shared foreground CLI executor.
- [x] Startup interruption for expired queued/running work and graceful cancellation on shutdown.
- [x] Optimistic pre-execution and pre-activation checks with `SOURCE_CHANGED`.
- [x] One classified automatic retry for transient provider/browser failures.
- [x] The Class C closing gate passed against an isolated test Workspace; no live v1 path was
      opened.

## E. §4.5 Knowledge consistency — the highest correctness risk

**Closed.** The durable journal landed at `e30b2f4`, validated file staging at `c77ea44`,
the coordinator and lifecycle commands at `9aaa855`, and removal of direct runtime writers at
`707c53d`. The verification handoff was finalized at `122b957`; the frozen close-out record is
`docs/v2/records/m2-knowledge-consistency.md`.

Execution packages:

- [x] **E1 — durable journal and repository contract** (`e30b2f4`). Add the next additive migration for the
      Knowledge mutation journal and focused quarantine state. Persist mutation identity,
      strategy, source/staged paths, old/new hashes, SQLite mutation identity, state, and
      timestamps. Add typed repository/UoW operations for `PREPARED -> COMMITTED` and quarantine,
      with constraints that reject illegal transitions and mutation-identity reuse. Prove only
      the migration and repository contract with focused real-SQLite tests.
- [x] **E2 — validated filesystem mutation preparation** (`c77ea44`). Replace direct Knowledge rewrites with
      a repository adapter that can build and validate the complete proposed Knowledge document,
      stage it under the isolated Workspace, hash old/new bytes, atomically replace the source,
      and restore only when hashes prove the action is safe. Keep path/layout knowledge out of the
      application layer. Prove validation, containment, atomic replace, and hash refusal with the
      focused Knowledge adapter tests.
- [x] **E3 — journal coordinator, recovery, and quarantine** (`9aaa855`). Implement the six-step protocol from
      `architecture.md` §7.2, startup recovery before normal services are exposed, and explicit
      reconciliation. Recovery must finish, restore, or quarantine from durable hashes and DB
      identities; it must never infer a missing fact. Normal queries expose only committed state.
      Focused quarantine blocks further promotions and approvals that depend on unreconciled
      Knowledge while history/export/tracking remain readable. Cover the eight failure windows in
      one parameterized focused matrix; do not run a broad suite here.
- [x] **E4 — route the existing lifecycle through the journal** (`9aaa855`). Move create-pending, claim
      capture, `pending -> confirmed`, `confirmed -> canonical`, and Profile attachment onto the
      coordinator, with one immutable audit event per transition. Move the confirm/promote mapping
      and the `--confirm` refusal from `cli.py` into `KnowledgeService` (**A6**), leaving the CLI as
      argument parsing/output only. Preserve the CLI-only canonical-correction rule: correction
      creates a replacement fact and never edits an old canonical fact. Run only the closest fact
      lifecycle and CLI refusal tests.
- [x] **E5 — contextual fact and SelectionPlan commands** (`9aaa855`). Implement `create_pending_fact` with a
      generated UUIDv4 identity, `create_fact_from_claim` with exact claim text and explicit
      metadata, and `confirm_and_use_fact` as one logical journaled command:
      `pending -> confirmed -> canonical -> Profile attachment -> immutable SelectionPlan`.
      Validate the entire command before mutation, record every lifecycle transition separately,
      use explicit Application/analysis/Profile/section inputs, and report the whole command as
      failed if it cannot complete. Plain `cv fact attach` remains a Knowledge-only mutation and
      therefore requires re-analysis before an ordinary plan can select the fact; the contextual
      command is the atomic path carried from 2a. Prove the happy path and constraint-failure
      rollback with focused service tests.
- [x] **E6 — boundary integration and verification handoff** (`707c53d`). Removed superseded direct-write
      paths, prove by inspection that all Knowledge writers enter through the journal, and wire
      reconciliation into `cv reconcile`. Inspect the final diff and test-count baseline, but do
      not run the broad closing gate. Instead, finish with a copy-paste-ready command sheet for the
      user covering: the non-browser suite; golden hashes; architecture test; deterministic
      offline CLI lifecycle in a fresh isolated `development`/`copy` Workspace with
      `OPENAI_API_KEY` unset; browser-complete suite; and a fresh `0001`-only database upgrading
      cleanly to head. The sheet must include all setup, fixture/input, Workspace, and explicit-ID
      steps rather than describing the flow in prose. The user ran the complete sheet successfully;
      the results and test-count reconciliation are frozen in the close-out record.

During E1–E5, only focused checks ran. At E6 the user independently ran the broad closing gate,
including the parameterized crash-window coverage, isolated offline lifecycle, browser suite,
and migration-to-head checks. Every gate passed, closing §4.7 item 5.

## F. §4.6 Workspace backup and restore — closed

Rescoped on 2026-08-19. v1 is a frozen archive and there will be no migration into v2,
so two of §4.6's three parts have no subject left. What remains protects v2's own data —
approved revisions, submitted artifacts, job snapshots of postings that later vanish —
which is forward-looking, not historical.

- [x] **Backup and restore.** `cv workspace backup --into` and
      `cv workspace restore --from --into`, in `runtime/backup.py`. The database goes
      through the SQLite backup API in `persistence/connection.py`, because the Workspace
      runs in WAL mode and a file copy can miss committed writes still in the log. `tmp`
      and `logs` are excluded. Neither command will write into a non-empty directory, and
      a backup may not be written inside its own Workspace. No separate manifest: the
      artifact hashes are already in `artifact_versions`, and a second hash list beside
      them can only drift.
- [x] **A28 rescoped** — the marker records `knowledge_source` and
      `knowledge_source_hash`, and an incomplete source is refused before the marker is
      written. Binding it to a verified v1 inventory answered a question that no longer
      exists: the copy runs only at `workspace init` into a fresh Workspace, over
      regenerable seed knowledge, so a wrong source costs one `workspace init`. What was
      worth keeping is being able to tell later which source a Workspace came from.

Dropped with the migration: the v1 inventory and mapping, the fixture-based migration
engine and its `source = migrated + explicitly_excluded, unexplained = 0` invariant.

- [x] **A24** — closed by deleting `infrastructure/migration.py`; the architecture debt
      allowlist and the persistence-offender set are both empty.

## G. §4.7 acceptance

State of the plan's seven §4.7 checkboxes; the criteria themselves live there.

| Plan item | State |
| --- | --- |
| 1 — repositories/UoW under real SQLite | Closed at H2: the eight uncovered Operations methods now tested directly; `latest_validation` was dead and removed |
| 2 — immutable entities reject bypasses | Closed at H1: every immutable table proven to refuse UPDATE and DELETE, derived from `PRAGMA table_info` |
| 3 — projection/action policy under concurrency | Closed at `fe1e92c`; includes two-connection SQLite snapshot consistency |
| 4 — ETag, idempotency, leases, cancellation, retry, `SOURCE_CHANGED` | Closed at `bfbd64d`; evidence in `m2-operations.md` |
| 5 — journal crash windows | Closed at `122b957`; evidence in `m2-knowledge-consistency.md` |
| 6 — backup restore to an openable Workspace | Closed: `restore_workspace` returns a Workspace loaded through the normal fail-closed path, so an archive that restored to something unopenable fails at restore |
| 7 — no M2 code points to live v1 paths | Closed by construction: no code reads v1 at all. The `looks_legacy` guard stays so no v2 command can open or mark the archive |

All seven are closed. Items 1 and 2 closed together as section H.

### H. Items 1 and 2 — closed

Both are partial for the same reason: they were written against the M1 table set and
never grew with it. The schema now has 24 tables and 40 triggers; the guards cover
eleven. Every boundary since added tables — operations, approved revisions, the
knowledge journal, tracking — and each one had to remember to extend a hand-kept list.
Nothing failed when one did not.

- [x] **H1 — immutable entities (item 2).** Closed. The inversion this item asked for
      already existed: `test_every_product_table_is_immutable_unless_explicitly_exempt`
      discovers the tables and assumes immutability, so `MUTABLE_TABLES` is the only way
      out. That test was never the gap.

      The gap was the behavioural half, which named four tables by hand. A trigger only
      runs when there is a row, so eleven of the fifteen immutable tables were guarded on
      paper and unproven in fact — exactly the count recorded as partial.

      `test_every_immutable_table_refuses_update_and_delete` now derives a probe row from
      `PRAGMA table_info` for every immutable table, inside a savepoint that always rolls
      back. Foreign keys and CHECK constraints are suspended: the row only has to exist
      long enough to be refused, and satisfying every constraint would mean rebuilding the
      schema's rules inside the test. The repository-backed test is kept rather than
      replaced, because it proves the same triggers bite with those constraints on, over
      rows the product itself wrote.

      Checked by breaking it. Deleting `no_update_job_analyses` from the baseline failed
      both tests with different messages — the structural one reporting a missing trigger
      and its orphaned counterpart, the behavioural one reporting `job_analyses: update
      was allowed on an immutable table`. The second is the evidence the first cannot
      give.
- [x] **H2 — repositories and UnitOfWork (item 1).** Closed.

      "Tables no test names" turned out to be the wrong measure — a table can be well
      covered through a service without a test ever naming it. Measured by method instead:
      of 85 public repository methods, 24 are never called by name in a test. Most of
      those 24 are exercised through the services that call them, which is real coverage,
      just indirect.

      Eight were not, and they are the ones that mattered:
      `claim_next_operation`, `set_operation_phase`, `record_operation_attempt`,
      `record_operation_output`, `activate_operation_output`, `complete_operation`,
      `fail_operation`, `complete_idempotency_receipt`. Their refusals are branches a
      successful run never takes — a lease held by another runner, an output activated
      after cancellation, a receipt completed twice with a different result. Now covered
      directly against real SQLite, with the five lease-owning methods parameterised over
      one shared contract so a sixth is one line rather than a sixth test.

      One method was dead: `latest_validation` had no caller anywhere and was not even
      declared in `ports/`, which declares only the different
      `latest_validation_for_working_draft`. Removed rather than covered.

      Not done, and deliberately: a derived guard that fails when a repository method has
      no coverage. Deriving "covered indirectly" needs real coverage data, which means
      adding `pytest-cov`. That is a dependency decision under the `CLAUDE.md` baseline
      rule, not a test change, so it is left for the user rather than assumed.

      A fourth, `status_history`, was found dead while closing H1 and dropped on the
      user's decision. `recruitment_events` had replaced it — same transitions plus actor,
      client, installation, corrections, and terminal outcome — and its only two
      references were one-time backfills in the old `0006` that built the replacement from
      it. It survived into the squashed baseline only because the squash preserved the
      final schema faithfully, v1 leftovers included.

      Two things it cost, both worth carrying into the next dead-code search. It looked
      referenced because `tests/test_database.py` had a test *named*
      `test_status_history_and_transition_contract` whose body queried
      `recruitment_events`: the body had moved and the name had not. A
      `\bstatus_history\b` grep matches that name, because `_` is a word character, so the
      search that found the table reported it as referenced. And dropping it removed
      `sqlite_sequence` too — `status_history` held the schema's only `AUTOINCREMENT`, so
      SQLite stopped creating its bookkeeping table and a `MUTABLE_TABLES` entry went with
      it.

This is the last irreversibility guard in the product: immutable records are the one
thing `CLAUDE.md` still names as not regenerable. Everything else outstanding is
cleanup, and lives in `cleanup-todos.md`.

## Dependency order

A through H are closed. §4.7 has no open acceptance item left; what remains for M2 is
whatever the milestone gate itself asks for, not this record.

## Retiring v1

Recorded here because it changes what several boundaries mean. On 2026-08-19 the user
reviewed what v1 holds — 22 applications, all `draft`, none sent, no source URLs, every
payload already tracked in Git — and decided it is a frozen archive, not data to migrate.
v2 starts with an empty database. The reasoning that was retired is preserved in
`docs/v1/migration-plan-superseded.md`.

- [x] Delete `infrastructure/migration.py`, `infrastructure/legacy_source.py`,
      `tests/test_migration.py`, the migration fixtures, and the `migrate` and
      `inventory-legacy` CLI commands. Both architecture allowlists emptied.
- [x] Squash migrations `0001`–`0010` into one baseline (873 -> 668 lines), dropping
      `migration_runs`, the `legacy_*` recruitment-event columns,
      `insert_legacy_recruitment_event`, `actor_type = 'migration'`, and
      `MIGRATED_HISTORICAL`. Safe only while no v2 database exists, which was checked
      before and after. The baseline was generated by applying the real chain to a
      throwaway database and reading back `sqlite_master`, then proved equivalent by
      diffing normalized schemas built from each; the only differences were the
      deliberate omissions. The `0001`-only upgrade-to-head gate went with it: with one
      migration, `0001` is head and the gate proves nothing.
- [x] The frozen schema fingerprint moved, deliberately. `tests/fixtures/m1_sqlite_master.tsv`
      is now `schema_sqlite_master.tsv`, regenerated by reading `sqlite_master` back from the
      squashed baseline: 3 entries gone (`migration_runs` and its two triggers), 40 added
      from the merged 0002-0010, nothing else. That is an independent check of the squash's
      equivalence claim. `docs/v2/records/m2-domain-records.md` says regenerating the fixture
      "remains forbidden" and `m2-approved-revisions.md` records it byte-identical; both are
      frozen records of what was true at their boundary and are left unedited. This line is
      the override. The guard itself is kept: it no longer proves compatibility with an
      earlier baseline, but it still catches a schema change nobody meant to make.
- [x] Removed `MIGRATED_HISTORICAL` from the §8 example warnings in
      `docs/v2/spec/state-and-use-cases.md`. It named a code path deleted with the
      migration. Only the example list changed; the warning taxonomy above it is
      normative and untouched.

      Noted while checking: `FACT_KNOWN_INCORRECT` in that same list also has no
      implementation. It is not stale — §8 describes it normatively as materially
      stronger than supersession, so it is unbuilt scope rather than a leftover. Left
      alone.
- [x] Reconciled the approved specifications with the decision. Retiring v1 in code left
      four specs describing work that will never happen, which is worse than the code
      being wrong: a specification is what the next reader trusts.

      `implementation-plan.md`: §4.6 rescoped to backup and restore, §4.7 ticked with the
      evidence pointing at this file, §9 "Live cutover event" withdrawn, M6 retitled, and
      the M1 criterion annotated where it accepted an adapter since deleted.
      `product-spec.md`: §20 rewritten — `Cutover Complete` and `Live` are no longer
      states — the v1-migration Definition-of-Done item removed, and
      `actor_type` corrected to `user | system`.
      `test-and-acceptance-plan.md`: §14 "Migration acceptance" withdrawn, keeping the one
      rule that was never about migration — a file is not evidence of a decision; §13
      loses the manifest step; §2.8 renamed to backup tests.
      `architecture.md`: the read-only v1 source adapter removed as the sole guard
      exception, and the `Engine` façade described as gone rather than temporary.

      `actor_type` was the sharpest of these: the spec still listed `migration` as a valid
      audit actor after the code had dropped it, so the two disagreed on a stored value's
      permitted range.

- [x] Collapsed Class C in `CLAUDE.md`. Class C was "schema, artifact paths, or v1 data",
      gated on the browser suite, a `0001`-only upgrade to head, and the migration-safety
      rules. It is now "schema or artifact paths", gated on the browser suite and the
      frozen schema fingerprint.

      The **Migration safety** section is gone: six rules replaced by three under
      **Immutable records**. Of the six, four had no subject left once there was no
      migration (snapshot-before-migrate, rehearse-on-a-copy, stop-on-check-failure,
      preserve-meaning-not-architecture). Two survive because they were never really
      about migration: written records are immutable, and a field that cannot be derived
      stays NULL.

      This is the counterweight `CLAUDE.md` asks for at a boundary close. None of the six
      ever fired. What carries the weight now is derived rather than declared: the frozen
      schema fingerprint catches an unintended schema change, `looks_legacy` refuses to
      open or mark the archive, and backup is a command that can be restored and opened
      rather than a checklist someone confirms.

      Also recorded there: agents do not run tests. The user runs them, and a boundary
      closes by handing over the ordered commands with what each proves.
