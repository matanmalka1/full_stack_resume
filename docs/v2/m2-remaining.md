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

**Implementation complete; closure gates pending.** The durable runner foundation landed at
`7400870`, and analyze/draft/render CLI integration landed at `d0e54f1`. The final boundary diff
adds approval receipts and crash recovery, structured technical failure logging, graceful worker
cancellation, provider-failure classification, CLI operation inspection/cancel/retry, and routes
`cv fast` through the same foreground runner.

- [x] Operation schema, atomic claims, bounded resource leases, heartbeat, phases,
      cancellation, manual retry, safe failure metadata, and inactive outputs.
- [x] Idempotent Operation creation and idempotent approval with a durable reserved revision ID.
- [x] Low-concurrency worker and the shared foreground CLI executor.
- [x] Startup interruption for expired queued/running work and graceful cancellation on shutdown.
- [x] Optimistic pre-execution and pre-activation checks with `SOURCE_CHANGED`.
- [x] One classified automatic retry for transient provider/browser failures.
- [ ] Run the Class C closing gate, record its exact results, then commit and mark this boundary
      Closed. No live v1 path is permitted in the rehearsal.

## E. §4.5 Knowledge consistency — the highest correctness risk

Not started. Scope is the five bullets of the plan §4.5, plus:

- [ ] **A6** — the confirm/promote mapping and the `--confirm` refusal leave `cli.py` for
      `KnowledgeService`.
- [ ] `cv fact attach` requires a re-analysis before a plan can select the new fact;
      `confirm_and_use_fact` is the proper command (carried from 2a).

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
| 4 — ETag, idempotency, leases, cancellation, retry, `SOURCE_CHANGED` | Implementation complete; awaiting D's final Class C gate |
| 5 — journal crash windows | Open, follows E |
| 6 — backup restore to an openable Workspace | Open, follows F |
| 7 — no M2 code points to live v1 paths | Holds so far; a standing constraint, not a deliverable |

No §4.7 checkbox is ticked yet. Boundary 1 deliberately claimed none — see
`docs/v2/records/m2-schema-and-repositories.md`, "§4.7 status".

## Dependency order

A → B → C are closed. D awaits its final gate; E follows the closed state-policy boundary; F
remains required before anything that touches real data. G closes incrementally rather than as a
phase.
