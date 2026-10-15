# Architecture

Layers, storage, transactions, the Operation runner, security, and runtime. Product
behavior: `product-spec.md`. States, commands, and HTTP: `state-and-use-cases.md`.
Section numbers are cited from code; keep them stable.

## 1. Architecture objective

One synchronous application layer, called by two processes:

- **FastAPI** is the only user-facing adapter. React reaches the system only through it.
- **The worker** executes Operations through the same application layer. The only
  Operation it queues itself is the `create_draft` an analysis continues into when
  automatic generation is on (product-spec §9), through `OperationContinuationStore`.

Dependency rule: `domain <- application <- infrastructure / api / runtime`. `runtime`
imports `api`, never the reverse. Product logic lives in domain and application code,
not in routers, React components, SQL triggers, or templates.

## 2. Technology baseline

Exact versions: `pyproject.toml`, `frontend/package.json`.

Backend:

- Python 3.11+, Pydantic 2
- FastAPI + Uvicorn
- PostgreSQL 17 through SQLAlchemy 2.0 Core (no ORM) and psycopg 3; Alembic
- Jinja2 for resume HTML; Playwright Chromium for rendering; `pypdf` for PDF checks
- `argon2-cffi` for passwords
- `boto3` only in the optional `s3` extra, imported inside the S3 adapter
- Tooling: pytest, ruff, pyright (`basic`)

Frontend:

- React, TypeScript, Vite, React Router, TanStack Query, React Hook Form, Tailwind CSS,
  `lucide-react`
- Types generated from the committed OpenAPI schema (`openapi/`)
- Tooling: Vitest, Playwright with axe, oxlint, Prettier, knip, design-token check

Not used: Redux, Celery, Redis, WebSockets, SSE, a DI framework, `python-dotenv`.

## 3. Source organization

```text
cv_engine/
  domain/           entities, value objects, validation, draft frame, lifecycle rules
  application/      commands, queries, ports, services, action policy, Operation runner
  infrastructure/   persistence adapters, object stores, Knowledge, provider, renderer
  api/              routers, schemas, middleware
  runtime/          composition root, config, paths, ASGI app, worker pool
  worker/           `python -m cv_engine.worker`
frontend/           React application (`frontend/src/features/README.md`)
openapi/            generated schema and TypeScript types
alembic/            schema revisions
```

### 3.1 Domain

Entities, value objects, lifecycle and transition rules, validation, the draft frame,
claim-review evidence checks, and Ready qualification. It imports no FastAPI,
SQLAlchemy, psycopg, filesystem paths, Playwright, provider code, or runtime config.
Serialized documents are Pydantic models.

### 3.2 Application

Commands, queries, services, ports, transaction boundaries, action policy, state
projections, optimistic commit checks, and turning validated Proposals into domain
state. Services are synchronous and grouped by kind of work (intake and queries,
analysis, AI authoring, editing, check and approval, history export, rendering,
recruitment and submission, knowledge, Operations, maintenance, settings). They return
Pydantic DTOs, never rows or paths.

Services live in `services/`, their ports in `ports/`. Top-level modules under
`application/` hold shared contracts (`operations.py`, `settings.py`), pure policy
(`state.py`, `transactions.py`), the error taxonomy, and the Operation runner.

### 3.3 Infrastructure

Implements the ports: SQLAlchemy Core persistence, transaction scopes, object stores,
Knowledge (user rows plus policy files), the OpenAI provider, rendering, logging.

Ports follow consumer and trust boundaries, not tables. The API's Operation port and
the worker's execution port are separate. Adapters don't call each other, hold no
connection, and open no transaction: every database method takes a transaction token,
and writes need a write token. Services depend on ports, not adapters.

### 3.4 API

Routers map HTTP to use-cases and back; no business logic. The API receives
`ApiServices` (`cv_engine/api/services.py`): application services plus instance
identity and transport limits, nothing lower-level.

### 3.5 Runtime and composition

`cv_engine/runtime/composition.py` is the manual composition root. `build_services`
wires config, one SQLAlchemy engine, the transaction manager, adapters, services, the
Operation runner, and the worker; `build_api_services` narrows it to `ApiServices`.
Tests substitute adapters through `build_services` keyword arguments.

Two processes over one database, neither supervising the other:

- `uvicorn cv_engine.runtime.asgi:app` serves HTTP and starts no background work.
- `python -m cv_engine.worker` recovers startup state, then claims Operations until
  SIGINT/SIGTERM. One worker at a time (advisory lock, §10).

## 4. Application paths

The root is the installed repository root, computed from the code location
(`runtime/paths.py`), and not configurable. Tests inject `AppPaths.from_root(...)`.

```text
knowledge_root   = {root}            profiles/, config/, ai/, rendering/ (base/: import input)
artifacts_root   = {root}/artifacts
temp_root        = {root}/tmp
logs_root        = {root}/logs
```

`artifacts`, `tmp`, and `logs` are created on startup, may not be symlinks, and every
path resolves inside the root.

## 5. CandidateContext

Each user has one CandidateContext row (`candidate_contexts`, §18.2) referencing their
name and contact facts and defining filename/display policy, timezone, and locale.
Application rows carry `user_id`; the user is the candidate. Renderers and filename
policy take CandidateContext explicitly.

Fact IDs: existing semantic IDs are kept; new facts get UUIDv4.

Knowledge is re-read for each command that depends on it. A change during a running
analysis is `SOURCE_CHANGED`.

## 6. Persistence boundary

### 6.1 PostgreSQL

Holds Applications (with job text, locked after submission by trigger
`lock_submitted_job_text`), recruitment and audit history, JobAnalyses, `cv_documents`
(fields: state-and-use-cases.md §3), `ai_calls` (§11), Submissions, Operations, fact
events, users, sessions, facts, CandidateContexts, Profile bindings (§18.2), settings,
and rate-limit buckets.

Addressed by `CV_DATABASE_URL`. One `Engine` (`pool_pre_ping=True`). Transactions run at
`REPEATABLE READ`.

Every immutable table has UPDATE and DELETE guard triggers. A table is treated as
immutable unless named in the mutable exception set
(`tests/platform/test_persistence_constraints.py`), so a new table without guards
fails the test.

Alembic owns the schema: one head, applied explicitly with `alembic upgrade head`,
never on startup.

### 6.2 Object storage

Submission files sit behind `ObjectStore` (keys and bytes). `LocalObjectStore`
(default) writes under `{artifacts_root}`; `S3ObjectStore` writes to an S3-compatible
bucket (`CV_S3_ENDPOINT_URL` for R2/MinIO). Chosen by `CV_OBJECT_STORE`.

```text
{artifacts_root}/ or {bucket}/{prefix}/
  submissions/{application_id}/{submission_id}/resume.html
  submissions/{application_id}/{submission_id}/resume.pdf
```

Database path fields store project-relative strings such as
`artifacts/submissions/{app}/{id}/resume.pdf`; the object key is the same without
`artifacts/`. Rows are identical under either backend. Both stores refuse traversal,
absolute paths, empty segments, backslashes, and drive prefixes.

Not in the object store:

- document content (inline in `cv_documents.content`);
- job text (inline in `applications.job_text`);
- render output: `{artifacts_root}/documents/{application_id}/{attempt_id}/`, mutable
  working files;
- policy files (version-controlled);
- provider responses (in `ai_calls`).

A Submission copies the document's HTML and PDF into its own keys with SHA-256. On S3
the copy is staged under `{temp_root}` and removed after upload.

### 6.3 Knowledge files

Facts, CandidateContext, and Profile bindings are per-user rows (§18.2). Policy stays in
version-controlled files: Profile templates, emphasis policy, prompts, task contracts,
requirement concepts, rendering rules.

## 7. Transaction ownership and consistency

```python
with transactions.write() as tx:
    store.mutate(tx, prepared)
```

A write scope commits once on normal exit and rolls back on exception. Adapters reject
closed tokens, foreign tokens, writes under a read token, and nested scopes. Services
never touch connections directly.

The Operation runner owns verification and activation scopes; handlers receive tokens.

AI, network, browser, filesystem, and object-store I/O run outside database scopes
(`assert_external_io_allowed()`).

Action-policy reads (state-and-use-cases.md §9) capture database and Knowledge state in
one read scope; Ready file verification runs after it.

State tables are the current truth; event tables are audit. Not event-sourced.

### 7.1 Immutable payload commit and orphan inspection

`validate bytes -> conditional store -> register`

The write never replaces an existing payload (`O_EXCL` locally, `IfNoneMatch: "*"` on
S3/R2) and returns the digest of what it stored. Every key includes a fresh Submission
ID, so retries never overwrite.

Nothing deletes an immutable payload; the stores have no delete operation. A failed
registration leaves an orphan, which `inspect_orphans` reports (older than
`ORPHAN_MIN_AGE`, one hour; age from file mtime or S3 `LastModified`) and never deletes.

Reconciliation verifies every payload hash, every AI-call response hash, and the fact
lifecycle.

### 7.2 Knowledge mutations

A fact mutation is one write scope: read the user's rows, apply the change in memory,
rebuild and validate the full Knowledge, then write the changed rows, bindings, events,
and the incremented `fact_store_version`. The version increment is conditional on the
version read, so a concurrent mutation gets `StateConflict`.

## 8. Domain lineage and provenance

Commands take explicit source IDs; only queries resolve "latest".

`CVDocument` records its `analysis_id` and has no revision history. A Submission
records `content`, `document_hash`, `job_text_hash`, and the copied files with SHA-256
— not `facts_hash`, CandidateContext version, or policy versions.

`fact_store_version` is coarse audit; `facts_hash` is the document's exact dependency
hash, computed on read. Ready is computed, never stored (state-and-use-cases.md §3–§6).

## 9. Application services and action policy

`application/state.py` implements the action policy (state-and-use-cases.md §9), from
one read scope (§7).

## 10. Operation runner

Types, statuses, phases, and failure codes: state-and-use-cases.md §11, §19.

**Concurrency.** Enforced by the database:

- one running Operation per Application (`uq_operations_running_application`);
- one running render overall (`uq_operations_running_render`).

A waiting Operation stays `queued`; its phase is derived on read. The worker's thread
count (2) is the only overall limit.

**Claiming.** The worker (`runtime/execution.py`) polls every 0.25 s with 2 threads. A
claim walks queued Operations oldest first, skipping ones whose Application or render
slot is busy, and in a savepoint locks the row (`FOR UPDATE SKIP LOCKED`) and sets
`running`, `executing`, and `lease_owner`. A lost race (skipped row, `40001`, or `23505`
on one of the two indexes) moves to the next candidate; any other `23505` is raised.
Claims don't expire.

**One worker.** The worker holds a PostgreSQL advisory lock (`worker_exclusivity`) on a
dedicated connection for its whole life; a second worker exits. At startup every
`running` row becomes `interrupted`. The worker checks the lock every 5 s; if lost, it
stops claiming, cancels what it holds, and exits (`WorkerLockLost`). Every runner write
requires `lease_owner` to still match, so interrupted work cannot activate.

**Records.** Type, secret-free payload and hash, idempotency key, provider/model/effort,
frozen sources (`OperationSources`), timestamps, lease owner, cancellation request,
phase, message, failure detail, retry reference, outputs.

**Execution.** Handlers implement `verify_sources`, `execute`, `activate`,
`after_activation`, and `discard`. Sources are checked before execution and before
activation (`SOURCE_CHANGED` on change). `execute` gets `execution_still_owned`.
Each provider attempt is logged to `ai_calls` in its own short scope as it ends.
Activation locks the Application, rechecks lease, sources, and cancellation, then
commits state, outputs, and completion together.

**Cancel and retry.** Queued cancellation is immediate; running cancellation prevents
activation. The runner never retries. A provider call is retried at most once (§11) and
a failed browser start once, both only while `execution_still_owned`.

## 11. AI adapter

Task semantics: product-spec §12.

`AIProvider` (`application/ports/outbound.py`) is provider-neutral. The OpenAI adapter
(`infrastructure/providers.py`) uses the Responses API with strict Structured Outputs
and returns Proposal DTOs plus provenance; it cannot write state. Without a configured
key no adapter is built.

Provider output passes schema validation and engine checks before becoming state. The
claim-review evidence check (`domain/claim_review.py`) runs at activation and again at
approval.

**Analysis contract.** Requirement identity is the normalized job-text hash plus the
requirement's normalized text under an identity-algorithm version; the prompt version
is not part of it. The reader accepts analysis contract `3.0` only.

**One attempt per call.** The adapter makes one HTTP request per call and returns an
`AICallRecord` for any outcome; it never retries or touches the database.
`services/ai_calls.py` logs each record first, then applies the retry policy:

| Outcome | How it is known | Retried |
| --- | --- | --- |
| `not_delivered` | `URLError` from a failed name lookup or refused connection | once, after 1-3 s |
| `outcome_unknown` | any other transport failure | never (may have been billed) |
| `rate_limited` | 429 that is not a billing refusal | once, only with `Retry-After` ≤ 20 s |
| `quota_exhausted` | 429 with a billing code or `insufficient_quota` → `PROVIDER_QUOTA_EXHAUSTED` | never |
| `http_error` | 500, or 503 (`Retry-After` up to 20 s) | once |
| `http_error` | any other status | never |
| `refused`, `schema_violation` | 200 without structured text, or text the schema refuses | never |

**AI call log.** `ai_calls` holds one append-only row per attempt, keyed by
`operation_id` and an `attempt` ordinal. It records provider, model, effort,
task-contract, schema and prompt versions and hashes, input hash, Knowledge context
hash, outcome, HTTP status, error type and code, `Retry-After`, response ID, sanitized
response and its hash, output hash, usage, price snapshot, cost, latency, and times. The
request itself is not stored. A row is appended even if the Operation was cancelled.

**Sanitized response.** The provider JSON with credential- and reasoning-shaped keys and
reasoning items removed; non-JSON bodies are kept truncated and redacted.
`sanitized_response_hash = sha256(canonical_json(sanitized_response))`.

**Usage and cost.** Ordinary input is `input_tokens - cached_tokens -
cache_write_tokens`; cached and cache-write input have their own rates. Unreported
usage is NULL, never zero. Operation totals sum all attempts; `not_delivered` adds zero,
and any other attempt with a missing value makes the total NULL.

## 12. HTTP API

`/api/v1` (separate from the product version). Routes: `openapi/openapi.json`, served
at `/api/v1/openapi.json`; interactive docs disabled. The schema is generated with
`python openapi/generate_openapi.py` and checked for drift; `openapi/types.ts` is
generated from it. `frontend/src/api/client.ts` handles HTTP mechanics.

No endpoint takes a storage location. Request bodies are capped by
`CV_API_MAX_BODY_BYTES` (default 2 MiB).

## 13. Frontend architecture

FastAPI serves `frontend/dist` at the same origin when it exists. In development Vite
proxies `/api`. Module boundaries: `frontend/src/features/README.md`; tokens and RTL:
`frontend/docs/design-system.md`.

TanStack Query owns server state and polling; React Hook Form owns forms; component
state owns dialogs and conflict UI. No client-side workflow state machine.

Auth state (`loading`, `authenticated`, `unauthenticated`) from `GET /auth/me` gates
private routes. A `401` clears it and the query cache and returns to `/login`. Sign-out
also clears per-user browser storage, including the intake recovery copy.

The UI is Hebrew/RTL; CV language is independent. The HTML preview is backend-rendered
in an isolated iframe. Operation progress polls while active and shows the backend's
status and phase. Autosave conflicts (`409`) open an explicit comparison.

## 14. Local security

The service binds to `127.0.0.1`, serves UI and API from one origin, and validates
`Origin` on every mutation. CORS uses an explicit list, no wildcard, no credentials;
development adds the Vite origin (`CV_API_DEV_ORIGIN`). An allowed `Origin` plus
`SameSite=Lax` cookies is the CSRF defence. *Not built:* hosted public origin (§18.5).

`OPENAI_API_KEY` is environment-only; React sees only whether it is set. Logs and
payloads never contain keys or secrets. No endpoint accepts paths or arbitrary uploads.

## 15. Runtime behavior

The API defaults to `127.0.0.1:8765`. Set `CV_API_HOST`/`CV_API_PORT` to match what
uvicorn binds, or the origin check refuses the UI's own requests.

PDFs render with Playwright Chromium.

Rotating JSON logs under `logs_root`: `server.jsonl` (API) and `operations.jsonl`
(worker). Tracebacks go only to files. The API console logs one line per request
(method, path, status, duration); the worker logs claims, outcomes, and lifecycle.

### 15.1 Runtime configuration and secrets

`cv_engine/runtime/config.py` resolves settings; `.env.example` lists them. Precedence:

`process environment > project .env > project cv.config.json > default`

Only the repository-root `.env` is read (`KEY=value`; malformed lines skipped).
`database_url` is secret. `OPENAI_API_KEY` is secret and environment-only. AWS
credentials come from boto3's ambient config. Secrets display as `***`. `.env*` is
Git-ignored.

## 16. Database lifecycle and upgrade

`alembic upgrade head` upgrades explicitly. `/health` reports the schema revision. No
hidden data migrations; backups are external.

## 17. Version surfaces

- product version, schema revision, API version
- domain document and analysis contract versions
- Knowledge versions (in `/health`)
- rendering, validator, and review policy versions
- per AI call: task-contract, prompt, and schema versions and hashes

## 18. Identity, sessions, and isolation

Product rules: product-spec.md §22. Commands and codes: state-and-use-cases.md §23.

### 18.1 Identity tables

Mutable: `users`, `user_sessions`, `rate_limit_buckets`, `user_settings`.

- `users`: `id`, `email` (NFC, trimmed, lowercased, `UNIQUE`), `password_hash`,
  `created_at`.
- `user_sessions`: `id`, `user_id`, `token_hash` (`UNIQUE`), `created_at`,
  `expires_at`, `revoked_at`; indexed by `user_id`.
- `user_settings`: `user_id` primary key.
- `applications.user_id NOT NULL`, indexed with `created_at`, `current_status`,
  `updated_at`.

Only aggregate roots carry `user_id`; everything else reaches its user through its
Application.

### 18.2 Knowledge schema

- **`facts`** (mutable): `id` (internal UUID), `user_id`, `fact_id` (the ID documents
  cite; `UNIQUE (user_id, fact_id)`), `status`, `source` (`common`, `development`,
  `sales`, `situational_skills`, or `user`), `ordinal`, `meaning`, `renderings` (`en`
  required), `tags`, `provenance`, `effective_dates`, `resume_style`, `link_target`,
  `replaces` (history only, no foreign key), `confirmed_at`, `created_at`,
  `updated_at`. A trigger refuses changes to `id`, `user_id`, `fact_id`, `source`,
  `ordinal`, `created_at`, and refuses deletes.
- **`fact_events`** (immutable): lifecycle history with `user_id` and `fact_json`.
- **`candidate_contexts`** (mutable, `user_id` primary key): `name_fact_id`,
  `contact_fact_ids`, `track_contact_fact_ids`, `link_schemes`, `filename_language`,
  `locale`, `timezone`, `context_version`, `fact_store_version`, `updated_at`.
  Referenced facts must be the user's canonical facts. Written only by
  `import-knowledge`.
- **`profile_bindings`** (mutable, key `(user_id, profile_id)`): `sections` (section →
  ordered fact references with `pinned`), `safe_headlines`, `omitted_roles`,
  `binding_version`. Written by `import-knowledge`, `attach_fact`, and
  `confirm_and_use_fact`.

Each fact mutation increments `fact_store_version`. Documents and Submissions reference
facts by `fact_id`, always resolved as `(application.user_id, fact_id)`.

### 18.3 Ownership in the application layer

The API resolves the session to an `Actor` and passes it to every service call. Roots
are resolved by user, children through their root:

```python
application = applications.get_for_user(tx, application_id, actor.user_id)
analysis = analyses.get_for_application(tx, analysis_id, application.id)
```

- A child lookup is constrained by its resolved Application; a record addressed by its
  own ID (Operation, fact) joins to its root in the same query. Not owned = not found.
- No persistence port reads or writes a user-owned root (`applications`, `facts`,
  `candidate_contexts`, `profile_bindings`, `user_settings`, `user_sessions`) without
  `user_id`, or a child without `application_id`. Exceptions: the worker's owner
  resolution and the operator CLI.
- Idempotency: `UNIQUE (application_id, operation_type, idempotency_key)`.
- Concurrency limits are per Application, plus the global render and thread limits.
- The worker takes the owner from `operations.application_id → applications.user_id`,
  never from the payload (a payload naming `user_id` is refused), and reads only that
  user's data.

### 18.4 Sessions and passwords

- Session token: 32 random bytes in the `__Host-cv_session` cookie (`HttpOnly`,
  `Secure`, `SameSite=Lax`, `Path=/`), stored as SHA-256. Lifetime 30 days
  (`CV_SESSION_DAYS`), no idle timeout or refresh. Sign-in revokes the presented
  session.
- Passwords: Argon2id with library defaults; 12 to 256 characters. Unknown emails
  verify a dummy hash for equal timing. Outdated hashes are upgraded on sign-in.

### 18.5 Transport and rate limit

- Every mutation needs an allowed `Origin`, `login` included.
- The app shell sends `frame-ancestors 'none'`; previews allow framing only by the app's
  own origin.
- Sign-in rate limit in `rate_limit_buckets`: 15-minute window, 5 failures per email,
  20 attempts per IP. The IP comes from a forwarding header only per
  `CV_TRUSTED_PROXY_HOPS`. The worker removes old windows.
- *Not built:* one public origin (`CV_PUBLIC_ORIGIN`, HTTPS), a Host allowlist, and
  HSTS.

### 18.6 Renderer isolation

- The page loads only its own `file://` HTML; every other request is aborted.
- Templates fetch no external asset; needed assets ship in `rendering/` and are copied
  into the attempt directory.
- CSP `script-src 'none'`; only the renderer's own measurement script runs.
- Navigation after the first load is aborted.
- A fresh browser context per render.

### 18.7 Operator CLI

`python -m cv_engine.admin`, no HTTP surface, same application layer. Passwords come
from a non-echoing prompt (entered twice) or `--password-stdin`, never an argument.

- `create-user --email`
- `set-password --email` (revokes every session)
- `import-knowledge --email [--from <dir>]`: loads `base/` and `profiles/` from `<dir>`
  (default: the installation) through the validated loader and writes the user's facts,
  CandidateContext, and Profile bindings in one transaction. Refuses an unknown user or
  one who already has Knowledge. Verifies by reading back before commit.
  `fact_store_version` starts at 0.
- `reconcile`, `inspect-orphans` (state-and-use-cases.md §19b).
