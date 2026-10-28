# Multi-Track CV Engine v2

Fact-safe CV generation and application tracking for Development, Sales, and Tech
Sales. A FastAPI backend and a React frontend. Job analysis is where AI belongs; from an
existing analysis, everything down to a Ready PDF runs with no key.

The binding specifications are under [`docs/spec/`](docs/spec/).
[`docs/README.md`](docs/README.md) says which document answers which question.

## Setup

Install `uv`, Python 3.11 or newer, and npm, then create a dedicated environment for
this checkout:

```bash
uv venv --python python3 .venv
uv pip install --python .venv/bin/python -e '.[test]'
./.venv/bin/python -m playwright install chromium
npm ci --prefix frontend
[ -e .env ] || cp .env.example .env
```

Each worktree keeps its own editable environment, so imports cannot fall through to a
different checkout. `uv` installs third-party packages from its global cache using
copy-on-write clones on macOS, avoiding another physical copy of Playwright's 115 MB
Node driver and the other shared dependencies.

Run these setup commands once in a new checkout without an existing `.venv`. They
install the locked frontend dependencies and create `.env` from `.env.example`
only when no local configuration exists.

PostgreSQL lifecycle and schema upgrades stay explicit. For the first run, start the
local database and apply the current migrations before starting the application:

```bash
docker compose up -d postgres
./.venv/bin/alembic upgrade head
./.venv/bin/python -m cv_engine.admin create-user --email you@example.com
./scripts/dev.sh
```

Every screen but sign-in requires a session, so the first run creates the one user;
`create-user` prompts for the password twice (12 to 256 characters). A forgotten
password is reset with `python -m cv_engine.admin set-password --email …`, which also
ends every session.

Every screen but sign-in also needs the user's Knowledge (facts, candidate context, and
Profile bindings). `profiles/` holds templates only, so Knowledge comes from a directory
that `export-knowledge` wrote from a database that already has it:

```bash
./.venv/bin/python -m cv_engine.admin export-knowledge --email you@example.com --to /tmp/knowledge
CV_DATABASE_URL=… ./.venv/bin/python -m cv_engine.admin import-knowledge \
  --email you@example.com --from /tmp/knowledge
```

The directory holds the candidate's personal data; delete it once imported.

Multiple worktrees may share the same PostgreSQL server, but worktrees that run in
parallel should use separate databases through `CV_DATABASE_URL`; they do not need
separate PostgreSQL servers.

PDF generation uses Playwright-managed Chromium. Playwright's normal macOS browser
cache is shared at `~/Library/Caches/ms-playwright`; leave `PLAYWRIGHT_BROWSERS_PATH`
unset to avoid duplicating browser binaries inside each worktree. To install the
browser again without replacing the environment:

```bash
./.venv/bin/python -m playwright install chromium
```

## Deployment

[`render.yaml`](render.yaml) is a Render Blueprint for one web service built from the
[`Dockerfile`](Dockerfile). [`scripts/serve.sh`](scripts/serve.sh) migrates, then runs
the API, the worker, and the built UI in one container. PostgreSQL is Neon; immutable
payloads go to an S3-compatible bucket (Cloudflare R2).

- **Database:** `DATABASE_URL` is Neon's *direct* connection string (host without
  `-pooler`). The pooler's transaction mode breaks the worker's session advisory lock
  and Alembic's migration transaction.
- **Bucket:** `CV_S3_BUCKET`, `CV_S3_ENDPOINT_URL` (the account endpoint, without the
  bucket name), `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.
- **Origin:** `CV_PUBLIC_ORIGIN` is the service's exact `https://` URL, no trailing
  slash. Without it every mutation, sign-in included, is refused with `403`.
- **First user:** run `create-user` and `import-knowledge` (Setup) from a checkout with
  `CV_DATABASE_URL` pointing at the deployed database, as `postgresql+psycopg://…`.

On Render's free plan the service sleeps after about 15 idle minutes and the worker
with it; rendered HTML/PDF live on the container's disk and are lost on every restart or
deploy, while submitted files are safe in the bucket. One render's Chromium peaks near
the plan's 512 MB, which is why the Blueprint sets `CV_WORKER_CONCURRENCY=1`. Keeping
the service awake keeps Neon's compute awake too (the worker polls every 0.25 s), which
spends the free plan's 100 compute hours in about two weeks.

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
- The CV document's content lives in PostgreSQL; its rendered HTML/PDF are mutable
  working outputs under `artifacts/documents/`. Immutable payloads — the files a
  Submission sent — live under the fixed `submissions/` key prefix, whose layout is frozen in
  `docs/spec/architecture.md` section 6.2 so a
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
Operations, so neither process supervises the other. Only one worker runs per database:
a second one refuses to start. Work a dead worker left claimed is interrupted when the
next worker starts.

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
stored as text on the Application and never fetched; it can be edited until the first
Submission locks it. Drafting stops for review
and never renders by default; unsupported wording is retained as `pending` rather than
discarded, and cannot be approved. Approval stamps the current document basis after its
content check passes, and rendering then runs the same content, claim, PDF, ATS, link,
direction, filename, and visual gates every time. Low fit and requirement gaps are
diagnostic information, not workflow blockers.

## Fact lifecycle

New information follows `pending -> canonical` on one explicit confirmation
(`docs/spec/product-spec.md` §17); every confirmation writes to the canonical source file under `base/` and appends an
immutable event to `fact_events`. Correcting a canonical fact means creating a
replacement that `replaces` it via `POST /api/v1/facts` — identity is always generated,
and a correction never mutates the fact it supersedes.

## Tracking and inspection

An internal submission requires the exact current Ready document hash. Ready qualification
is checked at submission time; the content and HTML/PDF are copied into immutable
Submission storage with their checksums. An external submission records what is known
without inventing internal document evidence, and a field that cannot be derived stays
null. `applied` is submission-owned: it is reached by recording a submission, never by
asking for it. Recruitment history, corrections, audit records, and submissions are
append-only, and a correction appends an event rather than editing the one it corrects.

## Maintenance

Reconciliation checks database references, artifact hashes, and the fact lifecycle:

```bash
python -m cv_engine.admin reconcile
```

It reports and never repairs: a mismatch against an immutable record is something to be
told about, not something maintenance may quietly fix. The command exits `0` when the
report's `passed` field is true and `2` when reconciliation finds a problem.
Verification goes through the configured payload store, so it reports the truth under
local storage and under an S3 bucket alike. Maintenance is an operator CLI, not a
user-facing HTTP surface.

## AI provider

Creating a new `JobAnalysis` and drafting a document's content both require a
configured provider, with no rules-based fallback (`docs/spec/product-spec.md` §2,
"Semantic analysis authority"). Everything downstream of existing content — editing,
validation, approval, rendering, Ready, export, and recruitment tracking — runs with no
key at all.

A configured key enables five structured OpenAI tasks: `propose_analysis`,
`draft_resume` (which chooses the facts and words them), `regenerate_section`,
`regenerate_claim`, and `assess_claim_support`, the separate reviewer every writing
Operation runs after the writer.
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

Sign-in does not work over this address yet. The session cookie is `Secure` (architecture
§18.4), and a browser stores one only from a secure context: `localhost` and `127.0.0.1`
are, a LAN address over plain HTTP is not. Mobile access needs HTTPS in front of the dev
server first.

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

Read-only storage inspection is available to the operator with
`python -m cv_engine.admin inspect-orphans`. Its `candidates` are managed immutable
payload references that no record references and that were stored more than an hour
ago, so a write still on its way to registration is never listed. It excludes mutable
working outputs and performs no deletion. Nothing in the system deletes an immutable
payload, so orphans are reported, never removed (`docs/spec/architecture.md` section
7.1). Local and S3 stores share this contract.

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
immutability, and targeted regressions. Tests marked `browser` or `eval` are deselected
by the default `pyproject.toml` configuration.

`.github/workflows/ci.yml` runs the browser-complete gate below (on `main`, and on
pull requests that touch rendering or browser tests; the default suite otherwise), the
API contract regeneration check, and the frontend `npm run check` and stubbed Playwright suite on
every pull request and on `main`.

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

The empty marker expression overrides the default `not browser and not eval` selection,
so this runs the entire suite, including rendering, PDF, and ATS acceptance checks. The
paid live eval is collected too and skips, because it needs `CV_RUN_PAID_EVAL=1`.
`CV_REQUIRE_BROWSER=1` makes the run fail immediately if browser tests are still
deselected.

The focused real-server frontend journey uses the same isolated PostgreSQL test
database described above. With frontend dependencies installed (`npm ci --prefix
frontend`) and its Chromium installed (`cd frontend && npx playwright install chromium`),
run from the project root:

```bash
./.venv/bin/python -m pytest -q -m browser tests/e2e/test_browser_api_journey.py
```

Pytest builds React into a temporary directory, starts FastAPI serving that build on
one origin, and launches the separate Playwright integration configuration. The intake
test drives creation, reload, list navigation, and duplicate acknowledgement with no
provider or worker. The preparation test runs the real worker outside the API process
and drives analysis, AI drafting, checking, approval, real PDF rendering and
download, and submission through the UI. Only the provider transport is scripted;
neither test intercepts API requests, and `OPENAI_API_KEY` remains unset. The preparation
test also needs the Python renderer's Chromium (`./.venv/bin/python -m playwright install chromium`).
Do not run other database suites concurrently against the same test database.
The ordinary `npm --prefix frontend run e2e` suite keeps its stubbed API and excludes
these integration tests.

Both Playwright configurations launch the Chromium that `npx playwright install chromium`
placed, unless `CV_PLAYWRIGHT_CHROMIUM` names another executable. In a cloud agent
container (`CLAUDE_CODE_REMOTE=true`) they use the preinstalled
`$PLAYWRIGHT_BROWSERS_PATH/chromium` instead (`frontend/playwright.chromium.ts`).

### Evaluating prompt changes

Before and after changing `ai/prompts/system.md`, `ai/contracts/task_contracts.json`, or
the model, run the paid live eval and compare the two reports. It runs three fixed
postings through the real OpenAI provider and renderer, costs roughly $0.50–$1.50 per
run, and writes `tmp/evals/<UTC timestamp>.json`:

```bash
CV_RUN_PAID_EVAL=1 OPENAI_API_KEY=... ./.venv/bin/python -m pytest -q -s -m eval tests/evals
./.venv/bin/python scripts/compare_evals.py tmp/evals/<before>.json tmp/evals/<after>.json
```

What it scores, its floors, and what stays manual: `docs/spec/test-and-acceptance-plan.md`
§6.1.

## Historical artifacts

The pre-v1 generation scripts and the v1 submission data they wrote (`outputs/`,
`jobs/status.csv`, `cv-html/`) were removed: every row was an unsent `draft`, so it
recorded no submission and preserved no evidence. The v1 source documents — `base/cv_base.md`,
`base/cv-formatted.md`, `base/cv-pdf/` — went with them. Nothing in v2 read them: the
canonical fact sources are `common.json`, `sales.json`, `development.json`, and
`situational_skills.json`.

`ai/prompts/` holds exactly the live prompt, `ai/prompts/system.md`. A prompt change edits
that file in place and bumps the prompt version in `ai/contracts/task_contracts.json`;
no versioned copy is kept beside it. The AI call log (`ai_calls`) records the prompt
version and hash used by each call, and the file behind that hash is recoverable from Git history.

Facts migrated out of `cv_base.md` still cite it in their `provenance`. Those strings are
the historical record of where a fact came from and are deliberately left unchanged; the
file they name is recoverable from Git history.
