# Multi-Track CV Engine v2

Fact-safe CV generation and application tracking for Development, Sales, and Tech
Sales. A FastAPI backend and a React frontend; the deterministic workflow reaches
Ready without an AI key.

The binding specifications are under [`docs/spec/`](docs/spec/):
`product-spec.md`, `state-and-use-cases.md`, and `architecture.md`.
[`docs/README.md`](docs/README.md) maps every document.

## Setup

Install `uv`, then bootstrap a dedicated environment for this worktree:

```bash
./scripts/bootstrap-worktree.sh
```

Each worktree keeps its own editable environment, so imports cannot fall through to a
different checkout. `uv` installs third-party packages from its global cache using
copy-on-write clones on macOS, avoiding another physical copy of Playwright's 115 MB
Node driver and the other shared dependencies.

PDF generation uses Playwright-managed Chromium. Playwright's normal macOS browser
cache is shared at `~/Library/Caches/ms-playwright`; the bootstrap refuses
`PLAYWRIGHT_BROWSERS_PATH=0`, which would instead duplicate browser binaries inside
each worktree. To install the browser again without replacing the environment:

```bash
./.venv/bin/python -m playwright install chromium
```

## Architecture

- `base/common.md`, `base/sales.md`, `base/development.md`, and
  `base/situational_skills.md` are the modular canonical fact store.
- `profiles/` selects and weights facts without duplicating content.
- `rendering/rules/` and `rendering/templates/` define Development, Sales LTR/RTL,
  and deterministic profile-specific presentations of canonical facts. Tech Sales
  can therefore shorten Development evidence into business-value wording without
  changing or duplicating the underlying fact.
- `cv_engine/` owns deterministic workflow, validation, persistence, rendering, and AI
  boundaries.
- PostgreSQL stores mutable application state and immutable history, through
  SQLAlchemy Core and numbered Alembic revisions.
- `artifacts/working/` contains replaceable working drafts; approved/rendered versions
  are immutable version directories under `artifacts/<application-id>/`.
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

Everything below describes what the engine does. The Web UI calls the same application
services the API exposes.

**Create the application and its immutable job snapshot.** A posting is captured once
and never re-fetched, because a job description that later vanishes from the web is
evidence nothing else can reproduce.

**Analyze, draft, review.** A draft records the exact job snapshot and job analysis it
was built from, and every later step — validation, approval, rendering, and the Ready
recheck — uses that exact analysis rather than whichever one is newest. Two
consequences follow. A new job snapshot must be analyzed before anything is drafted
against it, and a later analysis that materially changes Track, Profile, Emphasis,
language, Fit, gaps, or keywords invalidates the working draft, so regenerate it before
approving. A re-run that reproduces the same classification changes nothing and leaves
the draft valid.

Drafting stops for review and never renders by default. Manual edits are classified as
exact canonical wording, a versioned deterministic composite, conservatively extractive
derived wording, or a pending claim that blocks approval. Unsupported wording is
retained as `pending`; it is never silently discarded and cannot be approved. Structural
Markdown edits or removed claim markers remain hard failures.

**Approve, render, and read Ready.** Approval freezes exactly the content one
ValidationRun passed, so approving requires obtaining that run first: nothing can
approve content that nothing vouched for. Rendering runs the same content, claim, PDF,
ATS, link, direction, filename, and visual gates every time.

Low fit and material classification ambiguity stop by default. Explicit Track, Profile,
and Emphasis overrides are recorded as decisions, as is accepting a low fit. Overrides
never authorize fabricated facts.

Emphasis is a content decision, not a label. A Profile's `fact_ids` are the candidate
pool a section may draw from, and `config/emphasis.json` weights the canonical fact tags
per Emphasis, so the same Profile produces a different CV under `account-growth` than
under `new-business`. Selection is deterministic and recorded: `resume.claims.json`
carries the score, outcome and omission reason for every candidate considered. Because
Emphasis now changes the document, a disagreement about it between the deterministic
classifier and an AI proposal requires an explicit `--emphasis` decision.

The analyzer also normalizes job language such as outbound, discovery, closing, CRM,
pipeline, integrations, and onboarding into the canonical tag vocabulary. Unverified
direct SaaS Sales, named Sales-CRM usage, and strategic-partnership ownership remain
recorded gaps; verified substitute facts may be selected, but the missing experience
is never inferred from them.

## Fact lifecycle

New information is never written straight into a CV. It enters the store as a `pending`
fact, is confirmed, is promoted to `canonical`, and only then may a Profile section offer
it to the selection policy. Every step writes to the canonical source file under `base/`
and appends an immutable event to `fact_events`, so the status survives the
process and the trail explains who promoted what.

A manual draft edit the fact store cannot support becomes a `pending` claim that blocks
approval. Its wording is captured as a candidate fact rather than retyped: the claim's
exact text becomes the fact's rendering, with no AI rewriting, and meaning, tags, and
provenance are explicit input.

Explicit confirmation is required for every promotion, and `pending -> canonical` in one
step is refused. Until a fact is canonical it cannot be rendered, linked to a claim, or
attached to a Profile, and adding or confirming one never invalidates drafts already
built from the canonical facts. Promoting one to canonical does change the canonical
surface, so the working draft is rebuilt afterwards.

Correcting a canonical fact means creating a replacement that `replaces` it, which
`POST /api/v1/facts` accepts. Identity is always generated - a caller-chosen fact ID is
refused - and a correction never mutates the fact it supersedes.

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

## Optional AI provider

The deterministic engine completes the entire workflow offline. Configuring a key
enables OpenAI classification proposals through the provider-neutral structured task
contract. The Web settings page then offers a closed model catalog and
low/medium/high reasoning effort; those defaults are frozen onto each queued AI
Operation:

```bash
export OPENAI_API_KEY='...'
```

Provider output is Pydantic-validated and deterministic hard gaps remain authoritative.
The adapter uses strict Structured Outputs through the Responses API. Each provider
artifact preserves token usage, the dated pricing snapshot, and its calculated USD
cost; the Operation panel shows the selected model, effort, and final cost.

## Local Web UI

Two ways to run it, for two different jobs.

**Developing the frontend** — no build step:

```bash
./.venv/bin/python -m uvicorn cv_engine.runtime.asgi:app --host 127.0.0.1 --port 8765 --reload
./.venv/bin/python -m cv_engine.worker  # queued work
cd frontend && npm run dev              # localhost:5173
```

Vite compiles on demand and reloads on save. It proxies `/api` to the backend, so the
two are one origin from the browser's point of view. This is the normal loop; nothing
here needs `npm run build`.

**Running the product** — no Node process:

```bash
cd frontend && npm run build   # once, and after changing the frontend
./.venv/bin/python -m uvicorn cv_engine.runtime.asgi:app --host 127.0.0.1 --port 8765
./.venv/bin/python -m cv_engine.worker
```

FastAPI serves the built assets itself, same-origin with the API. Without a build it
still starts and serves the API alone - that is the dev loop above, where the UI comes
from Vite. `npm run build` also runs `tsc -b` and the design-token check, so it is
slower than `npm run dev` by design.

The explicit Uvicorn bind flags above must match `CV_API_HOST` and `CV_API_PORT`, whose
application defaults are `127.0.0.1` and `8765`. Serving on another address needs both
the corresponding environment setting and Uvicorn flag: the origin policy allows the
origin the app believes it answers on, so changing only Uvicorn refuses every
state-changing request from the app's own UI.

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

The pre-v1 generation scripts have been retired, and the v1 submission data they wrote
(`outputs/`, `jobs/status.csv`, `cv-html/`) has been removed: every row was an unsent
`draft`, so it recorded no submission and preserved no evidence. The v1 source documents
it was generated from — `base/cv_base.md`, `base/cv-formatted.md`, `base/cv-pdf/` — and
the superseded `ai/prompts/system-v1.md` were removed with it. Nothing in v2 read them:
the canonical fact sources are `common.md`, `sales.md`, `development.md`, and
`situational_skills.md`, and the task contract names `system-v2.md`.

Facts migrated out of `cv_base.md` still cite it in their `provenance`. Those strings are
the historical record of where a fact came from and are deliberately left unchanged; the
file they name is recoverable from Git history. New work uses `cv` exclusively.
