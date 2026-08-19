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
- [ ] v2 submissions bound to a revision and its exact PDF artifact, plus
      `record_external_submission`.
- [ ] Recruitment events with corrections (`corrects_event_id`, mandatory reason) and
      `terminal_outcome`.
- [ ] Retire `preparing` and `ready` from the recruitment axis; legacy history becomes migration
      events per `docs/v2/spec/migration-plan.md` §6.2.
- [ ] Audit records and `export_decision_markdown`.

Stage 7b landed in 2a and does not recur.

## C. §4.3 State and permissions

Not started. Scope is the five bullets of the plan §4.3; none is open to interpretation
here, so they are not restated.

Inherited into this section:

- [ ] The A2 residue — relocating the `_set_ready` / `_record_submission` /
      `record_decision` rules — which §4.3 replaces with the `PreparationState` and
      `ready_qualified` projections rather than moving as-is.
- [ ] The boundary-1 follow-up on private cross-owner reach-ins in the persistence
      package (`docs/v2/records/m2-schema-and-repositories.md`, "Follow-up for boundary 3").

## D. §4.4 Operations — the largest remaining package

Not started. Scope is the six bullets of the plan §4.4. It touches different tables from
§4.3 and can run alongside it.

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
| 3 — projection/action policy under concurrency | Open, follows C |
| 4 — ETag, idempotency, leases, cancellation, retry, `SOURCE_CHANGED` | Open, follows D |
| 5 — journal crash windows | Open, follows E |
| 6 — backup restore to an openable Workspace | Open, follows F |
| 7 — no M2 code points to live v1 paths | Holds so far; a standing constraint, not a deliverable |

No §4.7 checkbox is ticked yet. Boundary 1 deliberately claimed none — see
`docs/v2/records/m2-schema-and-repositories.md`, "§4.7 status".

## Dependency order

A → B → C, with D able to run alongside C because it touches different tables; E after C; F before
anything that touches real data. G closes incrementally rather than as a phase.
