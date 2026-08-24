# v2.0 Architecture

Status: **Approved for v2.0 implementation (2026-08-17)**

Product authority: `docs/v2/spec/product-spec.md`

Baseline: `v1.0.0` / `2cc31c7`

## 1. Architecture objective

v2.0 adds a local Web product without creating a second workflow engine. FastAPI and
the CLI are independent clients of one synchronous application layer. Existing domain
and validation behavior is preserved and separated from orchestration, storage, and
transport concerns.

The primary architecture rule is:

`domain <- application <- infrastructure / api / cli / runtime`

Dependencies point inward. Product semantics live in domain/application code, not in
routers, React components, SQL triggers, templates, or CLI dispatch.

## 2. Required technology baseline

Backend/runtime:

- Python 3.11+
- Pydantic for serialized domain documents, AI contracts, application boundary DTOs,
  and HTTP schemas
- FastAPI for the local HTTP API and production static-asset serving
- standard-library `sqlite3`
- Jinja2 for resume HTML
- Playwright-managed Chromium for rendering and render validation
- `pypdf` for PDF extraction and ATS checks

Frontend:

- React and TypeScript
- Vite
- React Router
- TanStack Query
- React Hook Form
- Tailwind CSS
- `lucide-react` for the icon set
- generated TypeScript types from OpenAPI
- selective Radix primitives only when an accessible complex primitive is warranted

Testing additions:

- Vitest, with `jsdom` as its DOM environment
- React Testing Library, with `@testing-library/jest-dom` matchers
- Playwright Web E2E
- axe checks on the central screens, through `@axe-core/playwright`

SQLAlchemy, Alembic, Redux, a full component framework, Celery, Redis, WebSockets, SSE,
and a DI framework are not part of v2.0.

## 3. Source organization

The target top-level organization is:

```text
cv_engine/
  domain/
  application/
  infrastructure/
  api/
  cli/
  runtime/
frontend/
```

Subpackages are introduced only when the amount and cohesion of code justify them.
There is no one-file-per-interface rule and no micro-packaging objective.

### 3.1 Domain

The domain owns entities, value objects, lifecycle rules, validation semantics,
transition rules, knowledge/fact safety, Ready qualification, and invariant checks. It
does not import FastAPI, SQLite, Workspace paths, Playwright, React concepts, provider
HTTP code, or runtime configuration.

Pydantic remains appropriate for DraftDocument and other serialized domain documents.
Small internal value objects may be dataclasses when serialization is not a boundary.

### 3.2 Application

The application layer owns explicit commands, queries, services, ports, UnitOfWork
boundaries, permissions/action policy, state projections, optimistic commit checks,
and conversion of validated Proposals into domain state.

Services are synchronous. The layer has no dependency on FastAPI or an event loop.

Focused services are:

- `ApplicationService`
- `AnalysisService`
- `DraftService`
- `RenderingService`
- `TrackingService`

A small façade may compose them for convenience but contains no business logic.

### 3.3 Infrastructure

Infrastructure implements SQLite repositories, UnitOfWork, filesystem payload stores,
KnowledgeRepository, OpenAI provider, rendering, operation claiming/execution, logging,
and backup.

Repository boundaries follow transactional ownership and use-cases rather than tables:

- `ApplicationRepository`
- `PreparationRepository`
- `DraftRepository`
- `ArtifactRepository`
- `OperationRepository`
- `TrackingRepository`
- `AuditRepository`

`PreparationRepository` may own JobSnapshot metadata, JobAnalysis, SelectionPlan,
ValidationRun, and ApprovedRevision metadata where their transactions belong together.

### 3.4 API and CLI

FastAPI routers map HTTP DTOs, headers, and application errors to use-cases and
responses. They do not load Profiles, select facts, call providers, validate claims,
calculate fit, or write history directly.

The CLI resolves arguments and compatibility aliases, then calls the same application
services. It does not call FastAPI. Legacy commands may use a compatibility resolver
with warnings; application contracts are not distorted to preserve an obsolete CLI
signature.

The v1 `Engine` compatibility façade was removed once the CLI called the application
services directly. It was never a v2 architectural boundary, and no code refers to it.

### 3.5 Runtime and composition

`runtime/composition.py` is the manual composition root. It builds Workspace paths,
configuration, repositories, UnitOfWork factory, services, provider, renderer,
operation worker, and API dependencies. No DI framework is used.

`cv web` is a supervisor responsible for Workspace validation, schema gates,
process/port detection, worker lifecycle, browser launch, and graceful shutdown.
FastAPI remains a Web server and does not become the installation/process manager.

## 4. Workspace model

No service constructs paths from a repository root. A Workspace/config layer supplies:

```text
knowledge_root
state_root
artifacts_root
temp_root
logs_root
```

The Workspace marker includes at least:

```json
{
  "workspace_id": "uuid",
  "workspace_version": 2,
  "purpose": "development",
  "data_class": "copy",
  "created_at": "UTC timestamp"
}
```

`purpose` and `data_class` distinguish development/test/live and copy/test/live data.
Normal v2 runtime commands fail closed unless the selected root contains a valid v2
marker whose purpose/data class is allowed for that command. An unmarked directory,
legacy v1 root, unknown marker version, or unsafe development/live combination is never
opened as a normal v2 Workspace. Guards use metadata rather than folder-name
heuristics.

There is no exception. The read-only v1 source adapter that once held one was deleted
on 2026-08-19 with the migration it served, so a v1 root is refused outright rather than
read under conditions.

`installation_id` is durable runtime identity stored in state metadata and remains
separate from `workspace_id`, even though v2.0 operates one Workspace at a time.

During development:

```text
v1 worktree -> v1 Workspace
v2 worktree -> isolated v2 Workspace
```

Nothing points v2 at v1. The archive is read by a person with a text editor or
`git worktree add`, never by this engine.

## 5. CandidateContext

One CandidateContext is loaded from Knowledge. It references canonical name/contact
fact IDs and defines filename/display policy, timezone, and locale. It carries its own
version/hash for provenance.

Application rows do not contain `candidate_id`. ApprovedRevision metadata records the
CandidateContext version/hash used. Renderers and filename policy take CandidateContext
as an explicit dependency, eliminating candidate literals from code.

Existing semantic fact IDs are preserved. New v2 facts use UUIDv4 technical identity;
a human slug is optional metadata and never a foreign key.

Knowledge dependencies are re-read or re-hashed before relevant commands. Manual file
and CLI edits remain valid inputs; a changed context produces `knowledge_changed` or
`SOURCE_CHANGED` and is never silently loaded into an open editor form.

## 6. Persistence boundary

### 6.1 SQLite

SQLite stores structured state and relationships:

- Applications and current recruitment projections
- immutable status and audit history
- JobSnapshot metadata
- JobAnalysis and SelectionPlan structured data
- WorkingDraft structured source, `edit_version`, and content hash
- ValidationRun structured reports and metadata
- ApprovedRevision metadata
- Artifact metadata
- Submission records
- Operation, lease, idempotency, failure, retry, and output metadata
- safe settings
- Knowledge audit and cross-store mutation journal
- schema, installation, and Workspace metadata

SQLite configuration includes foreign keys, WAL, a busy timeout, short transactions,
CHECK/UNIQUE constraints, and only the narrow triggers needed to prevent otherwise easy
immutability bypasses. Business workflows remain in domain/application code.

The database uses explicit numbered SQL migrations and schema version metadata. It does
not depend on application startup side effects to perform an unguarded migration.

### 6.2 Filesystem

The filesystem stores immutable/heavy payloads:

```text
{artifacts_root}/
  snapshots/{application_id}/{snapshot_id}.txt
  revisions/{application_id}/{revision_id}/resume.json
  revisions/{application_id}/{revision_id}/resume.md
  outputs/{application_id}/{revision_id}/{artifact_id}.html
  outputs/{application_id}/{revision_id}/{artifact_id}.pdf
  outputs/{application_id}/{revision_id}/{artifact_id}.png
  provider/{application_id}/{operation_id}/{artifact_id}.json
```

Additional manifests use immutable UUID-based names. Every payload has SHA-256 metadata
in SQLite. Recruiter-friendly names are Content-Disposition/export names, never the
physical identity of an artifact. There is no `latest.pdf` artifact.

JobSnapshot source is the exact text accepted by the backend. SQLite keeps path, source
hash, normalized dedupe hash, URL/provenance, timestamp, and prior-snapshot reference.

ApprovedRevision content includes immutable structured JSON and Markdown projection.
HTML, PDF, screenshot, claim manifest, decision/provenance export, and sanitized
provider response are separate registered artifacts where applicable.

### 6.3 Knowledge files

Facts, CandidateContext, Profiles, selection/emphasis policy, prompts, task contracts,
rendering rules, and templates remain file-backed and version-controlled. SQLite audit
does not become an alternative Knowledge source of truth. The product never runs Git
commit automatically.

## 7. UnitOfWork and consistency

Commands that mutate several SQLite tables execute through a UnitOfWork:

```python
with uow:
    ...
    uow.commit()
```

Services do not own global connections or call SQLite transaction primitives directly.
Each worker/request obtains an appropriate connection/UnitOfWork. Queries use
purpose-built projections and may use efficient joins without hydrating complete
aggregates.

State tables are authoritative current projections. Append-only events provide audit
and provenance; the system is not event-sourced.

### 7.1 Ordinary immutable payload commit

The normal artifact protocol is:

`write temp -> validate -> hash -> atomic rename -> register in SQLite`

Before registration, the artifact is invisible to normal queries. If registration
fails, reconciliation sees a safe orphan. A full journal is not required where orphan
reconciliation provides deterministic safety and no active state can reference the
file.

### 7.2 Knowledge mutation journal

Knowledge changes cross a file source of truth and SQLite audit/relationships, so they
use a narrow durable journal:

1. Validate the complete command and proposed Knowledge file.
2. Stage the new file.
3. Persist a `PREPARED` journal entry with old/new hashes and paths, staged path, DB
   mutation identity, and recovery strategy.
4. Atomically replace the Knowledge file.
5. Commit audit, attachment, SelectionPlan, and related SQLite state.
6. Mark the journal entry `COMMITTED`.

Startup recovery must decide from durable hashes and identities whether to finish or
restore. It never guesses. An unrecoverable state is explicitly quarantined.

Normal queries only expose `COMMITTED` state. Quarantine blocks additional promotions
and approval dependent on unreconciled Knowledge. It does not block history reads,
historical exports, or recruitment tracking.

## 8. Domain lineage and provenance

Commands always receive explicit source IDs. `latest` belongs to query/UI convenience,
not command semantics:

```python
analyze_job(application_id, job_snapshot_id)
create_draft(application_id, analysis_id, selection_plan_id)
approve_draft(working_draft_id, expected_version, validation_run_id)
render_revision(approved_revision_id)
```

WorkingDraft records source analysis and SelectionPlan. An edit from an approved
revision also records `parent_revision_id`. ApprovedRevision freezes Application,
JobSnapshot, JobAnalysis, SelectionPlan, Draft content/version/hash, CandidateContext,
facts and Knowledge dependencies, policy versions, validation, and decision provenance.

The global Knowledge-store version is coarse audit/detection. Exact `knowledge_context`
hashes determine dependency staleness. SelectionPlan additionally freezes candidate
fact IDs/hashes, Profile, selection policy, and Track/Emphasis dependencies. An
unrelated fact change does not invalidate every draft.

Ready is computed, never stored as a second revision type. An ApprovedRevision becomes
`ready_qualified` when its exact HTML/PDF/visual artifacts exist, render/PDF/ATS
validation passes, and current integrity verification passes. This projection is
independent of the active context but may become false if registered artifacts are
missing or corrupt. `PreparationState=ready` additionally requires compatibility with
the active JobSnapshot + JobAnalysis, and
`latest_ready_revision_id` is an ApprovedRevision ID.

Ready remains compatible across a new SelectionPlan/WorkingDraft under the same
JobSnapshot + JobAnalysis. A new snapshot or analysis demotes it only for the active
context; the immutable revision remains historical and downloadable.

## 9. Application services and action policy

Application services return Pydantic boundary DTOs. They enforce domain preconditions,
load all explicit sources, call ports, record audit, and commit one outcome. They do not
return database rows or paths.

The action-policy projector computes PreparationState, WorkingDraftState, warnings,
review reasons, stale reasons and primary reason, active Operation, available actions,
blocked actions and reason codes, nullable recommended action, active-context IDs,
milestone IDs, and `newer_draft_in_progress` in one consistent read transaction.

API and CLI consume this policy. React does not duplicate it.

## 10. Operation runner

Operation is an application/infrastructure concern, not the central domain aggregate.
The Operation runner has two hosts but one execution contract. Under `cv web`,
lightweight worker loops run inside the supervised local backend process, poll/claim
SQLite rows atomically, and execute jobs outside requests. A standalone CLI command
that creates an Operation attempts to claim that row and runs it in the foreground in
the CLI process with the same leases, heartbeat, resource locks, cancellation,
idempotency, and optimistic activation checks. If another eligible runner claims the
same row first, the CLI observes that one Operation through its terminal outcome rather
than duplicating it. It does not require FastAPI or a running Web server. Neither host
is a separately deployed service or requires Celery/Redis.

Default limits are:

- one mutating Operation per Application
- one global render/browser Operation
- two concurrent AI Operations

Locks are resource-specific. Render for one Application does not block analysis for
another.

Contention for the global render/browser slot is queueing, not an immediate failure. A
CLI foreground render remains queued with an observable `waiting_for_render_slot`
phase and waits/polls the same durable Operation until an eligible runner claims it or
the user cancels/interruption policy applies. It never starts a duplicate render merely
because a Web worker owns the current global lease.

Operation records contain type, full secret-free structured payload and hash,
idempotency key, provider/model, source IDs, expected versions/hashes, lifecycle
timestamps, lease owner/expiry, heartbeat, cancellation request, phase/message,
failure code, safe message, technical detail/log reference, retry reference, and output
references.

Startup changes queued/running rows with expired leases to `interrupted`; it does not
resume an external call. Graceful shutdown stops claiming, requests cancellation or
waits briefly, stops heartbeat, and leaves durable state for recovery.

Commit checks run before execution and before activation. `SOURCE_CHANGED` preserves
any immutable output as inactive evidence and fails the Operation without replacing the
WorkingDraft.

Queued cancellation is immediate. Running cancellation is best effort and cancels
activation. Retry creates another immutable Operation. One automatic retry with a small
exponential delay is allowed only for classified transient timeout/network/429/5xx or
temporary browser-startup failures.

## 11. AI adapter

The existing provider-neutral protocol is retained and expanded only for the five v2
tasks. The OpenAI adapter uses the Responses API and strict Structured Outputs. It
returns task-specific Proposal DTOs and provider provenance; it cannot save domain
state.

Each task receives minimal allowed context. Provider text and fact IDs pass schema and
semantic support validation. A valid ID paired with strengthened wording fails. Claims
are not silently dropped.

Calls are stateless. Default model and per-task overrides are backend configuration.
Exact model/provider, semantic task-contract version, prompt version/hash, input/output
schema versions, usage, latency, response ID, and output hashes are stored.

Sanitized raw response is an immutable filesystem artifact. Sanitization removes
secrets and excludes hidden chain-of-thought. Provider failure is explicit; deterministic
continuation requires another user-selected command.

## 12. HTTP API

The API prefix is `/api/v1`. Product v2 and API v1 are intentionally separate version
spaces.

Resources include Applications, JobSnapshots, analyses, SelectionPlans, WorkingDrafts,
validations, ApprovedRevisions, artifacts, Operations, submissions, and contextual
facts. True use-cases use action endpoints such as validate, approve, render, cancel,
and retry rather than artificial CRUD.

Asynchronous commands return `202 Accepted` plus an Operation Location. Synchronous
creation returns `201 Created`. SelectionPlan creation is `201` in deterministic mode
and `202` with a Location when AI proposal mode is requested. NeedsReview and failed
validation are successful domain outcomes.

API schemas are separate from domain and persistence types. OpenAPI is generated and
validated; TypeScript types are generated and checked for drift. A small handwritten
`apiClient.ts` owns HTTP mechanics.

WorkingDraft responses emit ETags. PATCH requires If-Match and maps to the application's
expected version. Version mismatch is `409`; stale/missing domain prerequisites are
`412`. Analyze, generate, approve, and render accept idempotency keys scoped by
installation + operation type + key. Reuse with another payload hash is
`409 IDEMPOTENCY_KEY_REUSED`.

Problems follow RFC-style Problem Details with stable code and safe context. Internal
technical details remain in structured rotating logs.

Artifact endpoints accept IDs only, verify path root containment and symlink safety,
and stream/download registered content with a friendly filename. Body size is bounded;
oversize is `413`.

## 13. Frontend architecture

Production React assets are built ahead of time and served by FastAPI under the same
origin. Node is not a user runtime dependency. Development Vite proxies `/api` to
FastAPI and only its configured origin is allowed.

TanStack Query owns server state and polling. React Hook Form owns local forms.
Component/local state owns transient editor dialogs and save-conflict UI. No Redux or
client-side workflow state machine is introduced.

The UI is Hebrew and its shell is RTL. CV language is independent. URLs, hashes,
technical identifiers, and code-like values use explicit LTR direction. HTML preview
is rendered by the backend and shown in an isolated iframe.

Operation progress is polled every one to two seconds while active and shows status,
phase, safe message, and timestamps. No synthetic percentages are displayed.

Autosave uses debounce and blur. A 409 opens an explicit local/current comparison and
never silently merges.

## 14. Local security

The production service binds to `127.0.0.1`, serves UI/API same-origin, disables
wildcard CORS, and validates Origin for mutation. Development allows only the exact Vite
origin. v2.0 has no authentication and no CSRF token.

The OpenAI key remains environment/backend secret configuration. React sees only a
configured boolean. Logs and Operation payloads are redacted and never contain keys,
authorization headers, or secrets.

Job/user text is untrusted. Prompt contracts isolate it from policy. Artifact access
prevents traversal and symlink escape. No endpoint accepts arbitrary local paths or
arbitrary file uploads.

## 15. Runtime behavior

`cv web` defaults to `127.0.0.1:8765`, opens the default browser, and supports
`--no-open`. It probes a health/identity endpoint to determine whether the existing port
belongs to the same installation and Workspace. If so it opens that instance; if a
foreign process owns the port it selects and reports another free port.

Production supports current Chrome/Chromium and Safari. Full E2E uses Chromium;
central-flow smoke tests use WebKit. Resume PDF rendering always uses the managed
Chromium configured by Playwright. Local Chrome is diagnostic only.

Structured rotating logs under `logs_root` include timestamp, level, Operation ID,
Application ID, phase, error code, and log reference. v2.0 offers an Open Logs Folder
action rather than a logs screen.

## 16. Backup and upgrade

`cv workspace backup` captures SQLite, Knowledge, immutable snapshots/revisions/
artifacts, Workspace marker/config needed to restore, and a manifest with hashes.
`cv workspace verify-backup` verifies the archive. Acceptance additionally restores to
a temporary directory, opens the restored Workspace, and reconciles it.

Upgrade is explicit:

`backup -> verify -> compatibility check -> migration -> integrity check -> launch`

There is no auto-update. A new binary/runtime never performs a hidden live data
migration.

## 17. Version surfaces

Provenance and compatibility track at least:

- product version
- database schema version
- domain document version
- API version
- Knowledge schema/version
- CandidateContext version/hash
- selection policy version
- rendering policy version
- task-contract semantic version
- prompt version/hash
- input/output schema versions
- validator versions

Versions may be per artifact/task rather than one global constant. Product version does
not substitute for these surfaces.

## 18. Architecture transition from v1

M1 introduces boundaries around the existing behavior before FastAPI/React. Current
validators and deterministic generation remain authoritative while orchestration leaves
`Engine`. The CLI moved first, to prove the application layer independently.

M2 supplies storage, operations, projections, action policy, and recovery foundations.
M3 exposes the vertical slice through thin HTTP endpoints. M4 builds UI on the proven
Application API. Dashboard work is gated until the API and Web complete one Application
through Ready including central failure paths.

No v2 implementation begins until the v2 specification set is approved and repository
authority instructions are updated to permit the v2 scope.
