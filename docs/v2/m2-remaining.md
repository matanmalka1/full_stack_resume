# M2 — remaining work

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
- [x] Retire `preparing` and `ready` from the recruitment axis; legacy history becomes migration
      events per `docs/v2/spec/migration-plan.md` §6.2 (`682985d`).
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

**Ready to start.** This boundary is sequential: the journal schema owns the durable record
consumed by file staging, recovery, the lifecycle commands, and finally the contextual
SelectionPlan command. Those packages converge on the Knowledge port/service, repository, and
composition root, so parallel lanes would not have honest exclusive ownership.

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
      steps rather than describing the flow in prose. The implementation is **awaiting user
      verification**, not closed; the command sheet was supplied at handoff.

During E1–E5, do not run the full suite, golden suite, browser suite, or offline lifecycle. A
failure in a focused check is fixed before moving forward. E6 does not run those broad checks
either: it supplies their exact commands for the user to run independently. §4.7 item 5 closes
only after the user reports that every crash window deterministically recovered or explicitly
quarantined and the remaining handoff commands passed.

## F. §4.6 Backup and migration scaffolding

Not started. Scope is the three bullets of the plan §4.6, plus:

- [ ] **A24** — remove the `subprocess` pytest call from `infrastructure/migration.py`.
      This is the only remaining architecture-test allowlist entry.
- [ ] **A28** — `--knowledge-from` bound to an inventory.

## G. §4.7 acceptance

State of the plan's seven §4.7 checkboxes; the criteria themselves live there.

| Plan item | State |
| --- | --- |
| 1 — repositories/UoW under real SQLite | Partial: boundary 1, M1 table set only |
| 2 — immutable entities reject bypasses | Partial: eleven tables covered at boundary 1 |
| 3 — projection/action policy under concurrency | Closed at `fe1e92c`; includes two-connection SQLite snapshot consistency |
| 4 — ETag, idempotency, leases, cancellation, retry, `SOURCE_CHANGED` | Closed at `bfbd64d`; evidence in `m2-operations.md` |
| 5 — journal crash windows | Awaiting user verification; implementation at `9aaa855`, handoff at `707c53d` |
| 6 — backup restore to an openable Workspace | Open, follows F |
| 7 — no M2 code points to live v1 paths | Holds so far; a standing constraint, not a deliverable |

§4.7 item 4 is closed. The remaining acceptance items close with their owning boundaries.

## Dependency order

A → B → C → D are closed. E follows the closed state-policy boundary; F remains required before
anything that touches real data. G closes incrementally rather than as a phase.
