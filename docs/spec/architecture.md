# v2.0 Architecture

Status: **Approved for v2.0 implementation (2026-08-17)**

PostgreSQL/object-storage, secret-configuration, and fixed-root amendment: **2026-08-25**

Product authority: `docs/spec/product-spec.md`

Baseline: `v1.0.0` / `2cc31c7`

## 1. Architecture objective

The product runs over one synchronous application layer. Two processes call that
layer, and the distinction between them is what the rest of this document assumes:

- **FastAPI is the only user-facing adapter.** Every user action arrives through it, and
  React reaches the application layer through the API and nowhere else.
- **The worker is an internal execution host.** It calls the same application layer
  directly, through the Operation runner, and serves no user. It is not a second client
  for any use-case: it executes Operations the API created.

A second user-facing adapter is what this rule excludes. Existing domain and validation
behavior is preserved and separated from orchestration, storage, and transport
concerns.

The primary architecture rule is:

`domain <- application <- infrastructure / api / runtime`

Dependencies point inward. Product semantics live in domain/application code, not in
routers, React components, SQL triggers, or templates.

There is one user-facing adapter. A second surface for a use-case the API already owns
has a second contract to keep compatible and no capability the first lacks.

## 2. Required technology baseline

Backend/runtime:

- Python 3.11+
- Pydantic for serialized domain documents, AI contracts, application boundary DTOs,
  and HTTP schemas
- FastAPI for the local HTTP API and production static-asset serving
- Uvicorn as the supervised loopback ASGI server
- PostgreSQL 17 for structured state and relationships
- SQLAlchemy 2.0 Core for database access; no ORM Session or mapped entities
- psycopg 3 as the PostgreSQL driver
- Alembic for explicit numbered schema revisions
- Jinja2 for resume HTML
- Playwright-managed Chromium for rendering and render validation
- `pypdf` for PDF extraction and ATS checks
- `boto3`, in the optional `s3` extra only, for the S3/R2 payload backend. Optional
  because the local store is the default: the deterministic workflow must reach Ready
  with nothing configured and no cloud SDK installed, so it is imported inside the
  adapter rather than at module scope

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
- Playwright browser tests over the built frontend
- axe checks on the screens those tests cover, through `@axe-core/playwright`

Redux, a full component framework, Celery, Redis, WebSockets, SSE, and a DI framework are
not part of the product.

## 3. Source organization

The top-level package organization is:

```text
cv_engine/
  domain/
  application/
  infrastructure/
  api/
  worker/
  runtime/
frontend/
```

Subpackages are introduced only when the amount and cohesion of code justify them.
There is no one-file-per-interface rule and no micro-packaging objective.

### 3.1 Domain

The domain owns entities, value objects, lifecycle rules, validation semantics,
transition rules, knowledge/fact safety, Ready qualification, and invariant checks. It
does not import FastAPI, SQLAlchemy, psycopg, filesystem paths, Playwright, React concepts,
provider HTTP code, or runtime configuration.

Pydantic remains appropriate for DraftDocument and other serialized domain documents.
Small internal value objects may be dataclasses when serialization is not a boundary.

### 3.2 Application

The application layer owns explicit commands, queries, services, ports, UnitOfWork
boundaries, permissions/action policy, state projections, optimistic commit checks,
and conversion of validated Proposals into domain state.

Services are synchronous. The layer has no dependency on FastAPI or an event loop.

Focused services are:

- `ApplicationService`
- `ApplicationQueryService`
- `AnalysisService`
- `DraftService`
- `RenderingService`
- `TrackingService`
- `KnowledgeService`
- `OperationService`
- `SettingsService`
- `MaintenanceService`

A small façade may compose them for convenience but contains no business logic.

### 3.3 Infrastructure

Infrastructure implements SQLAlchemy Core repositories, PostgreSQL UnitOfWork,
local/S3-compatible object stores, KnowledgeRepository, OpenAI provider, rendering, operation
claiming/execution, logging, and Alembic integration.

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

### 3.4 API

FastAPI routers map HTTP DTOs, headers, and application errors to use-cases and
responses. They do not load Profiles, select facts, call providers, validate claims,
calculate fit, or write history directly.

Maintenance is an API concern like any other. Reconciliation is
`POST /api/v1/maintenance/reconciliations` behind a `MaintenanceService`, which holds
the payload store and repository directly - `ApiServices` carries neither, so this
cannot be a router helper. CSV export is a function of the application layer with no
route, because writing the file is not yet a product use-case.

Every product use-case belongs to the API and the Web UI. A second surface for a
use-case the API owns has a second contract to keep compatible and no capability the
first lacks.

The v1 `Engine` compatibility façade was removed once the clients called the
application services directly. It was never a v2 architectural boundary, and no code
refers to it.

### 3.5 Runtime and composition

`cv_engine/runtime/composition.py` is the manual composition root. It builds fixed application paths,
configuration, repositories, UnitOfWork factory, services, provider, renderer,
operation worker, and API dependencies. No DI framework is used.

The system runs as two processes over one database, and neither supervises the other:

- `uvicorn cv_engine.runtime.asgi:app` serves HTTP. It starts no background work, so an app
  lifespan never spawns a worker per test client.
- `python -m cv_engine.worker` claims queued Operations under a lease.

A worker that dies leaves its claims to expire, and the next worker's
`recover_startup()` reclaims them. That lease is what makes the split safe.

FastAPI remains a Web server and does not become a process manager.

## 4. Application paths

The runtime uses the repository root as the single application root. There is no root
selector, marker, initialization command, or per-root identity. `AppPaths` supplies:

```text
knowledge_root
artifacts_root
temp_root
logs_root
```

All mutable and immutable local paths remain contained below that root. Tests inject a
temporary root directly into composition; the running processes do not expose that
injection surface. Nothing points v2 at v1. The archive is read by a person with a text
editor or `git worktree add`, never by this engine.

## 5. CandidateContext

One CandidateContext is loaded from Knowledge. It references canonical name/contact
fact IDs and defines filename/display policy, timezone, and locale. It carries its own
version/hash for provenance.

Application rows do not contain `candidate_id`. ApprovedRevision metadata records the
CandidateContext version/hash used. Renderers and filename policy take CandidateContext
as an explicit dependency, eliminating candidate literals from code.

Existing semantic fact IDs are preserved. New facts use UUIDv4 technical identity;
a human slug is optional metadata and never a foreign key.

Knowledge dependencies are re-read or re-hashed before relevant commands. Manual edits
to the source files remain valid inputs; a changed context produces `knowledge_changed` or
`SOURCE_CHANGED` and is never silently loaded into an open editor form.

## 6. Persistence boundary

### 6.1 PostgreSQL

PostgreSQL stores structured state and relationships:

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
- schema metadata

The database is addressed by the resolved `database_url` setting (`CV_DATABASE_URL` in
environment and `.env` surfaces), not by a local database path. One process-wide SQLAlchemy
`Engine` per URL owns pooling and connection health. UnitOfWork and multi-query projection
reads use explicit transactions; stable projections use `REPEATABLE READ`.

Foreign keys and CHECK/UNIQUE constraints enforce relational invariants. Every
immutable table carries an UPDATE guard and a DELETE guard, and which tables those are
is derived rather than listed: a table is immutable unless it is named in the mutable
exception set, so adding a table without its guards fails the check instead of passing
unnoticed. Application `current_status` validity is one CHECK constraint, which covers
both INSERT and UPDATE. Business workflows remain in domain/application code.

Alembic owns explicit numbered revisions, schema version metadata, and schema upgrades.
The revision graph has one head, `alembic upgrade head` applies it explicitly, and normal
runtime composition does not perform hidden migrations as a startup side effect.

### 6.2 Object storage

Immutable/heavy payloads sit behind `ObjectStore`, which speaks keys and bytes and
carries no `Path`. Two implementations satisfy it: `LocalObjectStore`, the default,
which maps a key onto a file under `{artifacts_root}`; and `S3ObjectStore`, which puts
it in an S3-compatible bucket (R2 and MinIO via `endpoint_url`). The composition root
selects one from `CV_OBJECT_STORE`; `PayloadStore` never branches on the backend.

The key layout is the same either way:

```text
{artifacts_root}/ or {bucket}/{prefix}/
  snapshots/{application_id}/{snapshot_id}.txt
  revisions/{application_id}/{revision_id}/resume.json
  revisions/{application_id}/{revision_id}/resume.md
  drafts/{application_id}/{working_draft_id}-v{edit_version}.json
  outputs/{application_id}/{revision_id}/{artifact_id}.html
  outputs/{application_id}/{revision_id}/{artifact_id}.pdf
  outputs/{application_id}/{revision_id}/{artifact_id}.png
  provider/{application_id}/{operation_id}/{artifact_id}.json
  manifests/{manifest_id}.json
```

**References are storage-neutral and their format is frozen.** PostgreSQL path fields,
including `job_snapshots.payload_path`, the ApprovedRevision resume paths, and
`artifact_versions.path`, store project-relative strings such as
`artifacts/snapshots/{app}/{id}.txt`; an object key is the same string without the
`artifacts/` prefix. A row is identical under either backend, so storage can change
without rewriting database rows.

Key validation is shared by both implementations rather than delegated to each. A
crafted key - traversal, absolute, empty segment, backslash, drive prefix - is refused
identically, because a payload's address must not depend on which backend is
configured. "S3 has no `..`" is not a reason to skip the check.

Three things stay on the local filesystem by decision: the mutable `artifacts/working/` draft,
which is rewritten on every autosave and is not an immutable record; `RenderTargets`,
because Chromium writes real files to real paths and cannot write to a bucket; and
Knowledge sources, which are version-controlled inputs rather than artifacts.

A rendered output is the one payload family that reaches storage as a location rather
than as bytes. The store decides where it is written: on the local store that is the
artifact path itself, so the rendered file *is* the stored object; on a remote store it
is scratch under `{temp_root}/render/`, uploaded and then removed. Deleting the render
location is correct in the second case and would destroy the payload in the first,
which is why the store answers the question rather than the caller.

Additional manifests use immutable UUID-based names. Every payload has SHA-256 metadata
in PostgreSQL. Recruiter-friendly names are Content-Disposition/export names, never the
physical identity of an artifact. There is no `latest.pdf` artifact.

JobSnapshot source is the exact text accepted by the backend. PostgreSQL keeps path, source
hash, normalized dedupe hash, URL/provenance, timestamp, and prior-snapshot reference.

ApprovedRevision content includes immutable structured JSON and Markdown projection.
HTML, PDF, screenshot, claim manifest, decision/provenance export, and sanitized
provider response are separate registered artifacts where applicable.

### 6.3 Knowledge files

Facts, CandidateContext, Profiles, selection/emphasis policy, prompts, task contracts,
rendering rules, and templates remain file-backed and version-controlled. Database audit
does not become an alternative Knowledge source of truth. The product never runs Git
commit automatically.

## 7. UnitOfWork and consistency

Commands that mutate several PostgreSQL tables execute through a UnitOfWork:

```python
with uow:
    ...
    uow.commit()
```

Services do not own global connections or call driver transaction primitives directly.
Each worker/request obtains an appropriate SQLAlchemy Connection/UnitOfWork. Queries use
purpose-built projections and explicit joins without hydrating ORM entities.

State tables are authoritative current projections. Append-only events provide audit
and provenance; the system is not event-sourced.

### 7.1 Ordinary immutable payload commit

The normal artifact protocol is:

`validate bytes -> conditional store under key -> register in PostgreSQL`

There is no temp-then-rename staging. Validation runs on the bytes before the key is
claimed, so a payload that fails it never occupies its destination - which is what temp
staging bought, without the temp file. The write itself refuses to replace an existing
payload: `O_EXCL` locally, a conditional PUT (`IfNoneMatch: "*"`) on S3 and R2. That
also closes the window an `exists()` check followed by a rename left open.

The hash is computed by the store over the bytes it stored, in the same read, and is
what the caller registers. Re-hashing the payload afterwards would describe a second
read rather than the stored object.

Before registration, the artifact is invisible to normal queries. If registration
fails, reconciliation sees a safe orphan. A full journal is not required where orphan
reconciliation provides deterministic safety and no active state can reference the
payload.

### 7.2 Knowledge mutation journal

Knowledge changes cross a file source of truth and PostgreSQL audit/relationships, so they
use a narrow durable journal:

1. Validate the complete command and proposed Knowledge file.
2. Stage the new file.
3. Persist a `PREPARED` journal entry with old/new hashes and paths, staged path, DB
   mutation identity, and recovery strategy.
4. Atomically replace the Knowledge file.
5. Commit audit, attachment, SelectionPlan, and related PostgreSQL state.
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
analyze_job(application_id, job_snapshot_id, provider)
create_draft(application_id, job_analysis_id, selection_plan_id, provider)
approve_draft(working_draft_id, expected_edit_version, validation_run_id)
render_revision(application_id, approved_revision_id)
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

The API consumes this policy. React does not duplicate it.

## 10. Operation runner

Operation is an application/infrastructure concern, not the central domain aggregate.
The worker process is the one host: it runs lightweight loops that poll and claim
PostgreSQL rows atomically and execute jobs outside requests, under leases, heartbeat,
resource locks, cancellation, idempotency, and optimistic activation checks.

The claim contract does not assume a single claimer. Two workers may run: whichever
claims a row first owns it, and the other observes that Operation through its terminal
outcome rather than duplicating it. That is what makes the worker safe to run in more
than one copy. It requires neither Celery nor Redis.

Default limits are:

- one mutating Operation per Application
- one global render/browser Operation
- two concurrent AI Operations

Locks are resource-specific. Render for one Application does not block analysis for
another.

Contention for the global render/browser slot is queueing, not an immediate failure. A
render waiting for the slot stays queued with an observable `waiting_for_render_slot`
phase until an eligible runner claims it or the user cancels. It never starts a
duplicate render merely because another runner owns the current global lease.

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

The existing provider-neutral protocol is retained and expanded only for the five
tasks. The OpenAI adapter uses the Responses API and strict Structured Outputs. It
returns task-specific Proposal DTOs and provider provenance; it cannot save domain
state.

Each task receives minimal allowed context. Provider text and fact IDs pass schema and
semantic support validation. A valid ID paired with strengthened wording fails. Claims
are not silently dropped.

Calls are stateless. Default model and per-task overrides are backend configuration.
Exact model/provider, semantic task-contract version, prompt version/hash, input/output
schema versions, usage, latency, response ID, and output hashes are stored.

Sanitized raw response is an immutable payload in the object store, registered like
any other. Sanitization removes secrets and excludes hidden chain-of-thought. Provider failure is explicit; deterministic
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
validated; TypeScript types are generated and checked for drift. The small handwritten
`frontend/src/api/client.ts` module owns HTTP mechanics.

WorkingDraft responses emit ETags. PATCH requires If-Match and maps to the application's
expected version. Version mismatch is `409`; stale/missing domain prerequisites are
`412`. Analyze, generate, approve, and render accept idempotency keys scoped by
operation type + key. Reuse with another payload hash is
`409 IDEMPOTENCY_KEY_REUSED`.

Problems follow RFC-style Problem Details with stable code and safe context. Internal
technical details remain in structured rotating logs.

Artifact endpoints accept IDs only. They resolve a registered reference, verify the
stored content hash, and stream it with a friendly filename. Containment is the
backend's: `LocalObjectStore` keeps every key below `artifacts_root` and refuses
traversal and symlink escape; `S3ObjectStore` has neither paths nor symlinks and
validates the key. Nothing above the store handles a filesystem path. Body size is
bounded; oversize is `413`.

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
phase, safe message, failure guidance, and the actions returned by the backend. No
synthetic percentages are displayed, and there is no separate Operation route.

Autosave uses debounce and blur. A 409 opens an explicit local/current comparison and
never silently merges.

## 14. Local security

The production service binds to `127.0.0.1`, serves UI/API same-origin, disables
wildcard CORS, and validates Origin for mutation. Development allows only the exact Vite
origin. The application has no authentication and no CSRF token.

The OpenAI key remains environment/backend secret configuration. React sees only a
configured boolean. Logs and Operation payloads are redacted and never contain keys,
authorization headers, or secrets.

Job/user text is untrusted. Prompt contracts isolate it from policy. Artifact access
resolves registered references only -- never a caller-supplied location -- and the
local backend additionally prevents traversal and symlink escape. No endpoint accepts
arbitrary local paths or arbitrary file uploads.

## 15. Runtime behavior

The API defaults to `127.0.0.1:8765`. The port is uvicorn's to bind, but the app must
also be told it, through `CV_API_PORT`: the origin policy allows the origin the app
believes it answers on, so a port given only to uvicorn refuses every state-changing
request from the app's own UI.

Production supports current Chrome/Chromium, and the browser tests run there. Resume
PDF rendering always uses the Chromium managed by Playwright. Local Chrome is
diagnostic only.

Structured rotating logs under `logs_root` include timestamp, level, Operation ID,
Application ID, phase, error code, and log reference. There is no logs screen: a log
reference identifies the entry, and the files are read directly on the host.

The two process consoles provide concise lifecycle visibility. The API logs startup,
shutdown, and one terminal line per HTTP request with method, path, status, and duration.
The worker logs claims, retries, terminal outcomes, startup recovery, and shutdown. The
complete structured streams are rotating `server.jsonl` and `operations.jsonl` files
under `logs_root`; exception details and tracebacks are file-only. Empty queue polling,
heartbeat traffic, HTTP query strings, headers, and bodies are not logged.

### 15.1 Runtime configuration and secrets

`cv_engine/runtime/config.py` is the single resolution contract. Precedence is:

`process environment > project .env file > project config > default`

Only the repository-root `.env` is considered. Real environment variables override
stale developer files. The supported `.env` syntax is the
small documented `KEY=value` subset, implemented without an additional dependency.

Each setting declares whether it is secret or environment-only.
`database_url` is secret. `OPENAI_API_KEY` is both secret and environment-only, so an
`unset OPENAI_API_KEY` reliably disables the OpenAI adapter even when a `.env` exists.
AWS credentials remain ambient boto3 configuration rather than values copied through
the application contract.

Masking occurs only at display/reporting boundaries. Any API, log, or error surface that
reports a configuration value must show `***` for a configured secret while preserving
the non-secret source label, and unset secrets
remain visibly unset. Connectors always receive the original value, never the masked
representation. `.env` and `.env.*` are ignored by Git, while `.env.example` is the
committed safe inventory of supported variables.

## 16. Database lifecycle and upgrade

The application has no built-in backup or restore command. PostgreSQL lifecycle and any
environment-level backup policy remain outside the application; this development-only
replacement starts from an empty database and does not migrate historical data.

Schema upgrade is explicit through `alembic upgrade head`. Runtime surfaces report the
current schema revision and database integrity result; a new binary/runtime never
performs a hidden live data migration.

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
