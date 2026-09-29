# Architecture

Product authority: `docs/spec/product-spec.md`. State, command, error, and HTTP
contracts: `docs/spec/state-and-use-cases.md`. This document owns what neither of those
does: layer boundaries, storage, transactions, the Operation runner, security, and
runtime. Where a topic is owned elsewhere it is linked, not restated. Section numbers are
cited from code and other specifications; keep them stable.

## 1. Architecture objective

One synchronous application layer, called by two processes:

- **FastAPI is the only user-facing adapter.** Every user action arrives through it.
  React reaches the application layer through the API and nowhere else.
- **The worker is an internal execution host.** It calls the same application layer
  through the Operation runner and serves no user. It executes Operations the API
  created; it is not a second client for any use-case.

A second user-facing surface for a use-case the API already owns is not added: it would
be a second contract to keep compatible with no capability the first lacks.

The dependency rule is:

`domain <- application <- infrastructure / api / runtime`

Dependencies point inward. `runtime` imports `api`; `api` never imports `runtime`.
Product semantics live in domain and application code, not in routers, React
components, SQL triggers, or templates.

## 2. Technology baseline

This is the dependency baseline. A new dependency is added only when it enforces a
contract, reduces rendering risk, or gives a concrete portability benefit. Exact
versions live in `pyproject.toml` and `frontend/package.json`.

Backend:

- Python 3.11+
- Pydantic 2 for serialized domain documents, AI contracts, boundary DTOs, and HTTP
  schemas
- FastAPI for the HTTP API and production static-asset serving; Uvicorn as the ASGI
  server
- PostgreSQL 17, through SQLAlchemy 2.0 Core (no ORM Session or mapped entities) and
  psycopg 3
- Alembic for explicit numbered schema revisions
- Jinja2 for resume HTML; Playwright-managed Chromium for rendering and render
  validation; `pypdf` for PDF extraction and ATS checks
- `boto3`, in the optional `s3` extra only, imported inside the adapter so the local
  path — which must reach Ready from an existing analysis with nothing configured —
  never needs it
- Tooling: pytest, pytest-cov, ruff, pyright (`basic`, which checks that adapters
  structurally satisfy their Protocol ports)

Frontend:

- React, TypeScript, Vite, React Router, TanStack Query, React Hook Form, Tailwind CSS,
  `lucide-react`
- TypeScript types generated from the committed OpenAPI schema (`openapi/`)
- Tooling: Vitest, Playwright with axe, oxlint, Prettier, knip, the design-token check
- An accessible headless primitive library (Radix) may be added selectively when a
  complex accessible primitive is warranted; none is installed

Redux, a full component framework, Celery, Redis, WebSockets, SSE, a DI framework, and
`python-dotenv` are not part of the product.

## 3. Source organization

```text
cv_engine/
  domain/           entities, value objects, validation, selection, lifecycle rules
  application/      commands, queries, ports, services, action policy, Operation runner
  infrastructure/   persistence adapters, object stores, Knowledge, provider, renderer
  api/              routers, schemas, middleware
  runtime/          composition root, config, paths, ASGI app, worker pool
  worker/           `python -m cv_engine.worker`
frontend/           React application (`frontend/src/features/README.md`)
openapi/            generated schema and TypeScript types
alembic/            schema revisions
```

Subpackages are introduced only when the amount and cohesion of code justify them.
There is no one-file-per-interface rule.

### 3.1 Domain

The domain owns entities, value objects, lifecycle rules, validation semantics,
transition rules, fact safety, selection, claim-review evidence checks, Ready
qualification, and invariant checks. It does not import FastAPI, SQLAlchemy, psycopg,
filesystem paths, Playwright, provider HTTP code, or runtime configuration.

Serialized domain documents are Pydantic models. Small internal value objects may be
dataclasses when serialization is not a boundary.

### 3.2 Application

The application layer owns commands, queries, services, ports, transaction boundaries,
action policy, state projections, optimistic commit checks, and conversion of validated
Proposals into domain state. Services are synchronous, have no dependency on FastAPI or
an event loop, and follow consumer and lifecycle boundaries (intake and queries,
analysis, selection, document authoring/validation/approval/history, rendering,
recruitment and submission, knowledge, Operations, maintenance, settings).

Services return Pydantic boundary DTOs, never database rows or filesystem paths.

### 3.3 Infrastructure

Infrastructure implements the ports: SQLAlchemy Core persistence, PostgreSQL
transaction scopes, the object stores, file-backed Knowledge, the OpenAI provider,
rendering, structured logging, and Alembic integration.

Persistence ports follow consumer, lifecycle, and trust boundaries rather than tables.
The Operation client port (what the API may do) and the execution port (what the worker
may do) are separate, so API permissions never carry worker authority. There is no
generic workflow-state DTO or persistence container.

Concrete adapters neither inherit, hold, nor call other adapters. They hold no bound
connection and open no transaction: every database method takes an opaque transaction
token explicitly, and writes require a write token. Private SQL helpers may share
statements and record conversion without becoming repository wrappers. Services depend
on ports, never on concrete adapters.

There is no root repository, repository bundle, generic dependency dictionary, `bind()`,
or repository-exposing unit of work. A new port needs a real consumer, lifecycle, or
trust boundary; a one-method port must represent an atomic persistence or external
system boundary. A service with more than seven constructor dependencies needs an
explicit architecture review, not a gateway introduced to shorten its constructor.

### 3.4 API

Routers map HTTP DTOs, headers, and application errors to use-cases and back. They do
not load Profiles, select facts, call providers, validate claims, calculate Fit, or
write history.

The API receives `ApiServices` (`cv_engine/api/services.py`): application services plus
instance identity and transport limits. It carries no store, repository, renderer,
provider, transaction manager, or worker. Anything that needs those — reconciliation
included — is an application service.

CSV export is an application function with no route; writing the file is not a product
use-case yet.

### 3.5 Runtime and composition

`cv_engine/runtime/composition.py` is the manual composition root. `build_services`
wires configuration, one SQLAlchemy engine, one transaction manager, adapters, services,
the Operation runner, and the worker; `build_api_services` narrows that to
`ApiServices`. No DI framework is used. Tests substitute adapters through
`build_services` keyword arguments. Building services also runs Knowledge mutation
recovery (§7.2), so both processes recover before serving.

The system runs as two processes over one database, and neither supervises the other:

- `uvicorn cv_engine.runtime.asgi:app` serves HTTP. It starts no background work, so a
  test client never spawns a worker.
- `python -m cv_engine.worker` recovers startup state, then claims queued Operations
  until SIGINT/SIGTERM.

One worker process runs at a time (§10).

## 4. Application paths

The application root is the installed repository root, computed from the code location
(`runtime/paths.py`). It is not selectable by argument, setting, or environment
variable. A test that needs another root injects `AppPaths.from_root(...)` into
composition.

```text
knowledge_root   = {root}            base/, profiles/, config/, ai/, rendering/
artifacts_root   = {root}/artifacts
temp_root        = {root}/tmp
logs_root        = {root}/logs
```

`artifacts`, `tmp`, and `logs` are created on startup and may not be symlinks. Every
path resolves inside the root.

## 5. CandidateContext

One CandidateContext is loaded from Knowledge. It references canonical name and contact
fact IDs and defines filename/display policy, timezone, and locale, with its own
version and hash for provenance.

Application rows carry no `candidate_id`. A Submission records the CandidateContext
version/hash used for its content. Renderers and filename policy take CandidateContext
as an explicit dependency, so no candidate literal lives in code.

Existing semantic fact IDs are preserved. New facts use UUIDv4 technical identity; a
human slug is optional metadata and never a foreign key.

Knowledge is re-read or re-hashed before commands that depend on it. Manual edits to the
source files are valid inputs; a changed context produces `knowledge_changed` or
`SOURCE_CHANGED` and is never silently loaded into an open editor form.

## 6. Persistence boundary

### 6.1 PostgreSQL

PostgreSQL holds structured state and relationships: Applications and their recruitment
projection, recruitment and audit history, JobSnapshot metadata, JobAnalyses, the one
mutable `cv_documents` row per Application (fields: state-and-use-cases.md §3),
provider-evidence artifacts, Submissions, Operations and their resource leases, fact
events, the Knowledge mutation journal, and safe settings.

The database is addressed by `database_url` (`CV_DATABASE_URL`). Composition creates one
`Engine` (`pool_pre_ping=True`) that owns pooling and connection health. Transaction
scopes run at `REPEATABLE READ`.

Foreign keys and CHECK/UNIQUE constraints enforce relational invariants. Every immutable
table carries an UPDATE guard and a DELETE guard trigger. Which tables are immutable is
derived, not listed: a table is immutable unless it is named in the mutable exception
set (`tests/platform/test_persistence_constraints.py`), so a new table without its guards
fails the check. Tables mutable only through one permitted transition guard their
terminal rows. Business workflows stay in domain and application code.

Alembic owns the schema. The revision graph has one head and is applied explicitly with
`alembic upgrade head`. Composition reads the current revision for reporting and never
migrates as a startup side effect. There is no built-in backup or restore; a fresh
installation starts from an empty database.

### 6.2 Object storage

Immutable payloads sit behind `ObjectStore`, which speaks keys and bytes and carries no
`Path`. `LocalObjectStore` (default) maps a key to a file under `{artifacts_root}`;
`S3ObjectStore` stores it in an S3-compatible bucket (R2 and MinIO through
`CV_S3_ENDPOINT_URL`). Composition selects one from `CV_OBJECT_STORE`; `PayloadStore`
never branches on the backend.

The key layout is the same either way, and `PayloadStore` refuses any other:

```text
{artifacts_root}/ or {bucket}/{prefix}/
  snapshots/{application_id}/{snapshot_id}.txt
  provider/{application_id}/{operation_id}/{artifact_version_id}.json
  submissions/{application_id}/{submission_id}/resume.html
  submissions/{application_id}/{submission_id}/resume.pdf
```

**References are storage-neutral and their format is frozen.** PostgreSQL path fields
store project-relative strings such as `artifacts/snapshots/{app}/{id}.txt`; the object
key is the same string without the `artifacts/` prefix. A row is identical under either
backend, so storage can change without rewriting rows.

Key validation is shared by both implementations. A crafted key — traversal, absolute,
empty segment, backslash, drive prefix — is refused identically, because a payload's
address must not depend on the configured backend.

What stays out of the object store, by decision:

- **Document content** lives inline in `cv_documents.content`; the document has no
  version history to address.
- **Render targets.** `render_document` writes HTML and PDF to a unique per-attempt
  directory, `{artifacts_root}/documents/{application_id}/{attempt_id}/`, and activates
  them as the document's `html_path`/`pdf_path`. Chromium writes real files to real
  paths, and these are mutable working outputs, not immutable records.
- **Knowledge sources** are version-controlled inputs, not artifacts.

A Submission copies the document's `content` inline and its active HTML and PDF into
submission-owned keys, recording a SHA-256 per file. On the local store the copied file
is the stored object; on a remote store the copy is scratch under `{temp_root}`,
uploaded and then removed. The store decides which, because deleting the source location
is correct in one case and destroys the payload in the other.

Every payload has SHA-256 metadata in PostgreSQL. Friendly names are
`Content-Disposition` names, never physical identity. There is no `latest.pdf`.

### 6.3 Knowledge files

Facts, CandidateContext, Profiles, selection/emphasis policy, prompts, task contracts,
requirement concepts, rendering rules, and templates are file-backed and
version-controlled. Database audit is not an alternative Knowledge source of truth. The
product never runs Git commit.

## 7. Transaction ownership and consistency

Application entry points own read and write scopes:

```python
with transactions.write() as tx:
    store.mutate(tx, prepared)
```

A write scope commits once on normal exit and rolls back on an exception. Tokens close
on scope exit. The adapter rejects closed tokens, tokens from another manager or engine,
writes under a read token, and nested scopes in one execution context. Services never
own connections or call driver transaction primitives.

The Operation runner owns source-verification and activation scopes; handlers receive
tokens, never transaction managers. Which commands are Operations and which are
synchronous, and how each takes the document lock, is state-and-use-cases.md §11.

AI, network, browser, filesystem, and object-store I/O run outside database scopes.
Outbound adapters enforce this with `assert_external_io_allowed()`. Metadata reads
finish before payload verification or streaming.

Action-policy reads (state-and-use-cases.md §9) capture database and Knowledge state in
one read scope; Ready payload verification runs after it closes, and the policy combines
both. The API returns this policy; React does not duplicate it.

State tables are authoritative current projections. Append-only events provide audit
and provenance; the system is not event-sourced.

### 7.1 Immutable payload commit and orphan reclaim

The payload protocol is:

`validate bytes -> conditional store -> register`

Validation runs on the bytes before the key is claimed, so a payload that fails it never
occupies its key. The write refuses to replace an existing payload: `O_EXCL` locally, a
conditional PUT (`IfNoneMatch: "*"`) on S3 and R2. The store hashes the bytes it stored
in the same pass, and that digest is what the caller registers. Every physical key embeds
a freshly minted ID (snapshot, artifact version, or Submission), so a retry writes new
keys and never overwrites an earlier attempt's.

Before registration a payload is invisible to queries. If registration fails, no row
references it and it is an orphan.

**Orphan inspection and reclaim** (`MaintenanceService`; routes in
state-and-use-cases.md §19b). A candidate is a stored payload that no database row
references and that was stored longer than `ORPHAN_MIN_AGE` (one hour) ago. Every writer
— JobSnapshot intake, provider evidence, `submit_application` — stores and registers
within one command, seconds apart, so a younger unregistered payload may still be on its
way to registration and is left alone. The age comes from the store itself: file mtime
locally, `LastModified` on S3.

`inspect_orphans` lists the candidates and deletes nothing. `reclaim_orphans` deletes
them, after reading the registered references once more immediately before deleting; a
candidate that became referenced is an integrity failure and reclaim stops without
deleting anything. Deleting an absent key is a no-op, so reclaim is idempotent.

The one limit: a registration that happened more than an hour after its `put` could find
its payload reclaimed. No writer holds a payload unregistered that long; if one ever did,
reconciliation reports the missing payload rather than hiding it.

Reconciliation verifies every registered artifact's payload hash and the fact lifecycle,
reporting both halves without short-circuiting.

### 7.2 Knowledge mutation journal

A Knowledge change crosses a file source of truth and PostgreSQL, so it uses a durable
journal (`knowledge_mutation_journal`: `PREPARED`, `COMMITTED`, `QUARANTINED`):

1. Validate the complete command and the proposed Knowledge file.
2. Stage the new file.
3. Persist a `PREPARED` entry with old/new hashes and paths, the staged path, the
   database mutation and its identity, and the recovery strategy.
4. Atomically replace the Knowledge file.
5. In one write scope, apply the fact events, any resulting document selection update
   (state-and-use-cases.md §17), and the transition to `COMMITTED`. They commit or roll
   back together.
6. Clean up staged and backup files outside the scope. A cleanup failure leaves
   temporary files but does not undo the commit.

Recovery runs during composition and decides from durable hashes and identities whether
to finish or restore each `PREPARED` entry. It never guesses; an unrecoverable entry is
`QUARANTINED`. What quarantine blocks is state-and-use-cases.md §17.

## 8. Domain lineage and provenance

Commands receive explicit source IDs. `latest` belongs to query and UI convenience, not
command semantics.

`CVDocument` records its source — `analysis_id` and `selection` — and has no draft or
revision lineage (`docs/decisions/single-document-model.md`). A Submission freezes the
provenance: Application, JobSnapshot, JobAnalysis, `content`/`document_hash`,
CandidateContext, `facts_hash`, and policy versions.

The Knowledge-store version is coarse audit and detection; `facts_hash` is the exact
dependency hash. Ready is computed from the document's basis, never stored
(state-and-use-cases.md §3, §4, §6).

## 9. Application services and action policy

The action-policy projector (`application/state.py`) implements state-and-use-cases.md
§9. Its architectural constraint is §7: inputs from one read scope, payload verification
after it closes.

## 10. Operation runner

Operation is an application and infrastructure concern, not the central domain
aggregate. Types, statuses, phases, failure codes, and idempotency are
state-and-use-cases.md §11 and §19. This section covers execution.

**Resources.** Required resources are derived from the request
(`required_operation_resources`), so a caller cannot weaken concurrency policy:

- one mutating Operation per Application (every type)
- one global render/browser slot (`render_document`)
- two global AI slots (every AI task, and `analyze_job`/`create_draft` unless the
  provider is `deterministic`)

Locks are resource-specific: a render for one Application does not block analysis for
another. Contention is queueing, not failure; a waiting Operation stays `queued` with an
observable waiting phase until a claim succeeds or the user cancels.

**Claiming.** The worker (`runtime/execution.py`) runs a thread pool (concurrency 2,
poll 0.25 s). A claim selects a queued row with `FOR UPDATE SKIP LOCKED`, inserts
resource slot rows, and takes a 30 s lease renewed by a 10 s heartbeat. A lost race — a
skipped row or a `40001` serialization failure — is a lost claim, not an error.

**Startup and shutdown.** Worker startup changes every `queued`/`running` row that still
holds a lease to `interrupted`, regardless of expiry, and releases its slots; it never
resumes an external call. This assumes no other worker is live, which is why one worker
process runs at a time. Shutdown stops claiming and requests cancellation for whatever
it still holds.

**Records.** An Operation stores its type, secret-free payload and hash (a payload with
a secret-named key is refused), idempotency key, provider/model/reasoning effort, frozen
sources (`OperationSources`), required resources, lifecycle timestamps, lease and
heartbeat, cancellation request, phase and message, failure detail and log reference,
retry reference, and outputs.

**Execution.** Handlers implement `verify_sources`, `execute`, `activate`,
`after_activation`, and `discard`. Commit checks run before execution and before
activation. `SOURCE_CHANGED` keeps any immutable output as inactive evidence and fails
the Operation without changing the document. Provider calls and payload preservation
happen outside scopes; prepared evidence is registered as inactive in short scopes
before activation, and neither cancellation nor activation rollback erases it.
Re-registering the same provider output does not duplicate evidence. Activation locks
the Application, reloads Operation and lease state, rechecks sources and cancellation,
then atomically activates use-case state, outputs, and completion. Post-commit
projections and file logging run after the scope closes.

**Cancel and retry.** Queued cancellation is immediate. Running cancellation is best
effort and cancels activation. A user retry creates another Operation. One automatic
retry, after a short delay, is allowed only for the transient codes.

## 11. AI adapter

Task semantics — analysis, coverage and shortfall, writer and reviewer, evidence
acceptance — are product-spec §12 and state-and-use-cases.md §13–§14. This section is
the adapter.

`AIProvider` (`application/ports/outbound.py`) is provider-neutral. The OpenAI adapter
(`infrastructure/providers.py`) uses the Responses API with strict Structured Outputs
and returns task-specific Proposal DTOs plus provider provenance. It cannot save domain
state. Tasks: `propose_analysis`, `propose_selection_plan`, `draft_resume`,
`regenerate_section`, `regenerate_claim`, and `assess_claim_support` (the reviewer step
of every writing Operation, a separate call from the writer). With no provider
configured no adapter is built, and nothing is sent.

Each task receives minimal allowed context. Provider output passes schema validation and
deterministic checks before it becomes domain state; the claim-review evidence check
(`domain/claim_review.py`) runs at activation and again at validation for approval, so
the evidence that let a line in is the evidence that keeps it in. Pre-approval
validation is synchronous and deterministic over stored evidence and starts no AI work.

**Analysis contract.** Requirement identity is the snapshot plus the requirement's
normalized text under a stated identity-algorithm version. The prompt version is
provenance, not identity input, so rewording a prompt does not turn unchanged
requirements into new entities. The reader accepts analysis contract `3.0` only and does
not invent fields for older documents. A provider-supplied held value is not numeric
evidence merely because it agrees arithmetically with the proposed coverage; it must
trace to canonical structured evidence or stay unresolved. Malformed thresholds are
invalid output.

**Provenance.** Calls are stateless. The model and reasoning effort are frozen when an
Operation is submitted. Model, provider, reasoning effort, task-contract version, prompt
version/hash, input/output schema hashes, usage, latency, response ID, dated pricing,
derived USD cost, and output hashes are stored. The sanitized raw response is an
immutable payload (§6.2); sanitization removes secrets and excludes hidden reasoning.

## 12. HTTP API

The prefix is `/api/v1`; product v2 and API v1 are separate version spaces. Endpoints,
status codes, and concurrency headers are state-and-use-cases.md §21–§22, and the
generated `openapi/openapi.json` is authoritative for the route table. OpenAPI is served
at `/api/v1/openapi.json`; interactive docs pages are disabled.

API schemas are separate from domain and persistence types. The schema is generated
(`python openapi/generate_openapi.py`) and checked for drift; `openapi/types.ts` is
generated from it. The handwritten `frontend/src/api/client.ts` owns HTTP mechanics.

Errors are RFC-style Problem Details with a stable code and safe context. Technical
detail stays in the structured logs.

Artifact endpoints take IDs only. They resolve a registered reference, verify the stored
hash, and stream it with a friendly filename. Containment belongs to the store:
`LocalObjectStore` keeps keys below `artifacts_root` and refuses traversal and symlink
escape; `S3ObjectStore` validates the key. Nothing above the store handles a filesystem
path. Request bodies are bounded (`CV_API_MAX_BODY_BYTES`, default 2 MiB); oversize is
`413`.

## 13. Frontend architecture

The production build is served by FastAPI at the same origin when `frontend/dist`
exists; without it the API runs alone. Node is not a user runtime dependency. In
development, Vite proxies `/api` to the API, and only that one origin is allowed.
Module boundaries: `frontend/src/features/README.md`; tokens, theming, and RTL:
`frontend/docs/design-system.md`.

TanStack Query owns server state and polling. React Hook Form owns local forms.
Component state owns transient editor dialogs and save-conflict UI. There is no Redux
and no client-side workflow state machine.

The UI is Hebrew and its shell is RTL. CV language is independent. The HTML preview is
rendered by the backend and shown in an isolated iframe.

Operation progress polls while an Operation is active and stops at a terminal status or
a permanent error. It shows the backend's status, phase, safe message, and actions —
no synthetic percentages and no separate Operation route.

Autosave uses debounce and blur. A `409` opens an explicit local/current comparison and
never merges silently.

## 14. Local security

The service binds to `127.0.0.1`, serves UI and API same-origin, and validates `Origin`
on mutation. CORS uses an explicit origin list with no wildcard and no credentials;
development adds only the one Vite origin (`CV_API_DEV_ORIGIN`). There is no
authentication and no CSRF token.

The OpenAI key is environment-only backend configuration. React sees only whether it is
configured. Logs and Operation payloads are redacted and never contain keys,
authorization headers, or secrets.

Job and user text is untrusted; prompt contracts isolate it from policy. Artifact access
resolves registered references only, never a caller-supplied location. No endpoint
accepts arbitrary local paths or arbitrary file uploads.

## 15. Runtime behavior

The API defaults to `127.0.0.1:8765`. Uvicorn binds the port, but the app must also be
told it through `CV_API_HOST`/`CV_API_PORT`: the origin policy allows the origin the app
believes it answers on, so a port given only to uvicorn refuses every state-changing
request from its own UI.

Resume PDFs always render with the Playwright-managed Chromium. Local Chrome is
diagnostic only.

Structured rotating logs under `logs_root`: `server.jsonl` (API) and `operations.jsonl`
(worker), with timestamp, level, Operation ID, Application ID, phase, error code, and
log reference. Exception details and tracebacks are file-only. There is no logs screen.

The consoles are concise. The API logs startup, shutdown, and one line per request with
method, path, status, and duration (uvicorn's access log is disabled). The worker logs
start, claims, terminal outcomes, startup recovery, and stop. Empty polling, heartbeats,
query strings, headers, and bodies are not logged.

### 15.1 Runtime configuration and secrets

`cv_engine/runtime/config.py` is the single resolution contract; `.env.example` is the
committed inventory of supported variables. Precedence:

`process environment > project .env > project cv.config.json > default`

Only the repository-root `.env` is read, in a small `KEY=value` subset parsed without a
dependency; a malformed line is skipped.

Each setting declares whether it is secret or environment-only. `database_url` is
secret. `OPENAI_API_KEY` is secret and environment-only, so `unset OPENAI_API_KEY`
reliably disables the OpenAI adapter even when a `.env` exists. AWS credentials stay
ambient boto3 configuration.

Masking happens only at display boundaries: a configured secret shows as `***` with its
source label, and an unset secret shows as unset. Connectors always receive the real
value. `.env` and `.env.*` are Git-ignored.

## 16. Database lifecycle and upgrade

Schema upgrade is explicit: `alembic upgrade head`. `/health` reports the current schema
revision; reconciliation reports payload and fact-lifecycle integrity. A new build never
performs a hidden data migration. Backup policy lives outside the application.

## 17. Version surfaces

Provenance and compatibility track, each where it applies:

- product version, database schema revision, API version
- domain document and analysis contract versions
- Knowledge versions (reported by `/health`)
- selection, rendering, validator, and review policy versions
- task-contract version, prompt version/hash, input/output schema hashes

The product version does not substitute for any of them.
