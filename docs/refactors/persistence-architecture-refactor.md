> This document is the source of truth for the persistence refactor. Do not redesign the architecture during implementation unless a concrete contradiction is found. If one is found, document it before changing direction.

# Persistence architecture refactor execution contract

## Current status

```text
Current phase: Phase 8 — Projections and test migration (NOT STARTED)
Last completed phase: Phase 7 — Worker and handlers
Next action: start Phase 8 in a new session
Known blockers: None; approval replay correction authorized (Decision Log below)
Last verified boundary: combined Phase 6+7 — all required gates passed; implementation commit pending
```

## 1. Final goal

The finished system has no root `Repository`, concrete repository inheritance, nested
repositories, `bind()`, repository casts, generic `shared` dependency dictionary, or generic
persistence container. Repositories follow cohesive persistence capabilities and use-case
transaction ownership rather than tables. Application Ports follow real consumer, lifecycle, or
trust boundaries. The application layer owns transaction boundaries, and no database transaction
is held open across AI, network, browser, filesystem, or object-store I/O.

Use-case reads are explicit minimal projections (`DraftContext`, `RenderContext`,
`SubmissionContext`, and operation-specific source projections). There is no general DTO carrying
"all workflow state" and no `WorkflowContextReader` that grows without a consumer boundary.

The initial transaction API is an auto-committing context manager:

```python
with transactions.write() as tx:
    ...
```

Normal exit commits exactly once; exceptional exit rolls back. This is simpler than a callback
while preserving the required invariants. The choice is not syntactic: it remains valid only while
closed-token detection, cross-manager rejection, nested-transaction refusal, and external-I/O
guards are enforced. A contradiction must be logged before changing this API.

## 2. Mandatory invariants

### Repositories

- A concrete repository does not inherit another concrete repository.
- A repository does not hold another repository.
- A repository does not call another repository.
- There is no root repository or repository bundle.
- A repository does not hold a bound mutable connection.
- A repository does not open, commit, or roll back a transaction.
- Repository methods that access the database require an active transaction token.
- Writes require a write transaction; a read transaction cannot satisfy them.

### Transactions

- Nested transactions are forbidden in one execution context.
- A transaction is closed after its scope exits.
- A transaction from another manager or engine is rejected.
- An exception rolls the transaction back.
- Successful scope exit commits exactly once.
- Handlers, activators, and repositories do not open transactions.
- Only allowlisted entry-point orchestrators may receive a transaction manager.

### External effects

- No AI, network, browser, filesystem write, or object-store write occurs inside a database
  transaction.
- An immutable payload is written and verified before database registration.
- External success followed by database rollback is allowed only as a reconcilable orphan.
- Working projections are derived and non-authoritative.
- Render payload metadata is registered only after every payload in the render exists.
- Knowledge mutation preserves its prepare, activate, recover, restore, and quarantine semantics.
- Database metadata is read and its transaction closed before object-store streaming or
  verification begins.

### Ports and services

- A service does not receive a concrete repository.
- There is no `cast()` between persistence capabilities.
- There is no generic dependency, repository, or workflow-state container.
- A new Port requires a real consumer, lifecycle, or trust boundary.
- A one-method Port requires a clear atomic persistence or external-system boundary.
- A commit gateway accepts prepared immutable data, performs no business decision, calls no
  external service, opens no transaction, and represents atomic fan-in that should not be split at
  its caller.
- A use-case projection has a minimal DTO; unrelated projections are split by consumer boundary.
- A service with more than seven constructor dependencies requires an explicit architecture review.

## 3. Non-goals

- No repository-per-table design.
- No compatibility layer for the old root `Repository`.
- No UnitOfWork that exposes repositories or becomes a service locator.
- No Port for every small reader or writer.
- No class-per-command design.
- No complex data migration merely to preserve the current database.
- No long-lived coexistence of the old and new persistence architectures.
- No generic `WorkflowContext` containing all persisted workflow state.
- No `*Committer` introduced merely to shorten a constructor or hide two or three repository calls.

The database and its current data are disposable. Schema and fixture reset are allowed when they
make the target design clearer.

## 4. Target architecture

### Application services

- `ApplicationService`: duplicate check, intake, job snapshot replacement, and notes.
- `AnalysisService`: analysis preparation/activation and selection-plan lifecycle.
- `DraftAuthoringService`: generation, editing, selection change, and regeneration over one
  optimistic WorkingDraft lifecycle; pure helpers remain functions/components.
- `DraftValidationService`: explicit validation command and recorded validation evidence.
- `DraftApprovalService`: approval preparation and idempotent atomic approval commit.
- `DraftHistoryService`: archive/keep and decision export.
- `RenderingService`: render preparation, external execution, payload ingestion, evidence
  registration, and activation.
- `RecruitmentService`: status, correction, deletion, close, and next action.
- `SubmissionService`: internal/external submission and optional applied transition.
- `KnowledgeQueryService`, `FactLifecycleService`, and `KnowledgeRecoveryService`.
- `OperationSubmissionService`: freeze sources and enqueue operations.
- `OperationLifecycleService`: get, cancel, and retry.
- `DraftReplacementService`: replacement reservation, keep/archive, and enqueue protocol.
- `ApplicationQueryService` and `MaintenanceService`.

### Application Ports

The expected stable persistence Ports are:

| Port | Scope |
| --- | --- |
| `TransactionManager` | read/write transaction scopes only |
| `IntakeApplicationStore` | intake-owned application identity and mutable notes |
| `JobSnapshotStore` | snapshot identity, versions, duplicate input projection |
| `AnalysisPlanStore` | analyses and selection plans, including their atomic initial insert |
| `DraftLifecycleStore` | WorkingDraft, ApprovedRevision, lifecycle events, generation record |
| `ArtifactCatalog` | artifact/version registration and lookup |
| `ValidationStore` | validation runs, reports, lineage, artifact/draft bindings |
| `DecisionStore` | approval decisions and decision lookups |
| `RecruitmentStore` | recruitment events, current projection updates, submissions |
| `AuditLog` | application audit append/history |
| `KnowledgeLifecycleStore` | fact events and durable mutation journal |
| `OperationClientStore` | enqueue, client-visible lookup, cancellation, retry inputs |
| `OperationExecutionStore` | claiming, leases, phases, attempts, outputs, completion/failure |
| `IdempotencyStore` | reservation, lookup, completion |
| `SettingsStore` | safe application settings |
| consumer-specific context readers | minimal Draft/Render/Submission/Operation source DTOs |
| `ApplicationProjectionReader` | API/query read models |
| `MaintenanceInspection` | cross-table integrity and artifact inventory |

Do not mechanically split read and write Ports when the consumer/lifecycle boundary is the same.
`SqlAlchemyOperationRepository` is expected to structurally implement two Ports because client
operations and worker execution have materially different trust surfaces.

### Concrete repositories

- `SqlAlchemyApplicationStore`
- `SqlAlchemyJobSnapshotStore`
- `SqlAlchemyAnalysisPlanRepository`
- `SqlAlchemyDraftLifecycleRepository`
- `SqlAlchemyArtifactCatalog`
- `SqlAlchemyValidationRepository`
- `SqlAlchemyDecisionRepository`
- `SqlAlchemyRecruitmentRepository`
- `SqlAlchemyAuditLog`
- `SqlAlchemyKnowledgeLifecycleRepository`
- `SqlAlchemyOperationRepository`
- `SqlAlchemyIdempotencyRepository`
- `SqlAlchemySettingsRepository`
- consumer-specific SQLAlchemy context/projection readers
- `SqlAlchemyMaintenanceInspection`

Each is independent and stateless with respect to transaction lifetime. Infrastructure may use a
private transaction-to-connection resolver; no repository stores the resolved connection.

### Transaction abstraction

`TransactionManager.read()` and `.write()` return auto-closing context managers. Transactions are
opaque application-layer tokens. SQLAlchemy repositories resolve a token through a private helper
that validates token type, active state, manager identity, and engine identity.

A `ContextVar` records the active transaction scope. Starting a second scope while one is active
fails. The same guard is exposed to outbound adapters as `assert_external_io_allowed()`; affected
AI, renderer, filesystem-writing, and object-store entry points must call it before side effects.

### Workflow context projections

There is no general reader. Add a reader only for an actual consumer projection, for example:

- `DraftContextReader.load_draft_context(...) -> DraftContext`
- `RenderContextReader.load_render_context(...) -> RenderContext`
- `SubmissionContextReader.load_submission_context(...) -> SubmissionContext`
- operation-source readers whose DTO is specific to the operation type or closely related group

Each DTO contains only fields consumed by that use-case. If one reader accumulates unrelated
methods, split it by consumer.

### Commit gateways

Initially approved gateways:

- `ApprovalCommitter`: approved revision, artifact registrations, decision, draft deactivation,
  audit, and idempotency completion.
- `SubmissionCommitter`: only if implementation confirms that submission, optional status
  transition, and audit are one atomic fan-in that cannot remain clear at the service call site.

No other gateway is pre-approved. A new gateway requires evidence in the Decision Log.

### Operation runner and handlers

The runner owns activation transactions. Handlers receive an active transaction in
`verify_sources(tx, operation)` and `activate(tx, operation, prepared)`. Handlers and activation
components cannot receive `TransactionManager`. Each handler receives only its source projection
reader and activator. AI/render execution occurs outside all database transaction scopes.

### Composition root

The composition root constructs one engine, one transaction manager, independent concrete
repositories/readers, explicit service constructors, handlers, runner, and worker. `Services`
contains application services and required outbound stores only. It exposes no repository,
transaction manager, or persistence bundle to the API.

### Test architecture

- Repository contract tests request individual concrete repository fixtures and a transaction
  manager fixture.
- Application tests substitute narrow Ports only when a fake materially improves the test.
- Scenario fixtures carry IDs/results and application services, not a persistence root.
- Persistence assertions request the relevant repository fixture and open a read scope.
- Intentional corruption uses an explicit raw-database fixture limited to integrity tests.
- Architecture tests derive forbidden inheritance, imports, casts, old consumers, and transaction
  ownership from the code rather than a hand-maintained inclusion list.

## 5. Migration map

| Old | New |
| --- | --- |
| `Repository` | removed |
| `SqlAlchemyRepositoryBase` connection/bind behavior | stateless connection resolver using transaction tokens |
| `SqlAlchemyUnitOfWork` | `SqlAlchemyTransactionManager` + read/write transaction scopes |
| old `ApplicationStore` | `IntakeApplicationStore` plus lifecycle-specific stores and query projections |
| `JobStore` | `JobSnapshotStore` + `AnalysisPlanStore` |
| `PreparationRepository` | `ApplicationStore` + `JobSnapshotStore` + `AnalysisPlanStore` + `AuditLog` at the service boundary |
| `SqlAlchemyPreparationRepository.create_application` | `ApplicationService` transaction over application, snapshot, and initial recruitment event |
| nested `SqlAlchemyPreparationRepository.applications` | removed; one application owner |
| `DraftRepository` | `DraftLifecycleStore` + `ArtifactCatalog` + `ValidationStore` + `DecisionStore` |
| `ReadinessRepository` | minimal ready/render/submission context projections and evidence readers |
| `TrackingRepository` | `RecruitmentStore` + readiness projection + `AuditLog` |
| `ArtifactRegistry` | `ArtifactCatalog` + `ValidationStore` + `DecisionStore`; generation records move to draft lifecycle |
| `FactAudit` + `KnowledgeMutationRepository` | `KnowledgeLifecycleStore` |
| `OperationRepository` | `OperationClientStore` + `OperationExecutionStore` + `IdempotencyStore` |
| `OperationRunnerRepository` | explicit runner dependencies + transaction manager |
| `QueryRepository` | consumer-specific context readers + `ApplicationProjectionReader` |
| `ApplicationRepository` | removed |
| `ServiceBase` | explicit collaborators and small knowledge/provider/payload components |
| `DraftService` multiple-inheritance façade | four cohesive draft service surfaces and internal pure/components |
| `OperationService` | submission + lifecycle + replacement; approval moves to draft approval |
| `shared` | explicit constructor arguments |
| working Markdown/manifest authority | derived, regenerable projection; validation input produced in memory |

## 6. Delete list

The following must be gone at completion:

- `cv_engine/infrastructure/persistence/repository.py`
- root `Repository`
- old composed repository Ports
- `bind()` and `sqlalchemy_unit_of_work()`
- old UnitOfWork if no remaining consumer justifies it
- `shared`
- `Services.repository`
- repository casts
- nested `self.applications`
- compatibility adapters/layers
- dead helpers and old imports
- `ServiceBase` if no real responsibility remains after migration
- test fixtures/helpers exposing a root repository

## 7. Phases

## Phase 1 — Transaction foundation

Status: DONE

### Goal

Introduce the final transaction token/scope model and its enforcement without changing product
semantics.

### Must preserve

- PostgreSQL `REPEATABLE READ` behavior.
- One process-wide engine per database URL.
- rollback on failure and connection closure.
- existing concurrency and row-lock behavior.

### Implement

- Application transaction Ports.
- SQLAlchemy read/write transaction manager.
- active/closed, manager, and engine validation.
- nested transaction refusal.
- external-I/O guard primitive.
- focused transaction and architecture tests.

### Migrate

- No product service in this phase; Application Intake is Phase 2.

### Delete

- Nothing still consumed by the old architecture.

### Verification

- [x] focused tests
- [x] typecheck
- [x] architecture checks
- [x] no forbidden imports
- [x] no old consumers remain for the new transaction API
- [x] commit-on-success, rollback-on-exception, close detection, foreign-manager rejection
- [x] nested transaction refusal
- [x] external-I/O guard coverage

### Handoff notes

Implementation is present in `application/transactions.py`, `ports/transactions.py`, and
`infrastructure/persistence/connection.py`. Focused coverage is in `tests/test_transactions.py`.
The new scope is context-managed, auto-commits on successful write exit, rolls back otherwise,
rejects nesting/foreign managers/closed tokens, and exposes the external-I/O guard. Cross-manager
rejection is a `TypeError`, representing an invalid adapter token without entering the application
error taxonomy. Final user-run gates: 42 focused tests passed, Pyright reported zero errors, Ruff
lint passed, changed-file formatting passed, and all 14 architecture tests passed. Do not migrate a
repository by adding another `bind()` variant; new repository methods accept transaction tokens
directly.

## Phase 2 — Application Intake vertical slice

Status: DONE

### Goal

Move duplicate check, ingest, snapshot replacement, and notes to independent application,
snapshot, recruitment, and audit repositories under the new transaction scopes.

### Must preserve

- payload-before-row ordering.
- duplicate warning behavior.
- immutable JobSnapshot history.
- initial `saved` recruitment event.
- optimistic notes update and audit.
- deleted application semantics.

### Implement

- `SqlAlchemyApplicationStore`.
- `SqlAlchemyJobSnapshotStore`.
- `SqlAlchemyInitialRecruitmentEventWriter`.
- `SqlAlchemyAuditLog`.
- final intake Ports and explicit `ApplicationService` constructor.
- immutable-payload orphan semantics and external-I/O guard calls.

### Migrate

- application service/API tests and persistence tests for this slice.
- intake seed/helpers and fixtures.

### Delete

- application-intake methods from `SqlAlchemyPreparationRepository` once no consumer remains.
- nested `self.applications` and its constructor/bind handling.
- corresponding old Port methods and casts.

### Verification

- [x] focused tests
- [x] typecheck
- [x] architecture checks
- [x] no forbidden imports
- [x] no old consumers remain
- [x] intake transaction atomicity and orphan ordering
- [x] no external payload write while transaction active

### Handoff notes

The service is migrated and composition uses independent application, snapshot, initial-recruitment,
and audit adapters. The payload write remains before the database scope. A failed DB transaction may
leave an immutable orphan but must never leave a row naming a missing payload. Focused contract and
rollback coverage was added and passes. The old preparation intake methods,
`ApplicationStore.create_application`, and nested `self.applications` adapter were deleted; persistence
test setup now creates intake records through the transaction-token stores. The root repository still
exists only for unmigrated slices and no longer exposes application creation. Final user-run gates:
42 focused tests passed, Pyright reported zero errors, Ruff lint passed, changed-file formatting
passed, and all 14 architecture tests passed.

## Phase 3 — Analysis and selection lifecycle

Status: DONE

### Goal

Migrate analyses and selection plans, including operation activation, with no preparation aggregate
or repository casts.

### Must preserve

- AI-only new analysis creation.
- analysis + initial plan atomicity.
- lineage and expected-plan conflicts.
- provider evidence preservation before activation.

### Implement

- `SqlAlchemyAnalysisPlanRepository` and Ports.
- analysis/selection source projections.
- explicit `AnalysisService` collaborators.

### Migrate

- analysis services, handlers, tests, seeds, and projections.

### Delete

- migrated preparation methods and casts.

### Verification

- [x] focused tests
- [x] typecheck
- [x] architecture checks
- [x] no forbidden imports
- [x] no old consumers remain
- [x] no provider/network call inside a transaction

### Handoff notes

Initial worktree was clean at `24d80de627f35bb47e9c49b8a47c6d110742540c`.
Phase 3 verification, including the requested closeout cleanup, has passed. Product/type/architecture gates were run by the user;
Ruff gates were run by the agent only after the user explicitly requested them.
Phase 3 and cleanup are committed as `247dd6f20c5512f312e4da918464c3c7df9f813c`.

- Added independent token adapters for analysis/plans, minimal analysis/selection sources, provider
  evidence, operation activation, and the atomic selection-plan/working-draft update.
- `AnalysisService` has explicit narrow dependencies, without ServiceBase, preparation aggregate,
  persistence casts or bound UoW. Handlers receive a scope-free activator; the runner owns activation.
- Provider execution and payload preservation/verification precede durable inactive evidence registration.
  Source/lineage recheck, analysis + initial plan, evidence activation and operation completion are atomic.
  Cancellation or activation rollback retains inactive evidence. Selection replacement preserves plan CAS.
- Migrated only the atomic plan/draft selection-change boundary; other draft lifecycle paths are unchanged.
- Removed preparation `save_analysis`, obsolete JobStore members, the PreparationRepository Port,
  analysis/selection casts and binds, and the unused proposal activation helper.
- Preparation remains for real future consumers: historical analysis/plan reads and snapshot capabilities
  (draft/readiness/query/knowledge), plus `knowledge/mutations.py` selection-plan writes with fact events
  and recovery journal semantics (Phase 9). Shared private SQL primitives serve these consumers without
  repositories calling repositories or wrapping the new token API. Root Repository, legacy UoW, composed
  Ports and unrelated handlers remained intentionally for later phases.
- Activation probes knowledge recovery state through its token and loads canonical files through a
  file-only collaborator, avoiding the legacy FileKnowledge callback opening a nested DB scope.
  Composition permits explicit `activation_knowledge` injection.
- Added rollback, shared-token activation, external-I/O exclusion, cancellation, retry/deduplication,
  plan/draft atomicity, token rejection and derived architecture coverage. Schema, immutable historical
  records, artifact paths, rendering output and `domain/facts.py` were not changed.

### Closeout cleanup — verified

Repository-wide searches covered production and test consumers, dynamic monkeypatch/getattr usage,
imports, Ports, helper references and migrated transaction paths. No architecture redesign was performed.

- Deleted unused legacy `_insert_application`, `set_normalized_role`, `update_application_notes`
  from the application adapter; deleted unused `duplicate_application_inputs` and
  `snapshot_for_content_hash` from preparation. Their migrated token implementations remain.
- Removed the four corresponding obsolete ApplicationStore/JobStore Protocol members and dead imports.
- Migrated `seed_analysis_for_command` snapshot ownership checking to AnalysisService's source projection.
- Reused private `_lock_application` SQL in provider evidence and operation activation instead of duplicated
  lock queries; corrected its stale READ COMMITTED/version-allocation docstring.
- Other extracted analysis/operation/draft SQL helpers have real consumers and are already shared.
  No unused Phase 1–3 composition dependency or temporary compatibility wrapper was found.
- Retained `add_job_snapshot` because readiness/chain/state tests use it to create future-phase scenarios.
  Historical analysis/plan/snapshot reads, draft/readiness/query casts and UoW, the root/composed Ports,
  and knowledge's Phase 9 plan writer remain required. Provider proposal-type casts are not persistence casts.
- Duplicate intake/normalized-role/note paths without consumers were removed. The legacy knowledge plan
  entry point and token plan entry point intentionally coexist and share SQL; future-phase historical readers
  also coexist with minimal token projections. No duplicate migrated write implementation remains for the
  removed capabilities. Legacy operation lifecycle and token activation methods coexist until Phase 6.
- Cleanup was included in the Phase 3 implementation commit above.

Final user-run verification: focused product/cleanup tests passed, including the final 100-test
cleanup subset; Pyright passed with zero errors and warnings; 17 architecture tests passed; Ruff
check and format check passed; and the fresh PostgreSQL pipeline with `OPENAI_API_KEY` unset passed
three tests. AI coverage includes activation lock ordering, evidence retry/cancellation, atomic
rollback, and external-I/O exclusion.

## Phase 4 — Draft lifecycle and evidence

Status: DONE

### Goal

Replace the broad Draft repository/service with cohesive draft surfaces and separate artifact,
validation, and decision ownership.

### Must preserve

- optimistic draft edits.
- exact lineage and validation binding.
- immutable approval evidence.
- archive-before-deactivate safety.

### Implement

- draft, artifact, validation, and decision repositories/Ports.
- four draft service surfaces.
- `ApprovalCommitter` with prepared immutable input.
- in-memory working projection generation.

### Migrate

- draft authoring, validation, history, approval, handlers, and tests.

### Delete

- old `DraftRepository`, `ReadinessRepository`, `DraftService` façade, migrated base helpers/casts.

### Verification

- [x] focused tests
- [x] typecheck
- [x] architecture checks
- [x] no forbidden imports
- [x] no old consumers remain
- [x] approval crash/orphan/idempotent-retry coverage

### Handoff notes

Phase 4 implementation is complete and all user-run boundary gates passed; the phase is **DONE**
in commit `08f69ee2cc13c3e329b0b47d2c40e2e031e4deed`. Recovery began from
`67b36e6d0f9f041585b76857618732846e532421`; the verified Phase 3 implementation and its
evidence remain unchanged.

The persistence split now has independent stateless token adapters for `DraftLifecycleStore`,
`ArtifactCatalog`, `ValidationStore`, `DecisionStore`, and the approval-owned
`IdempotencyStore`. Legacy adapters and token adapters share private connection-level SQL;
one adapter never calls another and no adapter opens a scope. Consumer-specific readers load
authoring, validation, approval, history, and Operation activation inputs without a generic
workflow DTO.

The multiple-inheritance `DraftService` façade and its base/mixin files are gone. API and runtime
composition expose `DraftAuthoringService`, `DraftValidationService`, `DraftApprovalService`,
and `DraftHistoryService`. Generation, editing, regeneration, validation, approval, archive/keep,
and decision export use those surfaces. Draft and regeneration handlers now use runner-owned
transaction-token activation. Working Markdown is written only after activation commits; a
projection failure is logged without rewriting the already-completed Operation. Immutable
approval and archive payloads are still written and verified before their database metadata.

`ApprovalCommitter` accepts one frozen `PreparedApproval` and performs the demonstrated fan-in:
ApprovedRevision/deactivation, both artifact registrations, decision, audit/lifecycle event, and
receipt completion in one caller-owned transaction. Reservation remains a preceding durable short
transaction, and an identical retry can reuse immutable payloads and the reserved revision. The
commit and receipt completion are one transaction, and recovery coverage distinguishes rollback
before commit from a lost response after commit.

Validation evaluates in memory outside a database scope, then locks and rechecks the exact working
draft version/hash before recording immutable evidence. Approval locks the WorkingDraft row while
rechecking its stored validation binding. These checks preserve optimistic editing and prevent a
run or revision from being recorded for content that changed during preparation.

Zero-consumer cleanup removed the façade, archival/decision mixins, draft base helpers, legacy
approval/replacement/deactivation writes, and legacy decision/generation/lifecycle-event writes.
Legacy `DraftRepository`/`ReadinessRepository` reads, direct persistence-test draft create/edit
methods, validation/artifact reads and render-owned writes remain because Phase 5 rendering,
Ready, tracking, projections, maintenance, and their integrity tests still consume them. The
remaining render casts and root-bound handler are Phase 5 scope; generic Operation lifecycle,
replacement reservation/enqueue, and its root repository remain Phase 6 scope.

Constructor review: `DraftAuthoringService` has ten explicit collaborators because authoring owns
one optimistic lifecycle across persistence, source projection, Knowledge/provider/evidence,
working projection, and the already-approved selection-change component. `DraftApprovalService`
has nine because preparation crosses stored source evidence, Knowledge, projection/render naming,
immutable payload publication, receipt reservation, and the approved atomic committer. Bundling
either set would create the forbidden generic dependency container; the committer is retained only
for its atomic fan-in, not to shorten the approval constructor.

The final implementation commit spans 62 paths: 4,711 insertions and 2,481 deletions. Its pre-commit
index and worktree checks were clean. The follow-up status update records the implementation hash
without amending that commit.

The schema, artifact paths, rendered output, immutable historical records, and other idempotency
paths are unchanged. No migration file or frontend file changed.

Final user-run verification: authoring/API/AI/operation tests passed; validation/application
contract tests passed; chain/history/Ready integrity tests passed with one browser-marked case
deselected; persistence/transaction and API-operation tests passed; 18 architecture tests passed;
approval rollback, retry, and lost-response recovery tests passed; Pyright passed with zero errors
and warnings; Ruff check and format check passed; and the fresh PostgreSQL pipeline at migrations
`0001`–`0002`, with `OPENAI_API_KEY` unset, passed three tests. Browser/golden and migration topology
gates were not required because renderer output, artifact paths, golden hashes, and `alembic/` were
unchanged.

## Phase 5 — Rendering, Ready, recruitment, and submission

Status: DONE

### Goal

Migrate rendering and tracking without broad readiness/tracking Ports or external I/O inside DB
transactions.

### Must preserve

- Ready re-derivation from stored evidence.
- both render payloads registered atomically only after both exist.
- submission-owned applied transition.
- append-only recruitment history.

### Implement

- render/submission context projections.
- recruitment repository and final services.
- render ingest-or-reuse and orphan semantics.
- `SubmissionCommitter` only if atomic fan-in evidence confirms it remains justified.

### Migrate

- rendering, tracking, Ready, maintenance, and their tests.

### Delete

- old tracking/readiness Ports and migrated repository methods.

### Verification

- [x] focused tests
- [x] typecheck
- [x] architecture checks
- [x] no forbidden imports
- [x] no old consumers remain
- [x] no browser/object-store I/O in transaction
- [x] partial render upload and DB rollback coverage

### Handoff notes

Work began from clean documentation HEAD `4ec331a1aa6def023485ca575c57b7a32ab3a923`,
directly above verified Phase 4 implementation `08f69ee2cc13c3e329b0b47d2c40e2e031e4deed`.

The recruitment and submission application surfaces are now split. `RecruitmentService`
owns status transitions, corrections, close/delete and next-action commands;
`SubmissionService` owns internal/external submission and the optional `saved -> applied`
transition. Both use caller-owned token scopes. `SqlAlchemyRecruitmentRepository` is stateless,
and `SqlAlchemySubmissionContextReader` supplies the submission-specific source projection.
Submission, its optional status event, and audit remain one atomic write scope without adding a
committer. API DTOs and routes are unchanged; composition now exposes the two cohesive services.

Rendering registration now ingests both payloads outside a database scope before opening one
short token write scope for both artifact rows. Post-render validation activation uses the
runner-owned token; Ready verification runs only after that scope closes. The render handler is
on the transactional-handler path and its database source check uses `RenderContextReader` rather
than a persistence cast. Maintenance now snapshots integrity findings and artifact inventory
through a read-only token Port, closes the scope, and only then verifies object-store payloads.

Implementation, zero-consumer cleanup, and verification are complete. `ReadyEvidenceReader` loads
only the persisted revision-bound evidence consumed by
qualification. The transaction closes before immutable payload presence/hash checks. Ready remains
a projection: no Ready row, flag, or status write was added. Application list/detail and revision
detail obtain Ready through this same re-derivation path rather than a persistence cast.

Render preparation now reads its revision, manifest, decision, snapshot, analysis history and plan
through `RenderContextReader`, closes the read scope, then reads immutable payloads and runs the
renderer. Both outputs are ingested before one short artifact-registration transaction. Matching
revision/type/lifecycle/content hashes reuse the existing artifact identity; newly ingested unused
payloads are reconcilable orphans. A second ingest failure or registration rollback leaves no
partial database registration. The runner owns post-render validation activation, and Ready is
rechecked only after that transaction closes. Render Operation source freezing also uses the
render service projection, removing its former readiness cast.

Maintenance now snapshots integrity findings and inventory in one token read and verifies payloads
after it closes. Recruitment/submission writes use only `RecruitmentStore`; the obsolete
`TrackingService`, `TrackingRepository`, composed tracking Port and legacy tracking writes were
deleted. The root tracking mixin remains read-only and is named `SqlAlchemyTrackingProjection`:
`ApplicationQueryService` still consumes recruitment events/submissions until the general query
projection migration in Phase 8. Root `Repository`, generic Operation lifecycle/idempotency and its
legacy UoW remain for Phase 6. Draft/chain legacy readers remain for Knowledge and other Phase 8/9
consumers; none is used by the migrated Phase 5 services or render handler.

Architecture guards now include Phase 5 transaction owners and reject root repositories,
persistence casts, bound UoW calls, or handler-owned scopes in the migrated services. Tests were
rewired from deleted tracking writes to the token store. No schema, public DTO, artifact path,
renderer output, golden fixture, immutable historical record, Phase 4 semantics, or Phase 6
lifecycle behavior was changed.

Constructor review: `RenderingService` has nine explicit collaborators because it spans the
specified render boundary: transaction ownership, render/Ready source projections, draft and
artifact/validation persistence, Knowledge, renderer execution, and immutable payload storage.
Combining them would create the forbidden broad workflow container. `SubmissionService` has six
collaborators because it owns the demonstrated submission/status/audit fan-in; that fan-in remains
clear at the service call site, so no `SubmissionCommitter` was introduced.

Final user-run verification:

- backend suite: **493 passed, two deselected**.
- focused render cancellation and source-change regressions: passed.
- Pyright: **zero errors and zero warnings**.
- Ruff check: passed.
- Ruff format check: **36 files already formatted**.
- fresh PostgreSQL pipeline at Alembic head `0002`, with `OPENAI_API_KEY` unset: **three passed**.
- staged and unstaged diff checks: clean.

Final zero-consumer cleanup found no further production deletion that belonged to Phase 5. The
remaining root `Repository`, legacy UoW/bind path, Operation repository/casts, generic Operation
submission/lifecycle/retry/replacement ownership and its idempotency wiring are Phase 6 scope.
Runner-wide legacy activation infrastructure remains for Phase 7. The read-only
`SqlAlchemyTrackingProjection` and query-side recruitment/submission readers remain consumers of
`ApplicationQueryService` until Phase 8 projection migration. Draft/chain readers and the
Knowledge mutation UoW remain for Phase 8/9 consumers. Two stale comments were corrected; no
compatibility wrapper, duplicate Phase 5 SQL write path, obsolete Phase 5 Port member, or dead
Phase 5 helper/import remains.

## Phase 6 — Operation submission, lifecycle, and replacement

Status: DONE

### Goal

Split the old Operation service and isolate generic idempotency from durable Operation lifecycle.

### Must preserve

- exact frozen source identities.
- idempotent replays.
- replacement keep-before-visibility protocol.
- cancellation and retry policies.

### Implement

- operation client/execution Ports.
- idempotency repository.
- submission, lifecycle, and replacement services.

### Migrate

- API routes, operation tests, and replacement workflow.

### Delete

- old `OperationService`, approval methods within it, and migrated operation casts.

### Verification

- [x] focused tests
- [x] typecheck
- [x] architecture checks
- [x] no forbidden imports
- [x] no old consumers remain
- [x] replacement crash-window coverage

### Handoff notes

Implementation, cleanup, and combined verification are complete.

- `OperationSubmissionService`, `OperationLifecycleService`, and
  `OperationReplacementService` now own explicit token scopes over a stateless
  `OperationClientStore`; the old `OperationService` façade is removed.
- Submission freezes source identities outside the enqueue transaction, then rechecks and locks
  the Application while replaying or creating the immutable queued Operation. Operation-row
  uniqueness remains the atomic generic submission idempotency record, including lost-response
  replay and changed-payload refusal.
- Replacement uses the token `IdempotencyStore`: reserve/replay precedes Keep, immutable Keep
  payload work runs outside a database scope, and enqueue visibility follows successful Keep.
  Pending-receipt recovery distinguishes failure before Keep, after Keep, and after enqueue.
- API containers and routers expose the three cohesive surfaces without opening scopes or
  changing HTTP status, body, or Operation `Location` behavior.
- The root Operation command/retry/cancellation/idempotency methods and broad
  `OperationRepository` Port are removed. Tests now use the client, execution, and receipt token
  capabilities for Phase 6+7 behavior.
- The runner integration boundary receives queued immutable Operations from the submission
  service and owns every execution scope described in the Phase 7 handoff.
- Final passing evidence: combined Operation/API coverage (147 passed), full backend coverage,
  architecture and old-consumer guards, Pyright, Ruff lint/format, and the fresh PostgreSQL
  pipeline with `OPENAI_API_KEY` unset all passed.

### Combined Phase 6+7 initial consumer map (before implementation)

| Consumer | Existing persistence/external boundaries and migration ownership |
| --- | --- |
| asynchronous API submitters in `applications.py`, `analyses.py`, `working_drafts.py`, and `approved_revisions.py` | `OperationService` freezes sources through migrated domain services, then writes through the root `OperationRepository`; Phase 6 moves reservation/replay and enqueue into service-owned token scopes without changing `202`/`Location` behavior |
| `api/routers/operations.py` | client-visible get, queued/running cancellation, and immutable retry currently share the broad Operation service/repository; Phase 6 moves them to `OperationLifecycleService` and `OperationClientStore` |
| WorkingDraft replacement submitter | one broad method owns idempotency reservation, Keep/archive, and replacement enqueue; Phase 6 preserves durable keep-before-visibility and crash-window replay while separating external payload work from short database scopes |
| `OperationRunner` | mixes direct root-repository calls with a legacy `unit_of_work()`/`bind()` activation path and the newer token activation path; Phase 7 makes the runner the sole owner of claim, execution, and activation scopes |
| six Operation handlers | all are already registered on the transactional handler path, but the compatibility handler contract and persistence arguments remain; Phase 7 leaves handlers with source readers/activators and transaction tokens only |
| `OperationWorker` and foreground executor | claim/recovery/cancellation currently call `OperationRepository` directly; Phase 7 moves them to the execution Port while preserving API/worker process separation |
| `SqlAlchemyOperationRepository` and Operation SQL | one bound concrete adapter serves client, runner, idempotency, and activation capabilities; Phases 6+7 retain shared private connection-level SQL but expose independent stateless token capabilities |
| composition and public service containers | `Services`/`ApiServices` expose one `OperationService`, while runner/worker receive the root repository; the primary integration step wires three cohesive services and the independent Operation adapter without exposing scopes to routers |
| root repository and composed Ports | Operation inheritance is the remaining Phase 6+7 reason they include Operation methods; post-migration cleanup removes those members while retaining only demonstrated Phase 8 query and Phase 9 Knowledge consumers |
| tests and architecture guards | operation/API/foreground fixtures still use the root repository and legacy runner shape; migrate only Phase 6+7 behavior here, while Phase 8 retains unrelated root-backed query/assertion fixtures |

The shared composition root, Port/export modules, architecture guards, and final legacy deletion are
primary-agent integration ownership. Phase 6 owns client application/API persistence; Phase 7 owns
runner/handler/worker persistence. Neither sub-slice may delete shared legacy before this combined map
is re-checked after both consumer migrations.

## Phase 7 — Worker and handlers

Status: DONE

### Goal

Move claiming/execution/activation to explicit runner dependencies and transaction-scoped handler
methods.

### Must preserve

- leases, heartbeat, retry, cancellation, application lock, and source recheck ordering.
- activation and operation completion in one transaction.

### Implement

- final handler contract.
- explicit source projections and activators.
- runner transaction ownership.

### Migrate

- worker host, handlers, foreground executor, and operation runner tests.

### Delete

- `OperationRunnerRepository`, handler casts, and old runner binding.

### Verification

- [x] focused tests
- [x] typecheck
- [x] architecture checks
- [x] no forbidden imports
- [x] no old consumers remain
- [x] handlers/activators cannot open transactions
- [x] no external execution in activation transaction

### Handoff notes

Implementation, cleanup, and combined verification are complete.

- `OperationRunner` now depends only on `TransactionManager`, `OperationExecutionStore`, and the
  handler registry. Claims, recovery, heartbeat, phases, attempts, cancellation observation,
  inactive outputs, failure, and completion all use short runner-owned token scopes.
- External source checks and provider/browser/filesystem execution remain outside database
  transactions. Activation is one short transaction ordered as Application lock, Operation/lease
  reload, persisted-source recheck, cancellation recheck, activation, output activation, and
  terminal completion. Post-commit projection and structured filesystem logging remain outside.
- Every registered handler uses one token contract for persisted source checks and activation;
  handlers and activators receive no transaction manager and open no scopes. Rejected provider
  evidence is returned to the runner for durable inactive registration rather than written through
  a persistence cast.
- Worker claim/recovery and foreground execution now delegate to the runner. The API process still
  creates Operations only; the worker remains the separate execution host.
- Removed `OperationRunnerRepository`, legacy/transactional handler bifurcation, runner
  `unit_of_work()`/`bind()`, `OperationActivationStore`, `SqlAlchemyOperationActivationStore`, the
  broad `SqlAlchemyOperationRepository`, and their obsolete Ports/imports.
- Remaining legacy is limited to demonstrated future consumers: `SqlAlchemyOperationProjection`
  supplies `active_operation`, `latest_operation`, and
  `has_active_matching_context_operation` to `ApplicationQueryService` for Phase 8; the root
  repository/UoW/bind path otherwise remains only for Phase 8 projections and Phase 9 Knowledge
  mutation/recovery. No Phase 6+7 service, runner, handler, worker, or focused test consumes it.
- Final passing evidence: claim/lease/heartbeat and foreground/worker race coverage, the combined
  Operation/API suite, full backend coverage, architecture and transaction-scope guards, Pyright,
  Ruff lint/format, and the fresh PostgreSQL pipeline all passed.

## Phase 8 — Projections and test migration

Status: NOT STARTED

### Goal

Finish consumer-specific read models and remove test dependence on a persistence root.

### Must preserve

- stable read snapshots.
- API view contracts.
- deliberate corruption coverage.

### Implement

- application projection readers.
- repository-specific and raw-DB test fixtures.
- derived architecture checks.

### Migrate

- all remaining `services.repository` assertions/helpers.

### Delete

- `Services.repository`, `QueryRepository`, root repository test fixture, generic test helpers.

### Verification

- [ ] focused tests
- [ ] typecheck
- [ ] architecture checks
- [ ] no forbidden imports
- [ ] no old consumers remain
- [ ] no `services.repository` use remains

### Handoff notes

None yet.

## Phase 9 — Knowledge lifecycle

Status: NOT STARTED

### Goal

Unify fact events and the durable mutation journal behind the final recovery-specific boundary.

### Must preserve

- prepare/activate/recover/restore/quarantine semantics.
- canonical fact safety and approval blocking.

### Implement

- knowledge lifecycle repository and services.
- recovery transaction boundaries.

### Migrate

- fact lifecycle, recovery, fixtures, and tests.

### Delete

- old FactAudit/KnowledgeMutation composed Ports and migrated adapters.

### Verification

- [ ] focused tests
- [ ] typecheck
- [ ] architecture checks
- [ ] no forbidden imports
- [ ] no old consumers remain
- [ ] crash recovery and external-I/O transaction guards

### Handoff notes

None yet.

## Phase 10 — Final deletion and baseline reset

Status: NOT STARTED

### Goal

Remove the old architecture completely and leave one coherent persistence model.

### Must preserve

- all product semantics and immutable record protections.

### Implement

- final schema/migration baseline reset if useful.
- final derived architecture guards.
- storage orphan maintenance listing/deletion with a grace period if not completed earlier.

### Migrate

- remaining docs, imports, fixtures, and composition.

### Delete

- every item in the Delete list, all temporary coexistence, and all dead helpers.

### Verification

- [ ] focused tests
- [ ] typecheck
- [ ] architecture checks
- [ ] no forbidden imports
- [ ] no old consumers remain
- [ ] scoped backend gates selected from the final diff
- [ ] pipeline test on a fresh PostgreSQL database

### Handoff notes

None yet.

## 8. Current status maintenance

Every phase completion updates the summary at the top, the phase Status, Verification checkboxes,
and Handoff notes. `Last verified commit` changes only after the user reports gates passing for the
named commit and conditions. A failed gate remains failed and blocks the next phase.

## 9. Testing gates

Before moving to the next phase, the user runs the commands handed over for that phase. Required
evidence is selected from the actual slice but always covers:

- focused tests for migrated behavior.
- Pyright typecheck over `cv_engine`.
- architecture checks.
- no imports or calls from the removed API in the migrated slice.
- no dead consumers before old code is deleted.
- transaction commit/rollback/lifetime/foreign-manager/nesting tests when transaction behavior is
  touched.
- tests proving relevant external adapters refuse I/O while a transaction is active.

The repository rule is that the user runs gates; agents update this document with reported results
and never mark unchecked evidence as passed.

## 10. Decision Log

Record only evidence-backed contradictions or deviations.

For each contradiction:

1. Stop the specific change.
2. Record the discovered code/spec evidence.
3. Explain why the current target does not fit.
4. Propose the smallest target-architecture change.
5. Update this document before implementation resumes.

### Locked decisions

- 2026-09-17: Start with context-managed auto-commit transactions. This is the simplest API that
  can meet all mandatory transaction invariants; callback syntax is not itself a goal.
- 2026-09-17: Workflow reads use minimal consumer-specific projection DTOs. A general
  `WorkflowContextReader` is forbidden.
- 2026-09-17: Commit gateways are limited to demonstrated atomic fan-in. Constructor shortening is
  not sufficient justification.

### Deviations

#### 2026-09-17 — Approval replay payload contract correction (approved)

- Code evidence: `application/services/operations/service.py:approve_idempotent`
  checks only `working_draft_id` before `_approval_result`. When the reserved revision
  exists, it returns that result (and may complete a pending receipt) before comparing
  the receipt payload with `_approval_payload(command)`. Changing only
  `expected_edit_version` or `validation_run_id` therefore returns the original approval
  instead of rejecting key reuse. This conclusion is from code inspection; no test was run.
- Binding evidence: `spec/state-and-use-cases.md` §15 requires the same key/payload to
  return the same revision and another payload to fail. The owning API route,
  `api/routers/working_drafts.py:approve_working_draft`, explicitly documents
  `409 IDEMPOTENCY_KEY_REUSED` for a changed draft, version, run, or content hash.
- Coverage evidence: `tests/test_api_working_drafts.py`'s
  `test_the_same_key_returns_the_same_revision_and_a_changed_payload_is_reuse` covers
  an identical replay and a different draft, but does not change the version/run on
  the same already-approved draft. `tests/test_operations.py`'s
  `test_pending_approval_receipt_recovers_a_committed_revision` requires same-payload
  recovery and must remain valid.
- Scope conflict: Phase 4 must preserve approval/idempotent recovery while this session
  prohibits observable API changes beyond internal wiring. Copying the early return
  into `DraftApprovalService` preserves behavior contrary to the specification;
  rejecting those requests corrects the specification mismatch but changes observable
  refusal behavior. The user has authorized the focused contract correction described below.
- Minimal proposed resolution: authorize this focused regression correction as part of
  Phase 4. Compare the existing receipt's frozen payload before returning a committed
  revision or completing its receipt, for both pending and completed receipts. Keep
  identical replay/recovery, immutable records, payload paths, and revision identity
  unchanged. Extend the closest API test to vary version/run on the same approved
  draft and retain pending-receipt recovery coverage. No architecture redesign, schema
  change, or Phase 6 lifecycle migration is proposed. Approved by the user: compare the exact logical payload before replay/recovery;
  cover identical replay, changed draft/version/run and other outcome-affecting inputs,
  reservation recovery, and identical retry after failure. This is a specification-required
  contract correction within Phase 4, not a Phase 4 redesign or authorization to change
  other idempotency paths.

#### 2026-09-17 — Provider-evidence registration boundary (approved)

- Code evidence: `application/services/base.py:ServiceBase.preserve()` registers the
  provider-response artifact during execution. `services/operations/handlers.py` returns
  it as an inactive prepared output. `application/operation_runner.py:run_claimed()`
  records inactive outputs before cancellation checks, then activates them inside the
  successful activation transaction.
- Binding behavior: product-spec §18 requires completed output after cancellation to be
  recorded as inactive evidence; state-and-use-cases §19 requires later output to be
  registered inactive and prohibits activation.
- Conflict if interpreted literally: the session requirement to save provider evidence
  as part of atomic activation cannot make initial artifact/output registration conditional
  on activation. Cancellation can skip activation; activation rollback must not erase
  already-recorded immutable evidence.
- Smallest proposed target clarification: prepare payloads outside transactions; register
  immutable artifacts and inactive operation outputs before activation in short database
  scopes; activate evidence outputs atomically with analysis + initial plan (or replacement
  plan) and operation completion. Initial registration remains outside the activation
  rollback domain. Provider/network/filesystem writes remain outside database scopes.
- Approved by the user: `prepare → persist inactive evidence → activation transaction →
  activate evidence`. Provider execution and payload preservation/verification occur outside
  database scopes. Initial metadata/output registration remains durable and inactive on
  cancellation or failed activation. Evidence activation, source/lineage recheck, analysis,
  initial plan, and associated operation activation writes share one transaction. Re-registering
  the same provider output must not duplicate evidence. No locked decision reopened.

### Phase 3 initial consumer map (before implementation)

| Public operation / consumer | Persistence and boundary |
| --- | --- |
| `AnalysisService.prepare` | snapshot identity/hash/payload source read; provider and payload outside DB scope |
| `AnalysisService.activate` | analysis + initial plan + classification/normalized role; synchronous entry point owns scope, runner owns operation scope |
| `create_selection_plan` | named analysis, compatible active plan, replacement write and expected-plan CAS |
| `prepare_selection_proposal` | named analysis/compatible plan; provider response preserved before activation |
| `activate_selection_proposal` | prepared deterministic overlay activation under runner scope |
| `apply_analysis_decisions` | named analysis/observed plan; classification replacement or plan replacement with CAS |
| analysis/selection handlers | frozen-source rechecks and activation; legacy preparation casts removed in this phase |
| operation submission | snapshot/analysis/compatible plan sources; two preparation casts removed |
| `drafts/selection.py` | bound UoW + preparation cast; migrate only the atomic plan/draft selection-change boundary |
| `knowledge/mutations.py` | real future-phase consumer of legacy `create_selection_plan`, atomically with fact events and recovery journal semantics |
| draft/readiness/query/knowledge reads | existing analysis/plan history readers remain until owning phases migrate |

`preparation.py` owns `save_analysis`, `create_selection_plan`, lock/CAS/lineage helpers,
analysis history readers, selection-plan readers, and legacy snapshot readers/writers.
`AnalysisService` inherits persistence casts through `ServiceBase` (application lookup and
provider artifact registration), even though its own module contains no `cast()`.
The runner currently binds its root UoW for every activation. Only analysis/selection activation
will use transaction tokens in this phase; unrelated handlers remain on their existing path.
The knowledge selection-plan writer cannot be deleted while that real Phase 9 consumer remains;
its persistence implementation may share private SQL primitives, without calling another
repository or wrapping the new transaction-token API.

### Phase 3 evidence identity and activation wiring

- Deduplication uses provider response identity, task, provider/model, input/output hashes and execution
  settings. The same provider-assigned response can be reused across retry Operations without rewriting
  its immutable artifact; each Operation has its own inactive/active output association. Without a provider
  response identity, reuse is limited to the same Operation. Distinct outputs remain distinct evidence.
  New metadata carries `evidence_key` and `payload_size`; old immutable records are untouched.
- Registration serializes on the Application lock and repeats lookup before insertion. Concurrent payload
  preservation can leave an unused immutable payload orphan, consistent with reconciliation invariants.
- Initial registration owns a separate short service transaction. Handlers and activators own no scope.
  The runner locks the Application as its first activation statement and emits filesystem-backed phase
  events after the transaction closes.

### Phase 4 initial consumer map (before implementation)

| Consumer | Existing persistence/external boundaries and migration ownership |
| --- | --- |
| `drafts/generation.py` | analysis/plan/latest snapshot/optional parent reads; provider + response preservation; activation replaces draft, validates, records generation; currently writes working projection during runner-bound activation |
| `drafts/regeneration.py` | exact draft/version/hash/analysis/plan reads; provider + evidence; optimistic activation update currently writes working projection under activation |
| `drafts/editing.py` | exact source/chain/Knowledge checks and optimistic edit; projection after edit; legacy `edit_claim` also records validation |
| `drafts/validation.py` | exact working version + bound chain + plan; in-memory Markdown already used; immutable validation report/lineage recording |
| `drafts/approval.py` | active/deleted/quarantine/projection/binding/chain checks; immutable JSON/Markdown publication before DB; revision + two artifacts + decision + audit + lifecycle event/deactivation fan-in |
| `operations/service.py` approval methods | receipt reservation, committed-revision recovery, approval delegation, then separate receipt completion; move approval ownership in Phase 4, leave unrelated operation lifecycle for Phase 6 |
| `drafts/archival.py` | payload before artifact + deactivation/audit/event transaction; Keep verifies an existing exact snapshot before reuse; replacement reservation/enqueue protocol remains Phase 6 |
| `drafts/decisions.py` | application + explicit revision + stored decision reads; historical Markdown export without live facts |
| `drafts/selection.py` | Phase 3 token plan + draft CAS already atomic; `_compose` still lives on `DraftServiceBase`; preserve token boundary while removing façade coupling |
| draft/regen handlers + runner | persistence casts and root-bound activation; runner owns Application lock and final activation/completion; migrate these handlers to tokens and move working projection writes after scope exit |
| `base.py` + `chain.py` | inherited provider/artifact/application helpers and broad chain reader; replace draft consumers with explicit collaborators/minimal chain inputs; retain only helpers with real future-phase consumers |
| API services/routes + runtime composition | single `drafts: DraftService` surface and `shared` wiring; migrate actual call sites to four service surfaces, retaining HTTP DTOs/routes |
| `persistence/drafts.py` + `artifacts.py` | bound-base WorkingDraft/ApprovedRevision SQL and combined artifact/validation/decision/generation SQL; extract private SQL for independent token adapters and still-required future-phase readers |
| Ready/render/tracking/query/maintenance | real `ReadinessRepository`/`DraftRepository` readers, including shared chain checks; prevent premature deletion; document the minimal Phase 4 wiring needed while leaving Phase 5 behavior migration unstarted |

The map does not authorize deleting legacy SQL or Ports. Production and test consumers
must be searched again after migration, before each deletion. No knowledge mutation,
operation claiming/retry/replacement protocol, or Phase 6+ work was performed.
