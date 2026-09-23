# Multi-Track CV Engine v2

Fact-safe CV generation and application tracking for Development, Sales, and Tech
Sales. A FastAPI backend and a React frontend. Job analysis is where AI belongs; from an
existing analysis, everything down to a Ready PDF runs with no key.

The binding specifications are under [`docs/spec/`](docs/spec/).
[`docs/README.md`](docs/README.md) says which document answers which question.

## Setup

Install `uv`, then bootstrap a dedicated environment for this worktree:

```bash
./scripts/bootstrap-worktree.sh
```

Each worktree keeps its own editable environment, so imports cannot fall through to a
different checkout. `uv` installs third-party packages from its global cache using
copy-on-write clones on macOS, avoiding another physical copy of Playwright's 115 MB
Node driver and the other shared dependencies.

The bootstrap also installs the locked frontend dependencies and creates `.env` from
`.env.example` when no local configuration exists. It never replaces an existing
`.env`.

PostgreSQL lifecycle and schema upgrades stay explicit. For the first run, start the
local database and apply the current migrations before starting the application:

```bash
docker compose up -d postgres
./.venv/bin/alembic upgrade head
./scripts/dev.sh
```

Multiple worktrees may share the same PostgreSQL server, but worktrees that run in
parallel should use separate databases through `CV_DATABASE_URL`; they do not need
separate PostgreSQL servers.

PDF generation uses Playwright-managed Chromium. Playwright's normal macOS browser
cache is shared at `~/Library/Caches/ms-playwright`; the bootstrap refuses
`PLAYWRIGHT_BROWSERS_PATH=0`, which would instead duplicate browser binaries inside
each worktree. To install the browser again without replacing the environment:

```bash
./.venv/bin/python -m playwright install chromium
```

## Architecture

- `base/common.json`, `base/sales.json`, `base/development.json`, and
  `base/situational_skills.json` are the modular canonical fact store.
- `profiles/` selects and weights facts without duplicating content.
- `rendering/rules/` and `rendering/templates/` define Development, Sales LTR/RTL,
  and deterministic profile-specific presentations of canonical facts. Tech Sales
  can therefore shorten Development evidence into business-value wording without
  changing or duplicating the underlying fact.
- `cv_engine/` owns deterministic workflow, validation, persistence, rendering, and AI
  boundaries.
- PostgreSQL stores mutable application state and immutable history, through
  SQLAlchemy Core and numbered Alembic revisions.
- `artifacts/working/` contains the replaceable working draft. Immutable payloads live
  under fixed key prefixes — `snapshots/`, `revisions/`, `outputs/`, `provider/`,
  `manifests/` — whose layout is frozen in `docs/spec/architecture.md` section 6.2 so a
  row reads the same under local storage and under an S3-compatible bucket.
- `base/` and `profiles/` hold the canonical source facts used directly by the
  application, so they are live input rather than archive.

## Default workflow

The Web UI is the product interface. The system runs as two processes - the API and
the Operation worker - over one database:

```bash
./.venv/bin/python -m uvicorn cv_engine.runtime.asgi:app --host 127.0.0.1 --port 8765  # API
./.venv/bin/python -m cv_engine.worker                                           # queued work
```

The API serves HTTP and starts no background work; the worker claims queued
Operations under a lease, so neither process supervises the other and a worker that
dies leaves its work recoverable by the next one.

Both terminals show concise lifecycle summaries. Complete rotating JSONL logs are
written under `logs/`: `server.jsonl` for API requests and failures, and
`operations.jsonl` for worker lifecycle, phases, retries, and failures. Follow them
without adding polling noise to the process terminals:

```bash
tail -f logs/server.jsonl
tail -f logs/operations.jsonl
```

Request bodies, headers, and query strings are excluded; credential-like values in
exception details and tracebacks are redacted.

Everything below is a brief summary; the full workflow semantics — staleness rules,
draft-edit classification, Emphasis weighting, and requirement-attestation boundaries —
are defined in [`docs/spec/product-spec.md`](docs/spec/product-spec.md) and
[`docs/spec/state-and-use-cases.md`](docs/spec/state-and-use-cases.md). The Web UI calls
the same application services the API exposes.

**Create → analyze → draft → review → approve → render → Ready.** A job posting is
captured once as an immutable snapshot and never re-fetched. Drafting stops for review
and never renders by default; unsupported wording is retained as `pending` rather than
discarded, and cannot be approved. Approval freezes exactly the content one
ValidationRun passed, and rendering then runs the same content, claim, PDF, ATS, link,
direction, filename, and visual gates every time. Low fit and requirement gaps are
diagnostic information, not workflow blockers.

## Fact lifecycle

New information follows `pending -> confirmed -> canonical` (`docs/spec/product-spec.md`
§17); every promotion writes to the canonical source file under `base/` and appends an
immutable event to `fact_events`. Correcting a canonical fact means creating a
replacement that `replaces` it via `POST /api/v1/facts` — identity is always generated,
and a correction never mutates the fact it supersedes.

## Tracking and inspection

An internal submission requires the exact qualified ApprovedRevision and PDF artifact IDs;
Ready qualification is re-derived from stored evidence at submission time, so a revision
whose PDF was replaced is refused rather than recorded. An external submission records
what is known without creating either identity, and a field that cannot be derived stays
null. `applied` is submission-owned: it is reached by recording a submission, never by
asking for it. Recruitment history, corrections, audit records, and submissions are
append-only, and a correction appends an event rather than editing the one it corrects.

## Maintenance

Reconciliation checks database references, artifact hashes, and the fact lifecycle:

```bash
curl -X POST -H "Origin: http://127.0.0.1:8765" \
  http://127.0.0.1:8765/api/v1/maintenance/reconciliations
```

It reports and never repairs: a mismatch against an immutable record is something to be
told about, not something a route may quietly fix. `200` carries the report whether or
not it passed, and `passed` is the field to read. Verification goes through the
configured payload store, so it reports the truth under local storage and under an S3
bucket alike.

## AI provider

Creating a new `JobAnalysis` requires a configured provider, with no rules-based
fallback (`docs/spec/product-spec.md` §2, "Semantic analysis authority"). Everything
downstream of an existing analysis — editing, validation, approval, rendering, Ready,
export, and recruitment tracking — runs with no key at all. Draft creation keeps its own
separate deterministic path (`provider=deterministic` on `create_draft`), unaffected by
this.

A configured key enables five structured OpenAI proposal tasks: `propose_analysis`,
`propose_selection_plan`, `draft_resume`, `regenerate_section`, and `regenerate_claim`.
The Web settings page offers a closed model catalog and low/medium/high reasoning
effort, frozen onto each queued AI Operation:

```bash
export OPENAI_API_KEY='...'
```

Provider output is Pydantic-validated through strict Structured Outputs; each provider
artifact preserves token usage, the dated pricing snapshot, and its calculated USD cost.

## Local Web UI

Two ways to run it, for two different jobs.

**Developing the frontend** — no build step:

```bash
./scripts/dev.sh
```

The script starts the API, queued-work worker, and Vite frontend together. Open
`http://localhost:5173`; `Ctrl+C` gracefully stops all three process groups, including
the Uvicorn reload and Vite child processes. It is equivalent to running these commands
in separate terminals:

```bash
export CV_API_DEV_ORIGIN=http://localhost:5173
./.venv/bin/python -m uvicorn cv_engine.runtime.asgi:app --host 127.0.0.1 --port 8765 --reload
./.venv/bin/python -m cv_engine.worker  # queued work
cd frontend && npm run dev              # localhost:5173
```

Vite compiles on demand and reloads on save. It proxies `/api` to the backend, so the
two are one origin from the browser's point of view. This is the normal loop; nothing
here needs `npm run build`.

Vite binds `localhost:5173` with a strict port and never falls back to another one,
because a silent fallback would disagree with the backend's Origin allowlist — which is
also why the backend needs `CV_API_DEV_ORIGIN` naming that exact origin.

For the Vite frontend alone, bind it to the local network with:

```bash
cd frontend
npm run dev:mobile
```

To start the API, worker, and the same mobile-accessible frontend together, run:

```bash
./scripts/dev.sh --mobile
```

The combined script prints the exact URL to open from a phone on the same network and
configures it as the allowed development origin. If automatic address detection chooses
the wrong interface, override it explicitly:

```bash
CV_DEV_MOBILE_HOST=192.168.1.23 ./scripts/dev.sh --mobile
```

**Running the product** — no Node process:

```bash
cd frontend && npm run build   # once, and after changing the frontend
./.venv/bin/python -m uvicorn cv_engine.runtime.asgi:app --host 127.0.0.1 --port 8765
./.venv/bin/python -m cv_engine.worker
```

`npm run build` writes to `frontend/dist`; a production caller passes that directory to
`cv_engine.api.create_app` as `frontend_dist`.
FastAPI serves the built assets itself, same-origin with the API. Without a build it
still starts and serves the API alone - that is the dev loop above, where the UI comes
from Vite. `npm run build` also runs `tsc -b` and the design-token check, so it is
slower than `npm run dev` by design.

The explicit Uvicorn bind flags above must match `CV_API_HOST` and `CV_API_PORT`, whose
application defaults are `127.0.0.1` and `8765`. Serving on another address needs both
the corresponding environment setting and Uvicorn flag: the origin policy allows the
origin the app believes it answers on, so changing only Uvicorn refuses every
state-changing request from the app's own UI.

## Generated API contract

`openapi/openapi.json` and `openapi/types.ts` are both generated and both committed, so
a change to a request or response schema arrives as a reviewable diff instead of as a
silent rebuild. `tests/platform/test_api_foundation.py` checks the first; `git diff --exit-code`
after regeneration checks the second. Regenerate after any API change and state the
diff in the commit message:

```bash
./.venv/bin/python openapi/generate_openapi.py
cd openapi && npm ci && npm run generate
```

Read-only storage inspection is available at `GET /api/v1/maintenance/orphans`.
Its `candidates` are managed immutable payload references absent from a database
snapshot, including payloads that active writers may still be registering. It excludes
mutable working projections and performs no deletion. Local and S3 stores share this
inspection contract.

## Tests

The suite truncates every table on each test, so it never runs against the configured
runtime database. It derives its own by appending `_test` to that database's name
(`cv` becomes `cv_test`); `CV_TEST_DATABASE_URL` overrides the derived URL and is
refused if it names the runtime database. Create and migrate it once:

```bash
docker compose exec postgres createdb -U cv cv_test
CV_DATABASE_URL=postgresql+psycopg://cv:cv@127.0.0.1:5433/cv_test ./.venv/bin/alembic upgrade head
```

The default run is the fast, non-browser suite:

```bash
./.venv/bin/python -m pytest -q
```

It covers unit contracts, the default workflow with deterministic renderer doubles,
golden Development/English Sales/Hebrew Sales/Tech Sales cases, migration,
immutability, and targeted regressions. Tests marked `browser` are deselected by the
default `pyproject.toml` configuration.

Browser tests start a real headless Chromium/Chrome. Some
sandboxed agent sessions (for example Codex under Seatbelt) block the browser's Mach
port registration, so the browser cannot start there at all; Chrome's `--no-sandbox`
flag does not help, because it only disables Chrome's own sandbox. Trusted Codex
sessions load `.codex/rules/pytest.rules` at startup, allowing only the project pytest
prefix to run outside Seatbelt. Restart Codex after first checking out the rule.

Run the explicit browser-complete gate in a normal terminal or in CI before `ready` or
completion:

```bash
env CV_REQUIRE_BROWSER=1 ./.venv/bin/python -m pytest -q -m ""
```

The empty marker expression overrides the default `not browser` selection, so this
runs the entire suite, including rendering, PDF, and ATS acceptance checks.
`CV_REQUIRE_BROWSER=1` makes the run fail immediately if browser tests are still
deselected.

## Historical artifacts

The pre-v1 generation scripts and the v1 submission data they wrote (`outputs/`,
`jobs/status.csv`, `cv-html/`) were removed: every row was an unsent `draft`, so it
recorded no submission and preserved no evidence. The v1 source documents — `base/cv_base.md`,
`base/cv-formatted.md`, `base/cv-pdf/` — went with them. Nothing in v2 read them: the
canonical fact sources are `common.json`, `sales.json`, `development.json`, and
`situational_skills.json`.

`ai/prompts/` holds exactly the live prompt. The task contract in
`ai/contracts/task_contracts.json` names it, and a superseded version is deleted rather
than kept beside it: an ApprovedRevision records the prompt version and hash it was
produced under, and the file behind that hash is recoverable from Git history.

Facts migrated out of `cv_base.md` still cite it in their `provenance`. Those strings are
the historical record of where a fact came from and are deliberately left unchanged; the
file they name is recoverable from Git history.
