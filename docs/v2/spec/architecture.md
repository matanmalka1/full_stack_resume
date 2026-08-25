# v2.0 Architecture

Status: **Approved for v2.0 implementation (2026-08-17)**

PostgreSQL/object-storage, secret-configuration, and fixed-root amendment: **2026-08-25**

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
- Playwright Web E2E
- axe checks on the central screens, through `@axe-core/playwright`

Redux, a full component framework, Celery, Redis, WebSockets, SSE, and a DI framework are
not part of v2.0.

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
- `AnalysisService`
- `DraftService`
- `RenderingService`
- `TrackingService`

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

`runtime/composition.py` is the manual composition root. It builds fixed application paths,
configuration, repositories, UnitOfWork factory, services, provider, renderer,
operation worker, and API dependencies. No DI framework is used.

`cv web` is a supervisor responsible for schema gates,
process/port detection, worker lifecycle, browser launch, and graceful shutdown.
FastAPI remains a Web server and does not become the installation/process manager.

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
temporary root directly into composition; production CLI commands do not expose that
injection surface. Nothing points v2 at v1. The archive is read by a person with a text
editor or `git worktree add`, never by this engine.

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

Foreign keys and CHECK/UNIQUE constraints enforce relational invariants. The 36 row
triggers comprise 28 UPDATE/DELETE guards over 14 immutable tables, four DELETE-only
guards over deliberately mutable tables, and four exact transition guards. Application
`current_status` validity is one CHECK constraint, which covers both INSERT and UPDATE.
Business workflows remain in domain/application code.

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
  outputs/{application_id}/{revision_id}/{artifact_id}.html
  outputs/{application_id}/{revision_id}/{artifact_id}.pdf
  outputs/{application_id}/{revision_id}/{artifact_id}.png
  provider/{application_id}/{operation_id}/{artifact_id}.json
```

**References are storage-neutral and their format is frozen.** `artifact_versions`
stores a project-relative string (`artifacts/snapshots/{app}/{id}.txt`); an object key
is the same string without the `artifacts/` prefix. A row is identical under either
backend, so storage can change without rewriting database rows.

Key validation is shared by both implementations rather than delegated to each. A
crafted key - traversal, absolute, empty segment, backslash, drive prefix - is refused
identically, because a payload's address must not depend on which backend is
configured. "S3 has no `..`" is not a reason to skip the check.

Three things stay on the local filesystem by decision: the mutable `working/` draft,
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
PostgreSQL rows atomically, and execute jobs outside requests. A standalone CLI command
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
operation type + key. Reuse with another payload hash is
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
is a compatible CV application. If so it opens that instance; if a
foreign process owns the port it selects and reports another free port.

Production supports current Chrome/Chromium and Safari. Full E2E uses Chromium;
central-flow smoke tests use WebKit. Resume PDF rendering always uses the managed
Chromium configured by Playwright. Local Chrome is diagnostic only.

Structured rotating logs under `logs_root` include timestamp, level, Operation ID,
Application ID, phase, error code, and log reference. v2.0 offers an Open Logs Folder
action rather than a logs screen.

### 15.1 Runtime configuration and secrets

`runtime/config.py` is the single resolution contract. Precedence is:

`CLI > process environment > project .env file > project config > default`

Only the repository-root `.env` is considered. Real environment variables override
stale developer files. The supported `.env` syntax is the
small documented `KEY=value` subset, implemented without an additional dependency.

Each setting declares whether it is secret or environment-only.
`database_url` is secret. `OPENAI_API_KEY` is both secret and environment-only, so an
`unset OPENAI_API_KEY` reliably disables the OpenAI adapter even when a `.env` exists.
AWS credentials remain ambient boto3 configuration rather than values copied through
the application contract.

Masking occurs only at display/reporting boundaries. Any CLI/API/log/error surface that
reports a configuration value must show `***` for a configured secret while preserving
the non-secret source label, and unset secrets
remain visibly unset. Connectors always receive the original value, never the masked
representation. `.env` and `.env.*` are ignored by Git, while `.env.example` is the
committed safe inventory of supported variables.

## 16. Database lifecycle and upgrade

v2.0 has no built-in backup or restore command. PostgreSQL lifecycle and any
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
