# M2 — remaining work

Status tracker. Updated as boundaries close. Authority for scope remains
`docs/v2-implementation-plan.md` §4.1–§4.7; this file only tracks state.

Closed: **§4.1 schema and repositories** (boundary 1, `4796744`, record in
`docs/v2-m2-schema-and-repositories.md`).

## A. 2a close-out — lead work, no executor

Implementation merged at `a9cc63a`. Verification and the two repairs below are lead work.

- [x] `cv_engine/domain/drafts.py` read. `build_draft` now accepts a frozen selection and
      re-derives section assignment from the Profile rather than recomputing the selection.
- [x] Semantic test changes reviewed across 12 files. The manual-Markdown tests document the
      intended D5 split: `validate` reports on the stored draft, `sync-draft` imports the file.
- [x] **Projection-divergence rule decided and implemented** (`21906be`). Approval refuses while
      the projection disagrees with the stored draft; `validate` does not, because its report on
      the stored draft is true. Approval was destroying unimported manual edits silently.
- [x] **Stale plan context now refused** (`21906be`). Drafting from a SelectionPlan that froze a
      different Profile version is refused instead of silently re-deriving the sectioning.
- [x] Persisted-plan parity guarded (`95942b8`). The plan path and the computed path produce
      identical Markdown, fact IDs, and per-section claim order across all four golden cases —
      previously the parity evidence covered a path production no longer takes.
- [x] One active WorkingDraft asserted at the storage level (`fdb3515`), through raw SQL rather
      than through a repository method.
- [x] `edit_version` conflict refusal verified: a stale write raises `edit version mismatch` and
      leaves the record unchanged.
- [x] `0002` then `0003` verified from a `0001`-only database. The upgraded `job_snapshots` shape
      is identical to a fresh head database.
- [x] Snapshot payload writer verified: payloads at the §6.2 path, SHA-256 matching `source_hash`,
      normalized hash present, payload written before registration.
- [x] Offline CLI on a Workspace created from scratch: ingest → analyze → draft → validate →
      approve → render → ready → reconcile, plus `cv fast`. Both PDFs one page, recruiter
      filename correct, `OPENAI_API_KEY` unset. This also proves the recreation path that the
      disposability decision (D4) depends on.
- [x] Full gate: **164 passed** with `CV_REQUIRE_BROWSER=1`, golden hashes unmoved, allowlist
      still one entry.
- [ ] Write the 2a closure record in `docs/v2-m2-domain-records.md` and remove the lane worktree.
- [ ] Carry forward: `cv fact attach` requires a re-analysis to obtain a plan that can select the
      new fact; `confirm_and_use_fact` (§4.5) is the proper command.
- [ ] Carry forward: `selection_plans.selection_policy_version` freezes the manifest's own policy
      version while the store reports a content hash, so the column cannot be compared to current
      state. §4.3 needs one comparable value before `POLICY_CHANGED` can use it.

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

## H. Carried debt and housekeeping

- [ ] **A3** — default emphasis resolved from the Profile store instead of the hardcoded map.
- [ ] Delete the boundary 1 lane branches `m2-boundary1-persistence` and `m2-boundary1-payloads`.

## Dependency order

A → B → C, with D able to run alongside C because it touches different tables; E after C; F before
anything that touches real data. G closes incrementally rather than as a phase.
