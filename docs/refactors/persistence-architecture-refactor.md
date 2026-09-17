> This document is the source of truth for the persistence refactor. Do not redesign the architecture during implementation unless a concrete contradiction is found. If one is found, document it before changing direction.

# Persistence architecture refactor execution contract

## Current status

```text
Current phase: Phase 3 — Analysis and selection lifecycle (DONE)
Last completed phase: Phase 3 — Analysis and selection lifecycle
Next action: Phase 3 closeout commit when explicitly requested; Phase 4 not started
Known blockers: None
Last verified commit: Phase 1–2 closeout commit (see git log; working-tree evidence recorded below)
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
lint passed, changed-file formatting passed, and all 14 architecture tests passed. The last
architecture failure was a stale `preparation.py` exemption after removal of its old `bind()`; the
exemption was deleted. Do not migrate a repository by adding another `bind()` variant; new
repository methods accept transaction tokens directly.

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
exists only for unmigrated slices and no longer exposes application creation. The first user-run
gate found one rollback test still monkeypatching the old audit adapter; it now injects the failure
through `SqlAlchemyAuditLog`. A removed `Connection` import still needed by unmigrated analysis
methods was restored. Final user-run gates: 42 focused tests passed, Pyright reported zero errors,
Ruff lint passed, changed-file formatting passed, and all 14 architecture tests passed. The existing
formatting issue in `domain/facts.py` is baseline, is outside this diff, and is not part of this
refactor.

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
Ruff gates were run by the agent only after the user explicitly requested them. No commit has been created.

User-reported verification checkpoint:

- Main focused command: 137 passed, 1 failed. The rollback test still patched the deleted root
  `_insert_selection_plan`; updated to patch the actual private SQL insertion primitive.
- Pyright: 1 error, missing `lock_application` on the legacy composed repository capability.
  Restored that declaration on the existing OperationRepository Port, where the legacy lock
  implementation now lives. No new root Port or persistence cast was introduced.
- Persistence subset: 8 passed; working-draft selection subset: 3 passed; knowledge subset: 3 passed.
- Architecture: 17 passed. Fresh PostgreSQL pipeline with OPENAI_API_KEY unset: 3 passed.
- User subsequently reported the corrected rollback test, Pyright and architecture rerun passed.
  Previously passing product subsets and pipeline remain applicable to these test/Port-only corrections.
- Ruff check: passed. Ruff format check: passed, 38 changed/new Python files already formatted.
  Both were run by the agent under the user's explicit instruction.
- All scoped gates now have passing evidence; Phase 3 is DONE. Phase 4 remains NOT STARTED.

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
  Ports and unrelated handlers remain intentionally. Phase 4 has not started.
- Activation probes knowledge recovery state through its token and loads canonical files through a
  file-only collaborator, avoiding the legacy FileKnowledge callback opening a nested DB scope.
  Composition permits explicit `activation_knowledge` injection.
- Added rollback, shared-token activation, external-I/O exclusion, cancellation, retry/deduplication,
  plan/draft atomicity, token rejection and derived architecture coverage. Schema, immutable historical
  records, artifact paths, rendering output and `domain/facts.py` were not changed.

### User-run gates (ordered)

All gates passed, including the focused cleanup reruns recorded below.

1. Focused analysis/selection, AI evidence, operation/API and transaction tests.
2. Persistence subset (tokens, lineage, immutable plans, CAS, locking); working-draft selection changes;
   knowledge `confirm_and_use` / selection-plan rollback subset.
3. `./.venv/bin/pyright cv_engine` and `tests/test_architecture.py` (including old-consumer guards).
4. Ruff check and format check on changed/new Python files; unrelated baseline files excluded.
5. `tests/test_pipeline_end_to_end.py` against fresh PostgreSQL with `OPENAI_API_KEY` unset.

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
- User-staged Phase 3 files were left staged; cleanup edits remain unstaged. No commit or Phase 4 work.

User-reported cleanup results: focused tests **100 passed**; Pyright **0 errors, 0 warnings**;
architecture **17 passed**; Ruff check **passed**; format check **7 files already formatted**.
All cleanup gates passed. No commit has been created and Phase 4 remains NOT STARTED.

Focused cleanup gates (user-run, completed):

```sh
./.venv/bin/python -m pytest -q tests/test_application_contracts.py tests/test_api_applications.py tests/test_analysis.py tests/test_selection.py tests/test_ai_tasks.py tests/test_api_analyses.py
./.venv/bin/pyright cv_engine
./.venv/bin/python -m pytest -q tests/test_architecture.py
./.venv/bin/ruff check cv_engine/application/ports/repositories.py cv_engine/infrastructure/persistence/applications.py cv_engine/infrastructure/persistence/preparation.py cv_engine/infrastructure/persistence/analysis_sql.py cv_engine/infrastructure/persistence/operation_activation.py cv_engine/infrastructure/persistence/provider_evidence.py tests/helpers.py
./.venv/bin/ruff format --check cv_engine/application/ports/repositories.py cv_engine/infrastructure/persistence/applications.py cv_engine/infrastructure/persistence/preparation.py cv_engine/infrastructure/persistence/analysis_sql.py cv_engine/infrastructure/persistence/operation_activation.py cv_engine/infrastructure/persistence/provider_evidence.py tests/helpers.py
```

AI tests cover activation lock ordering, evidence registration/retry/cancellation, atomic rollback and external
I/O exclusion; application contracts cover the migrated helper's ownership validation. No observable signature,
stored-value meaning, projection field, schema, render or artifact path changed in cleanup, so the prior fresh
PostgreSQL pipeline evidence remains applicable without another pipeline rerun.

## Phase 4 — Draft lifecycle and evidence

Status: NOT STARTED

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

- [ ] focused tests
- [ ] typecheck
- [ ] architecture checks
- [ ] no forbidden imports
- [ ] no old consumers remain
- [ ] approval crash/orphan/idempotent-retry coverage

### Handoff notes

None yet.

## Phase 5 — Rendering, Ready, recruitment, and submission

Status: NOT STARTED

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

- [ ] focused tests
- [ ] typecheck
- [ ] architecture checks
- [ ] no forbidden imports
- [ ] no old consumers remain
- [ ] no browser/object-store I/O in transaction
- [ ] partial render upload and DB rollback coverage

### Handoff notes

None yet.

## Phase 6 — Operation submission, lifecycle, and replacement

Status: NOT STARTED

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

- [ ] focused tests
- [ ] typecheck
- [ ] architecture checks
- [ ] no forbidden imports
- [ ] no old consumers remain
- [ ] replacement crash-window coverage

### Handoff notes

None yet.

## Phase 7 — Worker and handlers

Status: NOT STARTED

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

- [ ] focused tests
- [ ] typecheck
- [ ] architecture checks
- [ ] no forbidden imports
- [ ] no old consumers remain
- [ ] handlers/activators cannot open transactions
- [ ] no external execution in activation transaction

### Handoff notes

None yet.

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
