# M2 — remaining work

Status tracker. Updated as boundaries close. Authority for scope remains
`docs/v2-implementation-plan.md` §4.1–§4.7; this file only tracks state.

## Where things are written

One fact, one place. This file is the only record of *state*.

| Question | Answer lives in |
| --- | --- |
| What is done, what remains, what is blocked | **this file** |
| What was decided and why | that boundary's design brief |
| What was found in the code, historically | `docs/v2-architecture-audit.md`, frozen — not updated per boundary |
| Proof that something ran | the boundary's close-out section, the commit, the test run |
| Stages and gates per milestone | `docs/v2-implementation-plan.md`, stable |

Evidence is not copied here. A closed item names its commit and, where one exists, its
close-out section; the numbers live there.

Closed: **§4.1 schema and repositories** (boundary 1, `4796744`, record in
`docs/v2-m2-schema-and-repositories.md`).

## A. 2a — preparation records

**Closed.** Implementation merged at `a9cc63a`; close-out record in
`docs/v2-m2-domain-records.md` §9, which holds the gates and their numbers.

Two repairs the verification required, both fail-closed, both at `21906be`: approval refuses
while the Markdown projection holds unimported edits, and drafting refuses a SelectionPlan frozen
under a different Profile version. Parity for the persisted-plan path guarded at `95942b8`; one
active working draft asserted at storage level at `fdb3515`.

Carried forward:

- [ ] `cv fact attach` requires a re-analysis before a plan can select the new fact.
      `confirm_and_use_fact` (§4.5) is the proper command.
- [x] `selection_plans.selection_policy_version` now freezes the store's content hash rather than
      the declared label, and drafting compares it alongside the profile version, at `c5105b8`.
      §4.3 replaces both refusals with a stale reason.

## B. 2b — remainder of §4.2

- [ ] `ApprovedRevision` owning `revisions/{application_id}/{revision_id}/resume.{json,md}`
      through the payload store.
- [ ] Artifact metadata rows keyed to the revision: HTML, PDF, screenshot, claim manifest,
      provenance export.
- [ ] **A4** — the eight render groups into `domain/render_validation.py` behind a typed
      `RenderEvidence` DTO. Breaks both `monkeypatch.setattr` targets in `tests/conftest.py` and
      the duplicated group-name set there.
- [ ] `ready_qualified` as a computed projection, replacing stored READY.
- [ ] **A2 residue** — the `_set_ready`, `_record_submission`, and `record_decision` rules leave
      the repository.
- [ ] **A5** — typed decision record.
- [ ] v2 submissions bound to a revision and its exact PDF artifact, plus
      `record_external_submission`.
- [ ] Recruitment events with corrections (`corrects_event_id`, mandatory reason) and
      `terminal_outcome`.
- [ ] Retire `preparing` and `ready` from the recruitment axis; legacy history becomes migration
      events per `docs/v2-migration-plan.md` §6.2.
- [ ] Audit records and `export_decision_markdown`.

Stage 7b landed in 2a and does not recur.

## C. §4.3 State and permissions

- [ ] `PreparationState` and `WorkingDraftState` projection.
- [ ] Ready compatibility by JobSnapshot + JobAnalysis.
- [ ] Review, warning, blocker, and stale reason models.
- [ ] Available and blocked actions with reason codes, plus a nullable recommended action.
- [ ] One consistent Application read projection in a single read transaction.

## D. §4.4 Operations — the largest remaining package

- [ ] Operation schema, atomic claiming, resource leases, heartbeat, phases, cancellation, retry,
      idempotency, safe failure metadata, inactive outputs.
- [ ] Internal low-concurrency worker.
- [ ] The same runner as a foreground CLI executor, requiring no FastAPI.
- [ ] Startup interruption of expired queued and running work.
- [ ] Optimistic pre-execution and pre-activation checks with `SOURCE_CHANGED`.
- [ ] One classified automatic transient retry.

## E. §4.5 Knowledge consistency — the highest correctness risk

- [ ] `KnowledgeRepository` validation and atomic writes.
- [ ] The narrow `PREPARED`/`COMMITTED` mutation journal.
- [ ] Enough hashes, paths, mutation identity, and strategy for deterministic recovery.
- [ ] Focused quarantine and reconciliation.
- [ ] Contextual pending fact, confirmation and promotion, attachment, and SelectionPlan flows.
- [ ] **A6** — the confirm/promote mapping and the `--confirm` refusal leave `cli.py` for
      `KnowledgeService`.

## F. §4.6 Backup and migration scaffolding

- [ ] Workspace backup, manifest, hash verification, restore, and open/reconcile paths.
- [ ] v1 inventory and mapping contracts.
- [ ] Migration built against fixtures and copies; no live migration.
- [ ] **A24** — remove the `subprocess` pytest call; this is the only remaining architecture debt
      allowlist entry.
- [ ] **A28** — `--knowledge-from` bound to an inventory.

## G. §4.7 acceptance

- [ ] Repositories and UoW pass real SQLite integration tests — partially covered by boundary 1,
      for the M1 table set only.
- [ ] All immutable entities reject update and delete bypasses — partially covered.
- [ ] Projection and action policy internally consistent under concurrency fixtures.
- [ ] ETag, idempotency, leases, cancellation, retry, and `SOURCE_CHANGED` pass.
- [ ] Journal crash windows recover or quarantine explicitly.
- [ ] Backup restores to an independently openable and reconcilable Workspace.
- [ ] No M2 code points to live v1 paths.

## H. Open audit findings and housekeeping

The register of what was found is `docs/v2-architecture-audit.md`. What is still *open* is here.

- [ ] **A3** — default emphasis resolved from the Profile store instead of the hardcoded map (§4.2/§4.3).
- [ ] **A6** — confirm/promote mapping and the `--confirm` refusal leave `cli.py` (§4.5).
- [ ] **A24** — the `subprocess` pytest call; the only architecture-debt allowlist entry (§4.6).
- [ ] **A28** — `--knowledge-from` bound to an inventory (§4.6).
- [x] Guard sets derived instead of listed (`d37cc13`). Immutability, chain-integrity counts, and
      candidate literals now discover their subject and carry small exception lists, so no list
      grows with a new table or module. Found and fixed a real omission: `artifacts` had no
      immutability triggers since M1, added in migration `0004`.
- [ ] Delete the boundary 1 lane branches `m2-boundary1-persistence` and `m2-boundary1-payloads`.

## Dependency order

A → B → C, with D able to run alongside C because it touches different tables; E after C; F before
anything that touches real data. G closes incrementally rather than as a phase.
