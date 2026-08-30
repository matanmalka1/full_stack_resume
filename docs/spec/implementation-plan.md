# v2.0 Implementation Plan

Status: **Approved for v2.0 implementation (2026-08-17)**

PostgreSQL/object-storage plan amendment: **2026-08-25**

Product authority: `docs/spec/product-spec.md`

Architecture: `docs/spec/architecture.md`

State/use-cases: `docs/spec/state-and-use-cases.md`

## 1. Delivery rules

The implementation sequence is:

`Review -> Architecture -> Plan -> Implement -> Test -> Verify`

Work occurs on the active v2 branch/worktree against a dedicated PostgreSQL database.
A single developer working sequentially
uses small milestone commits rather than additional feature branches. Parallel lanes
follow `docs/process/execution-protocol.md` and isolate files, database, object-store
namespace, temp output, and ports.

No v2 process opens v1 data, in development or otherwise. Development and Alpha use
isolated project copies and databases.

Repository authority has already handed off to v2. `AGENTS.md` and the approved v2
specifications govern current work; the v1 documents remain frozen evidence.

## 2. M1 — Application foundation

Objective: prove that v1 behavior can run through clean application boundaries before
introducing HTTP or React.

### 3.1 Application paths and configuration

- Add explicit fixed application path/config models.
- Implement config precedence: CLI > environment > project `.env` > project config > defaults.
- Add CandidateContext loader referencing canonical identity/contact facts.
- Remove candidate literals from filename and rendering policy.
- Add version/hash surfaces for CandidateContext and Knowledge dependencies.

### 3.2 Package boundaries

- Introduce domain, application, infrastructure, CLI, API, and runtime boundaries
  incrementally without micro-packaging.
- Move or wrap v1 domain models/validators with no semantic regression.
- Define application command/query DTOs and stable error types.
- Define focused repository ports and UnitOfWork.
- Create the manual composition root.

### 3.3 Services and CLI

- Implement Application, Analysis, Draft, Rendering, and Tracking service seams.
- Move orchestration out of `Engine` into application use-cases.
- Make `Engine` a compatibility façade with no independent business logic.
- Migrate central CLI commands to the services.
- Preserve `cv fast` as an explicit CLI user-approval orchestration over exact validate,
  approve, render, and Ready checks; it may not bypass any blocker.
- Add compatibility resolvers/warnings only where legacy CLI signatures omit an
  explicit v2 source ID.
- Audit whether the v1 CSV export has a real consumer. Retain a versioned v2 CLI export;
  add `--legacy-format` only when that consumer is demonstrated.

M1 completion tightened the temporary compatibility design above: commit `d34cf50`
moved the exact `cv fast` orchestration into `cli.py`, repointed workflow consumers to
the services, and removed `Engine`. `compat.py` retains only the two sanctioned legacy
source-ID resolvers.

### 3.4 M1 acceptance

- [x] Domain/application code imports no FastAPI, SQLAlchemy/psycopg, path layout, or
      provider HTTP.
- [x] CLI completes the deterministic v1 Definition of Done through services.
- [x] Selected facts, claims, validation outcomes, Ready eligibility, and decision
      behavior retain semantic parity with v1.
- [x] Candidate name is not hardcoded in core or renderer policy.
- [x] Normal v2 commands use only the fixed project root; no root selector or v1 reader exists.
- [x] All applicable v1 safety invariants remain covered and the consolidated suite
      passes; retaining every legacy test item is not required.

M1's implementation boundary closed on 2026-08-18 at `67a80d5`. Command evidence and
the exact scope of each criterion are recorded in Git history; the
browser-required suite passed 124 tests in the dedicated v2 environment.

Stable commit boundary: application seam complete and CLI green.

## 3. M2 — Persistence, operations, projections, and recovery

Objective: create the durable v2 foundations required by the API rather than building
them inside endpoints later.

### 4.1 Schema and repositories

- Design the explicit v2 PostgreSQL schema and numbered Alembic revisions.
- Configure foreign keys, transaction boundaries/isolation, row-level claiming, and
  narrow immutable constraints/triggers.
- Implement SQLAlchemy Core repositories by transactional ownership and UnitOfWork;
  do not introduce ORM Sessions or mapped entities.
- Implement a storage-neutral ObjectStore for snapshots, revisions, outputs, provider
  responses, and manifests, with local default and optional S3-compatible adapters.
- Implement UUIDv4 IDs, UTC timestamps, and SHA-256 hashes. Introduce a serialization
  version only with a concrete versioned payload reader and writer.

### 4.2 Domain records

- Add immutable JobSnapshot object-store payloads and PostgreSQL metadata.
- Add immutable JobAnalysis and SelectionPlan versions.
- Add the one mutable WorkingDraft with edit version/content hash.
- Add immutable ValidationRun and ApprovedRevision records.
- Add artifact metadata and readiness qualification without a ReadyRevision entity.
- Add immutable submissions, recruitment events/corrections, current status projection,
  terminal outcome, and next action.
- Add audit records and human-readable provenance data.

### 4.3 State and permissions

- Implement PreparationState and WorkingDraftState projection.
- Implement Ready compatibility by JobSnapshot + JobAnalysis.
- Implement review/warning/blocker/stale reason models.
- Implement all available/blocked actions and nullable recommended action.
- Produce one consistent Application read projection in a single read transaction.

### 4.4 Operations

- Implement Operation schema, atomic claiming, resource leases, heartbeat, phases,
  cancellation, retry, idempotency, safe failure metadata, and inactive outputs.
- Implement the internal low-concurrency worker.
- Implement the same Operation runner as a foreground CLI executor so asynchronous
  commands complete without FastAPI or `cv web`.
- Implement startup interruption of expired queued/running work.
- Implement optimistic pre-execution and pre-activation checks with `SOURCE_CHANGED`.
- Implement one classified automatic transient retry.

### 4.5 Knowledge consistency

- Implement KnowledgeRepository validation and atomic writes.
- Implement the narrow PREPARED/COMMITTED mutation journal.
- Store enough hashes, paths, mutation identity, and strategy for deterministic recovery.
- Implement focused quarantine and reconciliation.
- Implement contextual pending fact, confirmation/promotion, attachment, and
  SelectionPlan flows.

### 4.6 Database lifecycle and storage portability

Superseded on 2026-08-25 with the PostgreSQL/object-storage baseline. The built-in
backup/restore command was retired: PostgreSQL and bucket lifecycle belong to
the configured environment, while this development baseline always starts from an empty
database.

- Apply schema changes explicitly through Alembic with one registered head.
- Prove an empty-database upgrade and foreign-key integrity.
- Keep immutable payload references identical under local and S3-compatible storage.
- Keep the deterministic local workflow operational without cloud configuration or boto3.

### 4.7 M2 acceptance

- [x] Repositories/UoW pass real PostgreSQL integration tests.
- [x] All immutable entities reject update/delete bypasses as required.
- [x] Projection/action policy is internally consistent under concurrency fixtures.
- [x] ETag, idempotency, leases, cancellation, retry, and SOURCE_CHANGED pass.
- [x] Journal crash windows recover or quarantine explicitly.
- [x] Alembic topology and empty-database upgrade checks pass.
- [x] Local and S3-compatible object-store contracts preserve immutable payload identity.
- [x] No M2 code points to live v1 paths.

The final archive-isolation item is met by construction rather than by a check: no code
reads v1 at all. The `looks_legacy` guard that backed it was retired on 2026-08-25 with
the v1 submission data it recognised; see CLAUDE.md.

Per-item commits and evidence are in Git history, which is the record of
state; they are not duplicated here.

Stable commit boundaries may separate schema/repositories, state policy, Operations, and
Knowledge journal when each boundary is green and intentionally scoped.

## 4. M3 — Application API vertical slice

Objective: prove the complete workflow through the Application API before building a
large frontend.

### 5.1 FastAPI foundation

- Add FastAPI and explicit `/api/v1` routers.
- Add separate Pydantic HTTP request/response schemas.
- Add composition dependencies that receive already-built services.
- Add Problem Details mapping and stable application error codes.
- Add OpenAPI generation/validation and generated TypeScript types.
- Add body-size limits, path containment, strict Origin/CORS policy, and artifact
  streaming by ID only.

### 5.2 Vertical-slice commands and queries

- Create Application and immutable JobSnapshot with duplicate warnings.
- Analyze in deterministic and AI modes through Operation.
- Commit one initial deterministic SelectionPlan with every successful JobAnalysis.
- Apply review decisions and create replacement immutable SelectionPlans.
- Run AI `propose_selection_plan` as a `202 + Location` Operation; keep deterministic
  plan creation synchronous.
- Generate/replace WorkingDraft.
- Read/update WorkingDraft with ETag.
- Apply deterministic fact selection changes.
- Run section/claim regeneration Operations.
- Validate exact WorkingDraft.
- Explicitly approve exact validated content.
- Render ApprovedRevision, establish `ready_qualified`, and project Ready when its
  snapshot+analysis match the active context.
- Query Operation progress and complete state/action projection.
- Download the exact Ready PDF.

### 5.3 AI tasks

- Version and implement `propose_job_analysis`.
- Version and implement `propose_selection_plan`.
- Version and implement `draft_resume`.
- Version and implement `regenerate_section`.
- Version and implement `regenerate_claim`.
- Preserve parsed and sanitized raw outputs with complete provenance.
- Add no silent fallback and deterministic continuation as a separate command.

### 5.4 M3 acceptance

- [x] Real FastAPI + worker + PostgreSQL + object-store test completes the API sequence
      Create -> Analyze -> Review if needed -> Draft -> Edit -> Validate -> Approve ->
      Render -> Ready.
- [x] The no-review path receives an initial SelectionPlan from Analyze and can
      auto-generate without another selection command.
- [x] NeedsReview and validation failure are successful outcomes.
- [x] Routers contain no business logic.
- [x] Commands use explicit source IDs; latest appears only in read/query helpers.
- [x] OpenAPI and generated TypeScript types have no drift.
- [x] Security, race, and failure-path tests pass.

Stable commit boundary: API vertical slice and failures green, no Dashboard endpoints
required beyond foundational projections.

## 5. M4 — React vertical slice

Objective: complete the same proven path through a Hebrew local Web UI.

### 6.1 Design pass

- Create low-fidelity wireframes before component implementation.
- Define typography, spacing, restrained color, focus, warning/blocker, and status
  hierarchy.
- Define RTL shell and explicit LTR technical/content islands.
- Validate the editor/preview layout at desktop widths and basic responsive fallback.

### 6.2 Frontend foundation

- Add React/TypeScript/Vite/Tailwind project.
- Add routing, TanStack Query, React Hook Form, generated types, and handwritten client.
- Add production build served by FastAPI and Vite proxy development flow.
- Add operation polling and safe global error handling.
- Add accessible Dialog/Popover primitives only as needed.

### 6.3 Screens

- New Application with duplicate precheck, `.txt` local read, and optional URL.
- Operation Progress.
- Analysis Review only when required, with one Apply Decisions commit.
- Draft Editor with claims/facts/warnings, deterministic changes, regeneration,
  free-text pending state, autosave, and explicit save-conflict dialog.
- Isolated server-rendered HTML Preview.
- Validation Results with blockers and warnings.
- Approval summary/confirmation for the exact validated version.
- Render progress/failure/retry.
- Ready screen with preview, PDF download, validation/provenance, and New Draft.
- Minimal Settings for auto-generation, AI enabled/default execution mode, provider
  configured state, open-browser preference, and basic UI preferences.


## 6. M5 — Tracking

Objective: add recruitment management only after the preparation workflow is stable.

- Implement Dashboard table, search, filters, sorting, badges, active Operation, next
  action/date, and warnings.
- Implement Application Detail header, current preparation, unified timeline,
  revisions/artifacts, submissions, and navigation to editor.
- Implement allowed forward RecruitmentStatus transitions.
- Implement explicit correction events and transactionally consistent status/outcome.
- Implement internal submission with explicit `ready_qualified` revision/PDF IDs,
  including historical-context warnings when active snapshot/analysis moved on.
- Implement external submission without fake revision/artifact.
- Implement multiple append-only submissions.
- Implement next action, date, event history, and computed overdue warning.
- Implement human-readable provenance/decision Markdown export.
- Do not add charts, notifications, Web CSV export, or delete.

M5 acceptance:

- [ ] Tracking never changes preparation state.
- [ ] Drafting after submission never moves recruitment backward.
- [ ] Submission and status/audit commit atomically.
- [ ] Corrections preserve the original event.
- [ ] Closing preserves terminal outcome.
- [ ] Dashboard and Application Detail pass axe and E2E coverage.

Stable commit boundary: v2.0 product scope complete before runtime/release hardening.

## 7. M6 — Runtime, packaging, and release

Objective: make the product locally operable and prove Release Ready without using live
data as a test environment.

### 8.1 Runtime supervisor

- Implement `cv web` and `--no-open`.
- Validate schema and compatibility.
- Implement default port 8765, same-instance health/identity detection, and controlled
  fallback port.
- Start composition, FastAPI, worker, and default browser.
- Implement graceful shutdown and durable interruption behavior.
- Bundle React build so Node is not a runtime requirement.
- Use managed Chromium for PDF rendering and diagnostic-only local Chrome fallback.
- Add Open Logs Folder.

### 8.2 Release hardening

- Run complete Linux/Chromium CI.
- Run macOS runtime, Chrome, WebKit, and rendering verification.
- Run manual OpenAI analysis/draft smoke and record execution metadata.
- Verify performance regression budgets and investigate material regressions.
- Verify Alembic topology, empty-database upgrade, object-store contracts, and the
  configured environment's data-protection policy.
- Run the complete v2 Definition of Done and publish the acceptance report.

### 8.3 Release states

Engineering Complete means all M0-M6 code/document/test work is done.

Release Ready additionally means the acceptance report, database/storage lifecycle, macOS
verification, and manual provider smoke have passed.

There is no cutover event. v2 starts with an empty database and v1 stays a frozen archive
in Git, so Release Ready is the last gate rather than the one before a migration.

## 8. Going live — withdrawn as an event

Withdrawn on 2026-08-19. There is nothing to cut over: v1 is a frozen archive in Git and
v2 starts with an empty database, so going live means creating the next application in
v2 rather than migrating the previous ones into it.

Rollback is running v1 from the archive. It needs no preparation — `git worktree add`
against the frozen commit — and it is not a downgrade of anything, because the two
systems never shared a database. Never downgrade the v2 database.

## 9. Commit and change discipline

- Never write into the v1 archive.
- Keep every commit scoped to one stable boundary.
- Do not combine architecture extraction with unrelated content changes.
- Add targeted regression coverage for every material bug not already caught by an
  existing meaningful test. Prefer strengthening the closest existing scenario over
  creating another test item.
- Do not edit generated HTML/PDF or immutable artifacts by hand.
- Do not add deferred features while implementing a milestone.
- Do not begin M5 before the M4 vertical-slice gate.

## 10. Stop conditions

Stop and request a decision for:

- a semantic change to an approved invariant
- scope expansion
- migration or data-loss risk
- a possible unsupported-claim approval path
- unresolved specification contradiction
- required dual-write
- required auth/cloud/deployment-model change

Do not stop for naming, folder structure, or another implementation detail that can
change without altering contracts or invariants.
